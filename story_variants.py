"""Evidence-preserving short-form adaptation from a longer documentary.

Every sentence is taken verbatim from the long-form script. No extra historical
claims, invented quotes, or implied source verification.
"""
from __future__ import annotations
import re

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
