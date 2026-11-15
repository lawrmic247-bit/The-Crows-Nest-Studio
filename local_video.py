"""Optional local-only ComfyUI shot generation for Crow's Nest Studio.

ComfyUI and model checkpoints are installed independently. No paid service,
no non-loopback HTTP calls, and no model download or user-supplied Python execution.
Workflows must be exported in ComfyUI API format, with __CROWS_PROMPT__
inside one positive text-encoder node, before import.
"""
from __future__ import annotations
import copy
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:8188"
MAX_BYTES = 90 * 1024 * 1024
ACCEPTED_EXTS = {".mp4",".webm",".mov",".gif"}


class LocalVideoError(RuntimeError):
    pass


def _request(path:str,payload:dict|None=None,*,urlopen=None,limit=2_000_000,
             timeout=12)->bytes:
    if urlopen is None:urlopen=urllib.request.urlopen
    if not path.startswith("/") or path.startswith("//"):
        raise LocalVideoError("Only local ComfyUI routes can be queried.")
    url=BASE+path
    if payload is None:
        req=urllib.request.Request(url,headers={"User-Agent":"CrowsNestStudio/4.3"})
    else:
        req=urllib.request.Request(
            url,data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type":"application/json","User-Agent":"CrowsNestStudio/4.3"},
            method="POST")
    with urlopen(req,timeout=timeout) as response:
        raw=response.read(limit+1)
    if len(raw)>limit:
        raise LocalVideoError("Video engine response exceeds the safety limit.")
    return raw


def status(*,urlopen=None)->str:
    try:
        raw=json.loads(_request("/system_stats",urlopen=urlopen))
        system=raw.get("system",{})
        devices=raw.get("devices",[])
        display=str(devices[0].get("name","unknown accelerator")) if devices else "accelerator unknown"
        return "Connected to local ComfyUI: "+display
    except (urllib.error.URLError,TimeoutError,OSError,ValueError,KeyError,TypeError) as exc:
        raise LocalVideoError("ComfyUI is not running locally at 127.0.0.1:8188. "
                              "Open ComfyUI first. No cloud fallback is used.") from exc


def load_workflow(path:Path)->dict:
    path=Path(path)
    if path.suffix.lower()!=".json" or not path.is_file() or path.stat().st_size>1_500_000:
        raise LocalVideoError("Choose a ComfyUI API-format workflow JSON under 1.5 MB.")
    raw=json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw,dict) or not 1<=len(raw)<=200:
        raise LocalVideoError("Expected an API-format object keyed by node IDs.")
    found=0
    for node_id,node in raw.items():
        if not isinstance(node_id,str) or not isinstance(node,dict):
            raise LocalVideoError("Workflow node structure is invalid.")
        inputs=node.get("inputs")
        if not isinstance(node.get("class_type"),str) or not isinstance(inputs,dict):
            raise LocalVideoError("Export workflow in API format, not UI graph format.")
        for key,value in inputs.items():
            if isinstance(value,str) and "__CROWS_PROMPT__" in value:
                found+=1
    if found!=1:
        raise LocalVideoError("Place __CROWS_PROMPT__ exactly once in the positive prompt text node.")
    return raw


def prepare_workflow(template:dict,prompt:str)->dict:
    if not isinstance(prompt,str) or not 12<=len(prompt)<=1800:
        raise LocalVideoError("Prompt must be 12–1800 characters.")
    graph=copy.deepcopy(template)
    for node in graph.values():
        for name,value in node["inputs"].items():
            if isinstance(value,str) and "__CROWS_PROMPT__" in value:
                node["inputs"][name]=value.replace("__CROWS_PROMPT__",prompt)
    return graph


def _outputs(history:dict,prompt_id:str)->list[dict]:
    item=history.get(prompt_id,history)
    if not isinstance(item,dict):
        return []
    outputs=item.get("outputs",{})
    rows=[]
    for node in outputs.values():
        if not isinstance(node,dict):continue
        for field in ("videos","gifs","images"):
            for data in node.get(field,[]):
                name=str(data.get("filename",""))
                if Path(name).suffix.lower() in ACCEPTED_EXTS:
                    rows.append(data)
    return rows


def generate_clip(prompt:str,workflow:Path,out:Path,*,urlopen=None,
                  poll_interval=4,deadline_seconds=900)->Path:
    """Queue one trusted local ComfyUI workflow and retrieve an output video."""
    if not 5<=deadline_seconds<=3600:
        raise LocalVideoError("Generation deadline must be between 5 and 3600 seconds.")
    template=load_workflow(workflow)
    data={"prompt":prepare_workflow(template,prompt),"client_id":uuid.uuid4().hex}
    submission=json.loads(_request("/prompt",data,urlopen=urlopen))
    prompt_id=submission.get("prompt_id")
    if not isinstance(prompt_id,str) or not re.fullmatch(r"[a-z0-9-]{8,80}",prompt_id,re.I):
        raise LocalVideoError("ComfyUI rejected the queued workflow: "+str(submission.get("error","unknown")))
    stop=time.monotonic()+deadline_seconds
    while time.monotonic()<stop:
        history=json.loads(_request("/history/"+prompt_id,urlopen=urlopen))
        if prompt_id in history:
            record=history[prompt_id]
            if record.get("status",{}).get("status_str")=="error":
                raise LocalVideoError("ComfyUI reported a generation error; inspect its local queue.")
            files=_outputs(history,prompt_id)
            if files:
                candidate=files[0]
                name=str(candidate.get("filename",""))
                suffix=Path(name).suffix.lower()
                if suffix==".gif":
                    raise LocalVideoError("Workflow returned a GIF. Configure an MP4/WebM SaveVideo output.")
                route="/view?"+urllib.parse.urlencode({
                    "filename":name,
                    "subfolder":str(candidate.get("subfolder","")),
                    "type":str(candidate.get("type","output")),
                })
                raw=_request(route,urlopen=urlopen,limit=MAX_BYTES,timeout=120)
                if len(raw)<1000:
                    raise LocalVideoError("ComfyUI exported an empty video.")
                out=Path(out).with_suffix(suffix)
                out.parent.mkdir(parents=True,exist_ok=True)
                tmp=out.with_suffix(out.suffix+".partial")
                tmp.write_bytes(raw)
                os.replace(tmp,out)
                return out
            if record.get("status",{}).get("completed"):
                raise LocalVideoError("The workflow finished without an MP4/WebM clip.")
        time.sleep(poll_interval)
    raise LocalVideoError("ComfyUI timed out; check its queue. This does not mean it stopped rendering.")


def build_reenactment_prompt(heading:str,subject:str)->str:
    """Avoid synthetic imagery being mistaken for actual historical footage."""
    return (
        "Historical illustration only, NOT authentic archival footage. "
        "Cinematic realistic reconstruction of a military history documentary "
        "with restrained camera movement, no captions or insignia forgery. "
        "Research subject: "+subject[:200]+". Scene: "+heading[:220]+". "
        "Do not depict a known individual's identifiable face without a verified reference. "
        "Avoid invented exact casualty numbers, medals, or documentary evidence."
    )
