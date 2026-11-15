#!/usr/bin/env python3
"""Local, review-gated prompt-to-episode production queue.

No invented fact-check clearance, auto publishing, or paid-cloud fallbacks.
Ollama is required for new scripts; historical claims remain unverified until reviewed.
"""
from __future__ import annotations
import argparse
import html
import json
import math
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local'/'share')/'TheCrowsNestStudio'
QUEUE = DATA/'production_queue'
EPISODES = ROOT/'episodes'
MEDIA_DIR = DATA/'media'
LOCK = threading.RLock()
FORMATS = ('short','wide','both')
VISUAL_STYLES = ('archival','motion','hybrid','ai_reenactment')
JOB_SCHEMA = 'crowsnest.job.v1'
STATUSES = ('queued','researching','drafting','gathering_media','awaiting_review','ready','rendering','finished','needs_model','failed')
MAX_NOTES = 20000
USER_AGENT = 'CrowsNestStudio/4.0 (+local documentary editor; contact via Wikimedia Commons)'


KEYWORDS = ("grenade","saved","risked","sacrific","medal of honor","rescued",
            "ambush","wounded","survived","against","suddenly","never",
            "remember","returned","courage","first","last","because")


def _sentences(scenes):
    text=" ".join(str(x.get("narration","")).strip() for x in scenes)
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+",text) if x.strip()]


def distill_story(scenes:list[dict],target:str)->list[dict]:
    """Choose hook, stakes and payoff for a short-form adaptation.

    YouTube Shorts target ~50–60 s and TikTok ~65–85 s at conversational speed.
    The user must still verify facts, context, assets and pronunciation.
    """
    if target not in ("shorts","tiktok"):
        raise ValueError("Expected shorts or tiktok")
    sentences=_sentences(scenes)
    if not sentences:
        raise ValueError("Documentary has no narration")
    limit=116 if target=="shorts" else 164
    def weight(i):
        sentence=sentences[i].lower()
        return sum(4 for phrase in KEYWORDS if phrase in sentence)+min(len(sentence.split()),12)/12
    n=len(sentences)
    first_candidates=range(max(1,n//3))
    hook=max(first_candidates,key=weight)
    middle_candidates=range(n//3,max(n//3+1,2*n//3))
    context=max(middle_candidates,key=weight) if middle_candidates else min(n-1,hook+1)
    tail_candidates=range(max(0,2*n//3),n)
    payoff=max(tail_candidates,key=weight) if tail_candidates else n-1
    choices=list(dict.fromkeys((hook,context,payoff)))
    words=sum(len(sentences[i].split()) for i in choices)
    # More evidence-rich supporting sentences, in chronological order after hook.
    for i in sorted(range(n),key=weight,reverse=True):
        length=len(sentences[i].split())
        if i in choices or words+length>limit:
            continue
        choices.append(i)
        words+=length
        if words>=limit-17:
            break
    if words<8:
        raise ValueError("Insufficient source narrative to make even a brief short")
    remainder=[sentences[i] for i in sorted(set(choices)-{hook})]
    split=max(1,len(remainder)//2)
    chapters=(("The Hook",sentences[hook]),
              ("The Stakes"," ".join(remainder[:split])),
              ("The Payoff"," ".join(remainder[split:])))
    return [{"heading":heading,"narration":text} for heading,text in chapters if text.strip()]


def social_story(scenes:list[dict],target:str,*,rewrite=None)->list[dict]:
    """Optional Ollama storytelling pass; safe extraction when unavailable.

    Human fact-check and rights review always remain mandatory. The generated
    version is not treated as a verified historical source.
    """
    fallback=distill_story(scenes,target)
    if rewrite is None:
        return fallback
    full=" ".join(str(scene.get("narration","")) for scene in scenes)
    if len(full)<350:
        return fallback
    words=110 if target=="shorts" else 165
    prompt=(
        "Rewrite an EXISTING sourced documentary into one exciting but factually "
        "faithful vertical social video. Target "+str(words)+" spoken words. "
        "First sentence: a punchy true hook. Middle: immediate stakes and context. "
        "End: what happened and why it matters. Use THREE concise paragraphs only, "
        "without titles or hashtags. Never invent a quote, person, casualty, place, "
        "date, numerical detail, event, or outcome. Do not embellish visuals as history. "
        "If a detail is not in the source, OMIT it. Keep the chronology and identities accurate. "
        "Original, UNVERIFIED documentary (rewrite only what it says):\n"+full[:16000]
    )
    try:
        result=rewrite(prompt,target)
        if not isinstance(result,str):
            return fallback
        paragraphs=[p.strip() for p in re.split(r"\n\s*\n+",result) if p.strip()]
        clean=" ".join(paragraphs)
        count=len(clean.split())
        bounds=(68,128) if target=="shorts" else (100,188)
        if not (bounds[0]<=count<=bounds[1]):
            return fallback
        # Reject any new numeric claims; even this check is not fact verification.
        source_nums=set(re.findall(r"\b\d+(?:,\d{3})*\b",full))
        new_nums=set(re.findall(r"\b\d+(?:,\d{3})*\b",clean))
        if not new_nums.issubset(source_nums):
            return fallback
        parts=paragraphs if len(paragraphs)==3 else [
            " ".join(clean.split()[:count//3]),
            " ".join(clean.split()[count//3:2*count//3]),
            " ".join(clean.split()[2*count//3:])
        ]
        return [{"heading":heading,"narration":part}
                for heading,part in zip(("The Hook","The Stakes","The Payoff"),parts)]
    except (RuntimeError,OSError,ValueError):
        return fallback


def available_outputs(formats):
    values=("full","shorts","tiktok")
    if not isinstance(formats,(list,tuple)) or not formats:
        raise ValueError("Choose at least one video output")
    if len(set(formats))!=len(formats) or not set(formats).issubset(values):
        raise ValueError("Unknown or duplicate output")
    return list(formats)



def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def slugify(s: str, limit=42):
    return re.sub(r'[^a-z0-9]+','_',s.lower()).strip('_')[:limit] or 'episode'


def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    target=path.with_name(path.name+'.tmp')
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(target,path)


def create_job(prompt:str, *, minutes:int=5, fmt:str='wide', model:str='qwen3:8b',
               voice:str='kokoro:am_onyx', notes_file:str='', auto_media:bool=True,
               visual_style:str='archival', deliverables=None) -> dict:
    prompt=' '.join(prompt.strip().split())
    if not 12<=len(prompt)<=3000:raise ValueError('Prompt must contain 12–3000 characters.')
    if not 1<=int(minutes)<=30:raise ValueError('Duration must be 1–30 minutes.')
    if fmt not in FORMATS:raise ValueError('Choose short, wide, or both.')
    if visual_style not in VISUAL_STYLES:raise ValueError('Choose archival, motion, hybrid, or AI reenactment visual style.')
    if deliverables is None:
        deliverables={'wide':['full'],'short':['shorts'],'both':['full','shorts','tiktok']}[fmt]
    deliverables=available_outputs(deliverables)
    if not re.fullmatch(r'[\w.:-]{2,100}',model):raise ValueError('Invalid local model name.')
    if notes_file and (not Path(notes_file).is_file() or Path(notes_file).stat().st_size>512_000):
        raise ValueError('Research notes must be an existing plain-text file under 500 KB.')
    ident=uuid.uuid4().hex[:12]
    job={'id':ident,'prompt':prompt,'title':prompt[:95],'minutes':int(minutes),'format':fmt,
         'model':model,'voice':voice,'notes_file':notes_file,'auto_media':bool(auto_media),
          'visual_style':visual_style,'deliverables':deliverables,'variants':{},
         'status':'queued','created_at':now(),'updated_at':now(),'error':'',
         'manifest':'','media_credits':'','research_leads':'','progress':'Waiting to run','script_words':0,
         'current_step':0}
    with LOCK:atomic_json(QUEUE/(ident+'.json'),job)
    return job


def import_chatgpt_job(path: Path, *, source_folder: Path | None=None) -> dict:
    """Import a private .json file from a locally synced ChatGPT job inbox.

    No remote code, credentials, network requests, or automatic publishing.
    An imported request remains in the normal queued/review-gated workflow.
    """
    path=Path(path).resolve()
    if source_folder is not None and path.parent != Path(source_folder).resolve():
        raise ValueError('Job file must be directly inside the configured inbox folder.')
    if path.suffix.lower()!='.json' or not path.is_file() or path.stat().st_size>120_000:
        raise ValueError('Select an existing ChatGPT job JSON under 120 KB.')
    raw=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(raw,dict) or raw.get('schema')!=JOB_SCHEMA:
        raise ValueError('Unrecognized ChatGPT job format. Expected crowsnest.job.v1.')
    allowed={'schema','topic','title','minutes','format','visual_style','voice','auto_media','research_notes','script','scenes','deliverables'}
    if any(k not in allowed for k in raw):
        raise ValueError('Unrecognized fields in ChatGPT job request.')
    for job in list_jobs():
        if job.get('source_file')==str(path):
            return job
    topic=raw.get('topic','')
    if not isinstance(topic,str):
        raise ValueError('Job topic must be text.')
    minutes=raw.get('minutes',10)
    if isinstance(minutes,bool) or not isinstance(minutes,int):
        raise ValueError('Job length must be an integer.')
    notes=raw.get('research_notes','')
    if not isinstance(notes,str) or len(notes)>MAX_NOTES:
        raise ValueError('Research notes cannot exceed 20,000 characters.')
    job=create_job(topic,minutes=minutes,fmt=raw.get('format','wide'),
                   voice=raw.get('voice','kokoro:am_onyx'),
                   visual_style=raw.get('visual_style','archival'),
                   auto_media=raw.get('auto_media',True),
                   deliverables=raw.get('deliverables',['full','shorts','tiktok']))
    if notes.strip():
        notes_path=QUEUE/(job['id']+'_notes.txt')
        notes_path.write_text(notes,encoding='utf-8')
        job=change(job['id'],notes_file=str(notes_path))
    # A ChatGPT-authored script can bypass the local Ollama drafting step.
    # This never bypasses the normal fact-check and media-rights approval gate.
    prepared=None
    if 'scenes' in raw:
        rows=raw['scenes']
        if not isinstance(rows,list) or not 1<=len(rows)<=50:
            raise ValueError('Prepared scenes must be a list with 1–50 sections.')
        prepared=[]
        for i,row in enumerate(rows,1):
            if not isinstance(row,dict) or set(row)-{'heading','narration'}:
                raise ValueError('Scene may contain only heading and narration.')
            words=row.get('narration','')
            heading=row.get('heading',f'Part {i}')
            if not isinstance(words,str) or not isinstance(heading,str):
                raise ValueError('Scene narration and heading must be text.')
            words=words.strip()
            if not 20<=len(words)<=12000:
                raise ValueError('Prepared scene must have 20–12000 characters.')
            prepared.append({'heading':heading.strip()[:90] or f'Part {i}',
                             'narration':words})
    elif 'script' in raw:
        script=raw['script']
        if not isinstance(script,str) or not 100<=len(script)<=85000:
            raise ValueError('Prepared script must have 100–85000 characters.')
        paragraphs=[x.strip() for x in re.split(r'\n\s*\n+',script) if x.strip()]
        if not paragraphs:
            raise ValueError('Prepared script is empty.')
        if len(paragraphs)>50:
            per=math.ceil(len(paragraphs)/50)
            paragraphs=['\n\n'.join(paragraphs[i:i+per])
                        for i in range(0,len(paragraphs),per)]
        prepared=[{'heading':f'Part {i}','narration':part}
                  for i,part in enumerate(paragraphs,1)]
    if prepared is not None:
        if sum(len(x['narration']) for x in prepared)>85000:
            raise ValueError('Prepared script is too long.')
        prepared_path=QUEUE/(job['id']+'_prepared.json')
        atomic_json(prepared_path,{'scenes':prepared})
        job=change(job['id'],prepared_scenes_file=str(prepared_path),
                   progress='Prewritten script imported; ready for archival media and review.')

    title=raw.get('title','')
    if title:
        if not isinstance(title,str):
            raise ValueError('Job title must be text.')
        job=change(job['id'],title=title.strip()[:95] or topic[:95])
    return change(job['id'],source_file=str(path),
                  progress='Imported from your private ChatGPT inbox; awaiting draft generation.')


def job_path(job_id:str)->Path:
    if not re.fullmatch(r'[0-9a-f]{12}',job_id):raise ValueError('Invalid job ID')
    return QUEUE/(job_id+'.json')


def get_job(job_id:str)->dict:
    obj=json.loads(job_path(job_id).read_text(encoding='utf-8'))
    if obj.get('id')!=job_id:raise ValueError('Queue item ID mismatch')
    return obj


def list_jobs()->list[dict]:
    if not QUEUE.exists():return []
    jobs=[]
    for p in QUEUE.glob('*.json'):
        try:jobs.append(get_job(p.stem))
        except (OSError,ValueError,KeyError):pass
    return sorted(jobs,key=lambda x:x['created_at'],reverse=True)


def change(job_id:str, **fields)->dict:
    with LOCK:
        old=get_job(job_id)
        old.update(fields,updated_at=now())
        atomic_json(job_path(job_id),old)
        return old


def ollama_generate(model:str,prompt:str,*,predict:int=1400,request=None)->str:
    payload={'model':model,'prompt':prompt,'stream':False,'options':{'temperature':0.45,'num_predict':predict}}
    data=json.dumps(payload).encode('utf-8')
    req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=data,
            headers={'Content-Type':'application/json'},method='POST')
    try:
        if request is None:request=urllib.request.urlopen
        with request(req,timeout=900) as response:
            raw=response.read(8_000_000)
        answer=json.loads(raw.decode('utf-8'))
        if answer.get('error'):raise RuntimeError(str(answer['error']))
        text=str(answer.get('response','')).strip()
        if not text:raise RuntimeError('Ollama returned an empty response. Try a different local model.')
        return text
    except (urllib.error.URLError,ConnectionError) as exc:
        raise RuntimeError('Ollama is not available locally. Install Ollama, run `ollama pull qwen3:8b`, and retry. '+str(exc)) from exc


def _search_terms(prompt:str)->str:
    """A concise search query, never an instruction sent to an external source."""
    text=re.sub(r"(?i)^(?:make|create|write|research|tell|explain|produce)\s+"
                r"(?:me\s+)?(?:(?:a|an|the)\s+)?(?:(?:\d+[\s-]*minute)\s+)?"
                r"(?:video|documentary|episode|story)?\s*(?:of|about|on)?\s*",
                "",prompt.strip())
    words=re.findall(r"[\wÀ-ỹ'-]+",text)
    return " ".join(words[:14])[:160] or prompt[:100]


def _research_json(url:str,*,fetch=None)->dict:
    """Read from two documented public metadata endpoints only, within time limits."""
    parts=urllib.parse.urlsplit(url)
    if parts.scheme!="https" or parts.hostname not in {"en.wikipedia.org","www.loc.gov"}:
        raise ValueError("Unexpected research service.")
    if fetch is None:fetch=urllib.request.urlopen
    req=urllib.request.Request(url,headers={"User-Agent":"CrowsNestStudio/4.4 (research-only)",
                                            "Accept":"application/json"})
    with fetch(req,timeout=12) as response:
        raw=response.read(1_400_001)
    if len(raw)>1_400_000:
        raise ValueError("Research API response exceeded limit.")
    content=json.loads(raw.decode("utf-8"))
    if not isinstance(content,dict):
        raise ValueError("Research API response must be an object.")
    return content


def discover_research(topic:str,*,fetch=None)->dict:
    """Gather real external source records; nothing here is fact-check clearance.

    Wikipedia search results are secondary leads; Library of Congress results
    are official bibliographic records, not verified support for a specific claim.
    Browser/search-link fallback is provided if a service is offline.
    """
    query=_search_terms(topic)
    sources=[];warnings=[]
    q=urllib.parse.quote(query,safe="")
    requests=(
        ("Wikipedia","https://en.wikipedia.org/w/rest.php/v1/search/page?q="+q+"&limit=5"),
        ("Library of Congress","https://www.loc.gov/search/?fo=json&c=6&q="+q),
    )
    for label,url in requests:
        try:
            data=_research_json(url,fetch=fetch)
            rows=data.get("pages",[]) if label=="Wikipedia" else data.get("results",[])
            if not isinstance(rows,list):
                raise ValueError("Research service provided an invalid result list.")
            for item in rows[:8]:
                if not isinstance(item,dict):continue
                title=str(item.get("title") or "").strip()
                if not title:continue
                if label=="Wikipedia":
                    key=item.get("key") or title.replace(" ","_")
                    page_url="https://en.wikipedia.org/wiki/"+urllib.parse.quote(str(key),safe="/:_-()")
                    excerpt=strip_html(str(item.get("excerpt") or item.get("description") or ""))
                else:
                    page_url=str(item.get("id") or "")
                    if not page_url.startswith("https://www.loc.gov/"):
                        continue
                    descr=item.get("description") or item.get("subject") or ""
                    if isinstance(descr,list):descr="; ".join(str(x) for x in descr[:4])
                    excerpt=strip_html(str(descr))
                # Search ranking can be poor for historical people. Favor matches.
                query_terms={x.lower() for x in re.findall(r"[a-zA-Z]{4,}",query)}
                stop={"about","video","military","history","documentary","the","their",
                      "with","from","american","story","medal","honor"}
                query_terms-=stop
                title_words={x.lower() for x in re.findall(r"[a-zA-Z]{4,}",title)}
                if query_terms and not query_terms.intersection(title_words):
                    continue
                if any(e['url']==page_url for e in sources):
                    continue
                sources.append({"title":title[:180],"url":page_url,
                                "publisher":label,"excerpt":excerpt[:700],
                                "type":("secondary overview" if label=="Wikipedia" else
                                        "official collection metadata"),
                                "status":"RESEARCH LEAD — original page must be checked",
                                "verified":False})
                if len(sources)>=10:break
        except (OSError,TimeoutError,ValueError,TypeError,KeyError,
                urllib.error.HTTPError,urllib.error.URLError) as exc:
            warnings.append(label+" temporarily unavailable: "+str(exc)[:150])
    # Expand the strongest encyclopedia leads into useful research context.
    # These remain secondary sources and must not be treated as verified proof.
    wiki_items=[item for item in sources if item['publisher']=='Wikipedia'][:2]
    for item in wiki_items:
        title=item['title'].replace(' ','_')
        extract_url=('https://en.wikipedia.org/w/api.php?' +
                     urllib.parse.urlencode({
                         'action':'query','prop':'extracts','explaintext':'1',
                         'format':'json','formatversion':'2',
                         'exchars':'4200','titles':title}))
        try:
            doc=_research_json(extract_url,fetch=fetch)
            pages=doc.get('query',{}).get('pages',[])
            if pages and isinstance(pages,list):
                content=str(pages[0].get('extract','')).strip()
                if len(content)>len(item.get('excerpt','')):
                    item['excerpt']=content[:4200]
        except (OSError,TimeoutError,ValueError,TypeError,KeyError,
                urllib.error.HTTPError,urllib.error.URLError):
            pass
    return {"topic":topic,"query":query,"retrieved_at":now(),
            "sources":sources,"warnings":warnings,
            "notice":"AUTOMATED DISCOVERY ONLY. None of these sources verifies any claim. "
                     "Check primary sources and exact excerpts before approving factual claims."}


def research_brief(report:dict)->str:
    """Human-readable source leads for local Ollama, explicitly untrusted data."""
    sections=[
        "AUTOMATIC SOURCE DISCOVERY — ALL CLAIMS STILL REQUIRE HUMAN FACT CHECK.",
        "Do not treat result summaries as proof. Do not cite a URL without opening it.",
        "TOPIC: "+str(report.get("topic","")),
    ]
    for idx,item in enumerate(report.get("sources",[])[:9],1):
        sections.append(f"\nSOURCE LEAD {idx} [{item['publisher']}, {item['type']}]: "
                        f"{item['title']}\nURL: {item['url']}\n"
                        f"RETRIEVED SUMMARY (UNVERIFIED): {item.get('excerpt','')[:1800]}")
    if not report.get("sources"):
        sections.append("\nNo external sources returned. Do NOT invent dates, names or numbers.")
    return "\n".join(sections)[:MAX_NOTES]


def research_notes(job:dict)->str:
    file=job.get('notes_file','')
    if not file:return ''
    return Path(file).read_text(encoding='utf-8',errors='replace')[:MAX_NOTES]


def _heading(text:str)->str:
    return re.sub(r'[^A-Za-z0-9 .,()\-\u2019]','',text).strip()[:90] or 'The Story'


def _clean_narration(text:str)->str:
    # Strip thinking, outline markdown, and bracketed stage directions that TTS would speak.
    text=re.sub(r'<think>.*?</think>','',text,flags=re.S|re.I)
    text=re.sub(r'^```(?:text)?|```$','',text,flags=re.M)
    text=re.sub(r'^\s*(?:Narration|Script|Voiceover):\s*','',text,flags=re.I)
    text=re.sub(r'(?m)^\s{0,5}#{1,4}\s+.*$','',text)
    return ' '.join(text.split()).strip(' "')


def _headings_from_outline(s:str, count:int)->list[str]:
    s=re.sub(r'<think>.*?</think>','',s,flags=re.S|re.I)
    s=s.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    try:
        value=json.loads(s)
        if isinstance(value,dict):value=value.get('sections',value.get('headings',[]))
        if isinstance(value,list):
            out=[_heading(x if isinstance(x,str) else x.get('heading','')) for x in value]
            if len(out)>=2:return out[:count]
    except (ValueError,AttributeError,TypeError):pass
    out=[_heading(re.sub(r'^[-*\d.)\s]+','',x)) for x in s.splitlines() if x.strip()]
    return out[:count] if len(out)>=2 else []


def generate_scenes(job:dict, *,complete=None,ollama=ollama_generate)->list[dict]:
    notes=research_notes(job)
    mins=job['minutes']
    requested_words=max(120,mins*125)
    count=min(18,max(3,math.ceil(mins*1.3)))
    source_instructions=('Use ONLY information directly established in the supplied research notes. '
        'If there is not enough evidence, use hedged language, avoid specific dates and unverified details, '
        'and include an open question for the reviewer. Do not fabricate citations. '
        'All factual assertions still require manual review.') if notes else (
        'This is an UNVERIFIED draft. Avoid made-up quotations, exact casualty figures, precise dates, '
        'unverified operations, or claims about current events. Never invent sources. Flag gaps for fact-check review.')
    topic=job['prompt']
    notes_section=('RESEARCH NOTES (not automatically verified):\n'+notes[:9000]) if notes else 'NO VERIFIED RESEARCH NOTES PROVIDED.'
    plan=ollama(job['model'],
        f'Plan a military history documentary for The Crow\'s Nest, an INDEPENDENT UNOFFICIAL channel. '
        f'Topic: {topic}\nDuration {mins} min. Visual style: {job.get("visual_style","archival")}. Write exactly {count} chronological or narrative section headings. '
        f'Output ONLY a JSON array of strings. No quotations or invented facts.\n{notes_section}',predict=550)
    headings=_headings_from_outline(plan,count)
    while len(headings)<count:headings.append(f'Part {len(headings)+1}: {_heading(topic[:50])}')
    words_per=math.ceil(requested_words/count)
    scenes=[]
    for i,heading in enumerate(headings,1):
        if complete:complete(i,count,'Drafting '+heading)
        instruction=(f'Write the spoken narration for section {i} of {count} in an American history documentary. '
           f'Title: {heading}. Topic: {topic}. Target {words_per} spoken words (at least {max(55,words_per-20)}). '
           f'Voice: grounded, memorable, never falsely sensational. '
           f'Previous section headings: {", ".join(headings[:i-1])[-300:]}. '
           f'Upcoming headings: {", ".join(headings[i:i+2])[-200:]}. '
           f'{source_instructions}\n{notes_section}\n'
           'Return ONLY final narration text in paragraphs without labels, notes, markdown headings, sources, or performance directions.')
        speech=_clean_narration(ollama(job['model'],instruction,predict=min(1200,words_per*3+150)))
        if len(speech.split())<min(30,words_per*.25):raise RuntimeError(f'Section {i} had too little narration; Ollama output not usable.')
        scenes.append({'heading':heading,'narration':speech})
    return scenes


class _StripHTML(HTMLParser):
    def __init__(self):super().__init__();self.s=[]
    def handle_data(self,s):self.s.append(s)

def strip_html(s:str)->str:
    parser=_StripHTML();parser.feed(html.unescape(s or ''))
    return ' '.join(' '.join(parser.s).split())[:500]


def commons_candidates(query:str,limit:int=8, *,fetch=None)->list[dict]:
    """Wikimedia Commons still-image discovery; licenses are never assumed public domain."""
    args={'action':'query','generator':'search','gsrsearch':query+' filetype:bitmap',
          'gsrnamespace':'6','gsrlimit':str(min(limit+8,30)),
          'prop':'imageinfo','iiprop':'url|extmetadata|mime',
          'iiurlwidth':'1280','format':'json'}
    url='https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(args)
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT})
    if fetch is None:fetch=urllib.request.urlopen
    with fetch(req,timeout=18) as resp: payload=json.loads(resp.read(1_500_000))
    rows=[]
    for page in payload.get('query',{}).get('pages',{}).values():
        info=(page.get('imageinfo') or [None])[0]
        if not info or not info.get('mime','').startswith('image/'):continue
        meta=info.get('extmetadata') or {}
        def field(k):return strip_html((meta.get(k) or {}).get('value',''))
        license_name=field('LicenseShortName').lower()
        if not any(x in license_name for x in ('public domain','cc0','cc-by','cc by','cc-by-sa','cc by-sa')):continue
        image_url=info.get('thumburl') or info.get('url') or ''
        parsed=urllib.parse.urlparse(image_url)
        if parsed.scheme!='https' or parsed.hostname not in ('upload.wikimedia.org','commons.wikimedia.org'):continue
        rows.append({'title':str(page.get('title','')),'url':image_url,
                     'page_url':info.get('descriptionurl',''),'license':field('LicenseShortName'),
                     'artist':field('Artist') or field('Credit'),
                     'credit':field('Attribution') or field('AttributionRequired'),
                     'restrictions':field('Restrictions')})
    return rows[:limit]


def download_commons_images(job:dict, scenes:list[dict], *,fetch=None)->tuple[list[dict],Path]:
    dest=MEDIA_DIR/job['id'];dest.mkdir(parents=True,exist_ok=True)
    # Search concise subject/title terms instead of sending a full instruction prompt.
    subject=re.split(r'\s+[—–:-]\s+',job.get('title',job['prompt']))[0][:90].strip()
    queries=[subject]
    if subject and len(subject)>8:
        queries.append(subject+' military history')
    for scene in scenes[:3]:
        heading=str(scene.get('heading','')).strip()[:80]
        if heading and heading.lower()!=subject.lower():queries.append(heading)
    candidates=[];used_urls=set()
    for query in dict.fromkeys(queries):
        if len(candidates)>=min(12,len(scenes)):break
        try:
            found=commons_candidates(query,limit=min(7,len(scenes)),fetch=fetch)
        except (urllib.error.URLError,TimeoutError,OSError,ValueError):
            continue
        for item in found:
            if item['url'] not in used_urls:
                item['search_query']=query
                item['visual_type']='archival still (license and relevance unverified)'
                candidates.append(item);used_urls.add(item['url'])
                if len(candidates)>=min(12,len(scenes)):break
    credits=[]
    if fetch is None:fetch=urllib.request.urlopen
    for i,source in enumerate(candidates):
        url=source['url'];path=dest/f'commons_{i+1:02}.jpg'
        req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT})
        try:
            with fetch(req,timeout=25) as resp:
                typ=(resp.headers.get('Content-Type') or '').lower()
                if not typ.startswith(('image/jpeg','image/png','image/webp')):continue
                image=resp.read(8_000_001)
                if len(image)>8_000_000:continue
            from PIL import Image,ImageOps
            from io import BytesIO
            im=Image.open(BytesIO(image));im.verify()
            im=Image.open(BytesIO(image)).convert('RGB')
            im.thumbnail((1600,1600))
            im.save(path,format='JPEG',quality=87)
            scene_index=min(len(scenes)-1,round(i*len(scenes)/max(1,len(candidates))))
            if scene_index<len(scenes):
                scenes[scene_index]['visual']=str(path)
                scenes[scene_index]['visual_provenance']='Candidate archival still; review media_credits.json'
                source['scene']=scene_index+1;source['local_path']=str(path)
                credits.append(source)
        except (OSError,ValueError,urllib.error.URLError):continue
    sheet=dest/'media_credits.json'
    atomic_json(sheet,{'notice':'Review original source pages and restrictions. CC BY/CC BY-SA licenses may require attribution or share-alike. No automatic rights approval.',
                       'items':credits})
    return credits,sheet


def make_research_leads(topic: str, dest: Path, report:dict|None=None) -> Path:
    """Write search leads; these do not constitute evidence of a factual claim."""
    domains = ('history.navy.mil', 'archives.gov', 'history.defense.gov',
               'navalhistory.org', 'si.edu', 'loc.gov')
    leads = [{
        'site': domain,
        'search_url': 'https://www.google.com/search?' + urllib.parse.urlencode({
            'q': 'site:' + domain + ' ' + topic}),
        'verified': False,
        'status': 'SEARCH LEAD ONLY — review the original record before citation',
    } for domain in domains]
    atomic_json(dest, {
        'topic': topic,
        'notice': ('Search results are not evidence. Open each original source, '
                   'confirm provenance and context, and record exact supporting text.'),
        'leads': leads,
        'retrieved_sources':(report or {}).get('sources',[]),
        'retrieved_at':(report or {}).get('retrieved_at',''),
        'warnings':(report or {}).get('warnings',[]),
    })
    return dest


def create_story_companions(job:dict,main:dict,*,rewrite=None)->dict[str,str]:
    """Write independently fact-checkable manifests from the same full story."""
    variants={}
    outputs=job.get('deliverables') or ['full']
    if 'full' in outputs:
        variants['full']=str(EPISODES/(main['slug']+'.json'))
    for target in ('shorts','tiktok'):
        if target not in outputs:
            continue
        scenes=social_story(main['scenes'],target,rewrite=rewrite)
        originals=main['scenes']
        # Reuse original footage when appropriate, but never invent provenance.
        pointers=(0,len(originals)//2,len(originals)-1)
        for row,index in zip(scenes,pointers):
            source=originals[index]
            if source.get('visual'):
                row['visual']=source['visual']
            if source.get('visual_provenance'):
                row['visual_provenance']=source['visual_provenance']
        slug=main['slug']+'_'+target
        short=dict(main)
        short.update(slug=slug,
                     title=main['title']+(' — YouTube Short' if target=='shorts' else ' — TikTok'),
                     deliverable=target,approved=False,scenes=scenes,
                     review_notice='Condensed version. Verify historical context, all claims and rights independently.')
        path=EPISODES/(slug+'.json')
        atomic_json(path,short)
        from fact_checker import sync_report,save_report
        report=sync_report(slug,short['title'],
                           '\n\n'.join(x['narration'] for x in scenes))
        save_report(report)
        variants[target]=str(path)
    return variants


def _local_reenactments(job:dict,scenes:list[dict],progress=None)->int:
    """Optional, strictly local AI illustrative scenes. Fail open to archival stills."""
    if job.get('visual_style')!='ai_reenactment':
        return 0
    from update_engine import load_settings
    config=load_settings()
    workflow=config.get('comfyui_workflow','')
    if not workflow:
        if progress:progress('AI video not configured. Using archival media/title cards instead.')
        return 0
    from studio import LocalVideoError,generate_clip,build_reenactment_prompt,status
    try:
        status()
    except LocalVideoError as exc:
        if progress:progress(str(exc)+' Falling back to archival media.')
        return 0
    count=0
    # Long films use several short illustrative clips, never pretend 10 minutes
    # of continuous, authentic period footage was generated.
    indices=sorted(set((0,len(scenes)//2,max(0,len(scenes)-1))))
    for i in indices:
        scene=scenes[i]
        if progress:progress(f'AI reenactment {count+1}/{len(indices)}: {scene.get("heading","")}')
        output=MEDIA_DIR/job['id']/f'AI_REENACTMENT_{i+1:02}.mp4'
        try:
            clip=generate_clip(build_reenactment_prompt(
                str(scene.get('heading','')),job['prompt']),Path(workflow),output)
        except (LocalVideoError,urllib.error.URLError,OSError,ValueError) as exc:
            if progress:progress('AI clip skipped: '+str(exc)[:200])
            continue
        scene['visual']=str(clip)
        scene['visual_provenance']='AI-generated illustration — not actual historical footage'
        count+=1
    return count


def run_job(job_id:str, *,progress=None,script_generator=generate_scenes,media_fetcher=download_commons_images)->dict:
    job=get_job(job_id)
    if job['status']=='finished':raise ValueError('This job is already complete.')
    def emit(status,text,step=None):
        fields={'status':status,'progress':text}
        if step is not None:fields['current_step']=step
        change(job_id,**fields)
        if progress:progress(text)
    try:
        prepared_file=job.get('prepared_scenes_file','')
        research_report=None
        if not prepared_file and not job.get('notes_file') and script_generator is generate_scenes:
            emit('researching','Finding source leads from Wikipedia and the Library of Congress...',0)
            research_report=discover_research(job['prompt'])
            brief=research_brief(research_report)
            research_file=QUEUE/(job_id+'_automatic_research.txt')
            research_file.parent.mkdir(parents=True,exist_ok=True)
            research_file.write_text(brief,encoding='utf-8')
            job=change(job_id,notes_file=str(research_file),
                       research_source_count=len(research_report['sources']))
            if progress:
                progress(f"Research leads: {len(research_report['sources'])} retrieved. "
                         "Nothing is automatically verified.")
        emit('drafting','Writing an unverified documentary draft using source leads...',0)
        def update(i,n,text):emit('drafting',f'Scene {i}/{n}: {text}',i)
        if prepared_file:
            prepared_path=Path(prepared_file).resolve()
            if prepared_path.parent!=QUEUE.resolve() or prepared_path.name!=job_id+'_prepared.json':
                raise ValueError('Prepared script path must remain inside this job queue.')
            scenes=json.loads(prepared_path.read_text(encoding='utf-8'))['scenes']
            if not isinstance(scenes,list) or not scenes:
                raise ValueError('Prepared script has no scenes.')
            if progress:progress('Using the ChatGPT-prepared script; no Ollama draft needed.')
        else:
            scenes=script_generator(job,complete=update)
        job=get_job(job_id)
        credits=[];credit_path=''
        if job['auto_media']:
            emit('gathering_media','Searching Wikimedia Commons for reusable historical images...')
            try:
                credits,source_path=media_fetcher(job,scenes)
                credit_path=str(source_path)
            except (urllib.error.URLError,TimeoutError,OSError,ValueError,RuntimeError) as exc:
                if progress:progress('Image lookup unavailable. Using title cards: '+str(exc)[:250])
        # Video generation is deliberately deferred until AFTER human
        # factual clearance and final render approval.
        title=job['title'].strip();slug=slugify(title)+'_'+job_id[:6]
        research_leads=make_research_leads(job['prompt'],
                                           MEDIA_DIR/job_id/'research_leads.json',
                                           report=research_report)
        manifest={'slug':slug,'title':title,'description':'Independent, unofficial military documentary. Research and fact checking required before publication.',
                'approved':False,'sources':[],'visual_style':job.get('visual_style','archival'),
                'media_sources':[x.get('page_url','') for x in credits if x.get('page_url')],
                'review_notice':'AI generated UNVERIFIED script; check every factual assertion and media license before final render.',
                'production_job':job_id,'narrator':{'voice':job['voice']},'scenes':scenes}
        manifest['deliverable']='full'
        path=EPISODES/(slug+'.json');atomic_json(path,manifest)
        from fact_checker import sync_report,save_report
        report=sync_report(slug,title,'\n\n'.join(s['narration'] for s in scenes));save_report(report)
        variants=create_story_companions(
            job,manifest,rewrite=lambda prompt,target:
                ollama_generate(job['model'],prompt,
                                predict=380 if target=='shorts' else 500))
        if not variants:raise ValueError('No video outputs were selected.')
        primary=variants.get('full') or next(iter(variants.values()))
        words=sum(len(s['narration'].split()) for s in scenes)
        estimate=round(words/125,1)
        result=change(job_id,status='awaiting_review',
                     progress=f'{len(variants)} drafts: {", ".join(variants)}. Review each for factual and media accuracy.',
                     manifest=primary,variants=variants,media_credits=credit_path,
                     research_leads=str(research_leads),script_words=words,error='')
        if progress:progress(result['progress'])
        return result
    except Exception as exc:
        msg=str(exc)
        status='needs_model' if 'ollama' in msg.lower() or 'model' in msg.lower() else 'failed'
        change(job_id,status=status,error=msg,progress=msg[:250])
        raise


def prepare_for_render(job_id:str, *,rights_confirmed:bool=False,deliverable:str|None=None)->Path:
    """Human consent and source-led fact check required to release publishable rendering."""
    job=get_job(job_id)
    if job['status'] not in ('awaiting_review','ready','finished'):
        raise ValueError('The production draft is not ready for review.')
    if not rights_confirmed:raise ValueError('Confirm asset rights and attribution after reviewing media_credits.json.')
    variants=job.get('variants') or {}
    if deliverable is not None:
        if deliverable not in variants:
            raise ValueError('This job has no output named '+str(deliverable))
        path=Path(variants[deliverable])
    else:
        path=Path(job['manifest'])
    data=json.loads(path.read_text(encoding='utf-8'))
    from fact_checker import require_clearance
    require_clearance(data['slug'],'\n\n'.join(s['narration'] for s in data['scenes']))
    data['approved']=True;atomic_json(path,data)
    reviewed=dict(job.get('variant_reviews') or {})
    reviewed[data.get('deliverable','full')]=True
    change(job_id,status='ready',variant_reviews=reviewed,
           progress='Source checks and media rights confirmed for '+data.get('deliverable','full')+'. Ready to render.')
    return path


def render_ready(job_id:str,*,rights_confirmed=False,render_fn=None,deliverable=None)->list[Path]:
    manifest=prepare_for_render(job_id,rights_confirmed=rights_confirmed,deliverable=deliverable)
    job=get_job(job_id)
    if render_fn is None:
        from studio import render as render_fn
    data=json.loads(manifest.read_text(encoding='utf-8'))
    kind=data.get('deliverable','full')
    fmts=['wide'] if kind=='full' else ['short']
    change(job_id,status='rendering',progress='Rendering '+','.join(fmts))
    try:
        outputs=[render_fn(manifest,fmt,voice_model=job['voice']) for fmt in fmts]
        change(job_id,status='finished',progress='Rendered: '+', '.join(p.name for p in outputs))
        return outputs
    except Exception as exc:
        change(job_id,status='failed',error=str(exc),progress='Render failed; retry after fixing: '+str(exc)[:200])
        raise


def main():
    parser=argparse.ArgumentParser(description='The Crow\'s Nest prompt-to-video production queue')
    sub=parser.add_subparsers(dest='command',required=True)
    add=sub.add_parser('add');add.add_argument('prompt');add.add_argument('--minutes',type=int,default=5)
    add.add_argument('--format',choices=FORMATS,default='wide');add.add_argument('--model',default='qwen3:8b')
    add.add_argument('--voice',default='kokoro:am_onyx');add.add_argument('--notes-file',default='')
    add.add_argument('--no-media',action='store_true')
    sub.add_parser('list')
    run=sub.add_parser('run');run.add_argument('job_id')
    opts=parser.parse_args()
    if opts.command=='add':print(json.dumps(create_job(opts.prompt,minutes=opts.minutes,fmt=opts.format,model=opts.model,
                              voice=opts.voice,notes_file=opts.notes_file,auto_media=not opts.no_media),indent=2))
    elif opts.command=='list':print(json.dumps(list_jobs(),indent=2))
    elif opts.command=='run':run_job(opts.job_id,progress=lambda s:print(s,flush=True))

if __name__=='__main__':main()
