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
VISUAL_STYLES = ('archival','motion','hybrid')
JOB_SCHEMA = 'crowsnest.job.v1'
STATUSES = ('queued','drafting','gathering_media','awaiting_review','ready','rendering','finished','needs_model','failed')
MAX_NOTES = 20000
USER_AGENT = 'CrowsNestStudio/4.0 (+local documentary editor; contact via Wikimedia Commons)'


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
               visual_style:str='archival') -> dict:
    prompt=' '.join(prompt.strip().split())
    if not 12<=len(prompt)<=3000:raise ValueError('Prompt must contain 12–3000 characters.')
    if not 1<=int(minutes)<=30:raise ValueError('Duration must be 1–30 minutes.')
    if fmt not in FORMATS:raise ValueError('Choose short, wide, or both.')
    if visual_style not in VISUAL_STYLES:raise ValueError('Choose archival, motion, or hybrid visual style.')
    if not re.fullmatch(r'[\w.:-]{2,100}',model):raise ValueError('Invalid local model name.')
    if notes_file and (not Path(notes_file).is_file() or Path(notes_file).stat().st_size>512_000):
        raise ValueError('Research notes must be an existing plain-text file under 500 KB.')
    ident=uuid.uuid4().hex[:12]
    job={'id':ident,'prompt':prompt,'title':prompt[:95],'minutes':int(minutes),'format':fmt,
         'model':model,'voice':voice,'notes_file':notes_file,'auto_media':bool(auto_media),
          'visual_style':visual_style,
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
    allowed={'schema','topic','title','minutes','format','visual_style','voice','auto_media','research_notes','script','scenes'}
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
                   auto_media=raw.get('auto_media',True))
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


def make_research_leads(topic: str, dest: Path) -> Path:
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
    })
    return dest


def run_job(job_id:str, *,progress=None,script_generator=generate_scenes,media_fetcher=download_commons_images)->dict:
    job=get_job(job_id)
    if job['status']=='finished':raise ValueError('This job is already complete.')
    def emit(status,text,step=None):
        fields={'status':status,'progress':text}
        if step is not None:fields['current_step']=step
        change(job_id,**fields)
        if progress:progress(text)
    try:
        emit('drafting','Writing an unverified script with local Ollama...',0)
        def update(i,n,text):emit('drafting',f'Scene {i}/{n}: {text}',i)
        prepared_file=job.get('prepared_scenes_file','')
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
        title=job['title'].strip();slug=slugify(title)+'_'+job_id[:6]
        research_leads=make_research_leads(job['prompt'],MEDIA_DIR/job_id/'research_leads.json')
        manifest={'slug':slug,'title':title,'description':'Independent, unofficial military documentary. Research and fact checking required before publication.',
                'approved':False,'sources':[],'visual_style':job.get('visual_style','archival'),
                'media_sources':[x.get('page_url','') for x in credits if x.get('page_url')],
                'review_notice':'AI generated UNVERIFIED script; check every factual assertion and media license before final render.',
                'production_job':job_id,'narrator':{'voice':job['voice']},'scenes':scenes}
        path=EPISODES/(slug+'.json');atomic_json(path,manifest)
        from fact_checker import sync_report,save_report
        report=sync_report(slug,title,'\n\n'.join(s['narration'] for s in scenes));save_report(report)
        words=sum(len(s['narration'].split()) for s in scenes)
        # If output is short, disclose the actual estimate rather than assert the requested duration was achieved.
        estimate=round(words/125,1)
        result=change(job_id,status='awaiting_review',progress=f'Draft ready: {len(scenes)} scenes, {words} words (~{estimate} min). Fact check and media review required.',
                  manifest=str(path),media_credits=credit_path,research_leads=str(research_leads),script_words=words,error='')
        if progress:progress(result['progress'])
        return result
    except Exception as exc:
        msg=str(exc)
        status='needs_model' if 'ollama' in msg.lower() or 'model' in msg.lower() else 'failed'
        change(job_id,status=status,error=msg,progress=msg[:250])
        raise


def prepare_for_render(job_id:str, *,rights_confirmed:bool=False)->Path:
    """Human consent and source-led fact check required to release publishable rendering."""
    job=get_job(job_id)
    if job['status'] not in ('awaiting_review','ready','finished'):
        raise ValueError('The production draft is not ready for review.')
    if not rights_confirmed:raise ValueError('Confirm asset rights and attribution after reviewing media_credits.json.')
    path=Path(job['manifest']);data=json.loads(path.read_text(encoding='utf-8'))
    from fact_checker import require_clearance
    require_clearance(data['slug'],'\n\n'.join(s['narration'] for s in data['scenes']))
    data['approved']=True;atomic_json(path,data)
    change(job_id,status='ready',progress='Fact checks and media rights confirmed. Ready to narrate and render.')
    return path


def render_ready(job_id:str,*,rights_confirmed=False,render_fn=None)->list[Path]:
    manifest=prepare_for_render(job_id,rights_confirmed=rights_confirmed)
    job=get_job(job_id)
    if render_fn is None:
        from studio import render as render_fn
    fmts=['short','wide'] if job['format']=='both' else [job['format']]
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
