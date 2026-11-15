#!/usr/bin/env python3
"""Source-led factual review gate for The Crow's Nest Studio.

This tool does NOT claim to prove statements by lexical overlap or by an LLM.
It extracts claims, prioritizes fact-checking, tracks independent source evidence,
and blocks publication while a factual claim remains unsupported, contradicted,
or changed since review. Human signoff is required for each claim.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / 'episodes' / 'fact_checks'
STATUSES = ('unreviewed', 'supported', 'disputed', 'needs_correction', 'nonfactual')
ABSOLUTE = re.compile(r'\b(always|never|only|first|last|all|none|every|earliest|largest|smallest|most|least|completely)\b', re.I)
DATES = re.compile(r'\b(?:1[5-9]\d{2}|20\d{2}|21\d{2}|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))\b', re.I)
NUMBERS = re.compile(r'\b\d+(?:[.,]\d+)?\s*(?:%|percent|years?|months?|days?|ships?|soldiers?|sailors?|people|miles?|kilometers?|tons?|feet|casualties|dollars?)\b', re.I)
CAUSAL = re.compile(r'\b(because|caused|resulted in|led to|responsible for|due to)\b', re.I)
SENSITIVE = re.compile(r'\b(killed|casualties|battle|war|attack|operation|deployment|government|military|Navy|Army|Marine|Air Force|Space Force|Coast Guard)\b', re.I)


def clean_sentence(s: str) -> str:
    return ' '.join(s.strip().split())


def get_claims(script: str) -> list[dict]:
    lines = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9“"\(])|\n\s*\n+', script.strip())
    claims=[]
    for line in lines:
        text=clean_sentence(line)
        if len(text)<5:continue
        ident=hashlib.sha256(text.casefold().encode('utf-8')).hexdigest()[:18]
        flags=[]
        if DATES.search(text):flags.append('date')
        if NUMBERS.search(text):flags.append('quantity')
        if ABSOLUTE.search(text):flags.append('absolute claim')
        if CAUSAL.search(text):flags.append('causation')
        if SENSITIVE.search(text):flags.append('military/history')
        claims.append({'id':ident,'text':text,'flags':flags,'priority':'high' if len(flags)>=2 or ('date' in flags or 'quantity' in flags) else 'normal'})
    # Collapse identical script claims to one check; they will have the same underlying evidence.
    return list({c['id']:c for c in claims}.values())


def report_path(slug: str, root: Path=ROOT) -> Path:
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,80}', slug):
        raise ValueError('Unsafe project slug')
    return root/'episodes'/'fact_checks'/f'{slug}.json'


def safe_url(url: str) -> bool:
    try:
        p=urllib.parse.urlsplit(url.strip())
        host=(p.hostname or '').lower()
        return (p.scheme=='https' and bool(host) and '.' in host and
                not host.endswith(('.local','.internal','.test')) and
                not host.endswith(('.localhost','.lan')) and
                host not in {'localhost','metadata.google.internal'} and
                p.username is None and p.password is None and p.port in (None,443) and
                len(url)<=2000 and not re.match(r'^(127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|0\.|[0-9.]+$)',host))
    except ValueError:
        return False


def source_tier(url: str) -> str:
    if not safe_url(url): return 'invalid link'
    domain=(urllib.parse.urlsplit(url).hostname or '').lower()
    if domain.endswith(('.mil','.gov')):return 'government / official (verify context)'
    if domain.endswith('.edu'):return 'academic (verify authorship)'
    if 'wikipedia.org' in domain:return 'encyclopedia / starting point'
    return 'other source (verify independence)'


def sync_report(slug: str, title: str, script: str, root: Path=ROOT) -> dict:
    path=report_path(slug,root)
    try:
        previous=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):previous={}
    old={c.get('id'):c for c in previous.get('claims',[]) if isinstance(c,dict)}
    rows=[]
    for claim in get_claims(script):
        prior=old.get(claim['id'],{})
        rows.append({**claim,
                     'status':prior.get('status','unreviewed') if prior.get('status') in STATUSES else 'unreviewed',
                     'source_url':prior.get('source_url',''),
                     'source_quote':prior.get('source_quote',''),
                     'review_notes':prior.get('review_notes',''),
                     'reviewer_confirmed':bool(prior.get('reviewer_confirmed',False)),
                     'reviewed_at':prior.get('reviewed_at',''),
                    })
    return {'schema':1,'slug':slug,'title':title,'claims':rows,
            'last_scanned':datetime.now(timezone.utc).isoformat(timespec='seconds')}


def save_report(report:dict,root:Path=ROOT) -> Path:
    path=report_path(report['slug'],root)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return path


def numbers_covered(claim: str, quote: str) -> bool:
    numbers=set(re.findall(r'(?<![A-Za-z0-9])\d+(?:[.,]\d+)*(?![A-Za-z0-9])',claim))
    quote_numbers=set(re.findall(r'(?<![A-Za-z0-9])\d+(?:[.,]\d+)*(?![A-Za-z0-9])',quote))
    return numbers.issubset(quote_numbers)


def mark_claim(row:dict, *, status:str, source_url:str='',source_quote:str='',review_notes:str='',
               reviewer_confirmed:bool=False) -> None:
    if status not in STATUSES:raise ValueError('Unknown fact-check status')
    if status=='supported':
        if not safe_url(source_url):raise ValueError('Supported claims require a valid HTTPS source URL.')
        if len(source_quote.strip())<15:raise ValueError('Paste a specific supporting excerpt (15+ characters).')
        if not reviewer_confirmed:raise ValueError('Confirm you personally compared the source with the claim.')
        if not numbers_covered(row['text'],source_quote):
            raise ValueError('The supporting excerpt must explicitly contain the dates/numbers stated in this claim.')
    elif status=='nonfactual':
        if any(flag in row.get('flags',[]) for flag in ('date','quantity')):
            raise ValueError('Statements containing dates or quantities cannot be exempted as purely editorial.')
        if len(review_notes.strip())<12 or not reviewer_confirmed:
            raise ValueError('To exempt an editorial statement, explain why and confirm your review.')
    row.update(status=status,source_url=source_url.strip(),source_quote=source_quote.strip(),
               review_notes=review_notes.strip(),reviewer_confirmed=bool(reviewer_confirmed),
               reviewed_at=datetime.now(timezone.utc).isoformat(timespec='seconds') if reviewer_confirmed else '')


def status_summary(report:dict) -> tuple[int,int,int]:
    rows=report.get('claims',[])
    ready=sum(1 for row in rows if row_ready(row))
    return ready,len(rows),len(rows)-ready


def row_ready(row:dict)->bool:
    if not row.get('reviewer_confirmed'):return False
    if row.get('status')=='nonfactual':return len(row.get('review_notes','').strip())>=12
    return (row.get('status')=='supported' and safe_url(row.get('source_url',''))
            and len(row.get('source_quote','').strip())>=15
            and numbers_covered(row.get('text',''),row.get('source_quote','')))


def require_clearance(slug:str,script:str,root:Path=ROOT) -> Path:
    path=report_path(slug,root)
    if not path.is_file():raise ValueError('Fact-check report missing. Use FACT CHECK in the editor before publication.')
    saved=json.loads(path.read_text(encoding='utf-8'))
    current=sync_report(slug,saved.get('title',''),script,root)
    ready,total,unresolved=status_summary(current)
    if total==0:raise ValueError('No factual or editorial statements found for review.')
    if unresolved:
        raise ValueError(f'Fact check: {ready}/{total} cleared; {unresolved} unresolved or changed. Open FACT CHECK and review each claim.')
    return path


def report_markdown(report:dict)->str:
    ready,total,unresolved=status_summary(report)
    out=[f"# Fact Check — {report.get('title','Untitled')}", '',
         f'Cleared: {ready}/{total}; unresolved: {unresolved}',
         'This records human review and traceable evidence, not an independent guarantee of truth.', '']
    for i,row in enumerate(report.get('claims',[]),1):
        out.extend([f"## {i}. {row['text']}",
            f"- Status: {row['status']} ({'cleared' if row_ready(row) else 'NOT CLEARED'})",
            f"- Risk flags: {', '.join(row.get('flags',[])) or 'general historical claim'}",
            f"- Source: {row.get('source_url','not supplied') or 'not supplied'}",
            f"- Excerpt: {row.get('source_quote','') or 'not supplied'}",
            f"- Notes: {row.get('review_notes','')}",
            f"- Reviewed: {row.get('reviewed_at','')}",''])
    return '\n'.join(out)


def research_url(claim:str,site:str='official')->str:
    site_filter=('site:history.navy.mil OR site:archives.gov OR site:history.defense.gov'
                 if site=='official' else '')
    q=f'{claim[:180]} {site_filter}'.strip()
    return 'https://www.google.com/search?q='+urllib.parse.quote(q)


def wiki_candidates(claim:str,fetch=None)->list[dict]:
    """Return Wikipedia research leads (not verified evidence).
    Safe to omit if offline / network unavailable; never marks a claim supported.
    """
    if fetch is None:fetch=urllib.request.urlopen
    keywords=re.findall(r"[A-Za-z0-9'-]+",claim)[:13]
    url='https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode({
        'action':'query','list':'search','srsearch':' '.join(keywords),
        'srlimit':'5','format':'json','utf8':'1'})
    req=urllib.request.Request(url,headers={'User-Agent':'TheCrowsNestStudio/2.0 (research support; independent project)','Accept':'application/json'})
    with fetch(req,timeout=10) as response:
        b=response.read(180001)
    if len(b)>180000:raise ValueError('Research results too large.')
    raw=json.loads(b.decode('utf-8'))
    out=[]
    for row in raw.get('query',{}).get('search',[]):
        title=html.unescape(row.get('title',''))
        snippet=html.unescape(re.sub('<[^>]*>','',row.get('snippet','')))
        out.append({'title':title,'snippet':snippet,'url':'https://en.wikipedia.org/wiki/'+urllib.parse.quote(title.replace(' ','_'))})
    return out


def main():
    parser=argparse.ArgumentParser(description='Source-led fact check for a Crow\'s Nest episode')
    parser.add_argument('episode',type=Path)
    parser.add_argument('--report',action='store_true',help='Print summary and evidence audit report')
    args=parser.parse_args()
    episode=json.loads(args.episode.read_text(encoding='utf-8'))
    script='\n\n'.join(s.get('narration','') for s in episode['scenes'])
    report=sync_report(episode['slug'],episode.get('title',''),script)
    if not args.report:save_report(report)
    print(report_markdown(report))

if __name__=='__main__':main()
