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
    if words<24:
        raise ValueError("Insufficient source narrative to make an accurate short")
    remainder=[sentences[i] for i in sorted(set(choices)-{hook})]
    split=max(1,len(remainder)//2)
    chapters=(("The Hook",sentences[hook]),
              ("The Stakes"," ".join(remainder[:split])),
              ("The Payoff"," ".join(remainder[split:])))
    return [{"heading":heading,"narration":text} for heading,text in chapters if text.strip()]


def available_outputs(formats):
    values=("full","shorts","tiktok")
    if not isinstance(formats,(list,tuple)) or not formats:
        raise ValueError("Choose at least one video output")
    if len(set(formats))!=len(formats) or not set(formats).issubset(values):
        raise ValueError("Unknown or duplicate output")
    return list(formats)
