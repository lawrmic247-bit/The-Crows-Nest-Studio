"""Optional local Qwen3-TTS voice cloning and prompt-designed character voice.

Qwen weights are downloaded to Hugging Face's model cache only when first used.
A GPU with substantial VRAM is strongly recommended. CPU inference can be slow.
This module never sends voice files to a hosted inference API.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from voice_profiles import get_profile,get_audio,create_profile,DEFAULT_ACTING

CLONE_MODEL = 'Qwen/Qwen3-TTS-12Hz-0.6B-Base'
DESIGN_MODEL = 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign'
DESIGN_SCRIPT = ("From first light to the last watch, there is always a story worth telling. "
                 "This is The Crow's Nest, where history has a voice.")


def load_model(model_id:str):
    try:
        import torch
        from qwen_tts import Qwen3TTSModel
    except ImportError as e:
        raise RuntimeError('Qwen3 is optional. Install it in the studio private Python environment: pip install qwen-tts soundfile torch') from e
    device='cuda:0' if torch.cuda.is_available() else 'cpu'
    dtype=torch.bfloat16 if device.startswith('cuda') and torch.cuda.is_bf16_supported() else torch.float32
    print(f'Loading {model_id} on {device} (first use may download several GB)...',flush=True)
    return Qwen3TTSModel.from_pretrained(model_id,device_map=device,dtype=dtype)


def clone(profile_id:str,text:str,dest:Path, *, reference_is_cleaned:bool=False,model=None):
    if not text.strip():raise ValueError('Narration text must not be empty.')
    prof=get_profile(profile_id)
    if not prof.get('consent_confirmed'):
        raise PermissionError('Consent confirmation is required before cloning.')
    ref=get_audio(profile_id,'cleaned' if reference_is_cleaned else 'reference')
    transcript=prof.get('transcript','').strip()
    # The Qwen Base model accepts a reference clip + its exact transcript.
    # Acting notes are stored with the profile; this API does not accept a
    # separate delivery-instruction argument for generate_voice_clone.
    if model is None:model=load_model(CLONE_MODEL)
    kwargs={'text':text,'language':'English','ref_audio':str(ref),
            'x_vector_only_mode':not bool(transcript)}
    if transcript:kwargs['ref_text']=transcript
    # Apply the same user pronunciation guide for direct Voice Studio previews.
    from narration import normalize_for_speech
    kwargs['text']=normalize_for_speech(kwargs['text'])
    wavs,sr=model.generate_voice_clone(**kwargs)
    import soundfile as sf
    dest.parent.mkdir(parents=True,exist_ok=True)
    sf.write(str(dest),wavs[0],sr,subtype='PCM_16')
    print('VOICE CLONE AUDIO:',dest,flush=True)
    return dest


def design(name:str,prompt:str,dest:Path):
    if len(prompt.strip())<15: raise ValueError('Give a detailed character voice description.')
    model=load_model(DESIGN_MODEL)
    wavs,sr=model.generate_voice_design(text=DESIGN_SCRIPT,language='English',instruct=prompt.strip())
    import soundfile as sf
    dest.parent.mkdir(parents=True,exist_ok=True)
    sf.write(str(dest),wavs[0],sr,subtype='PCM_16')
    # AI-generated reference clip, not a real person, but still mark voice provenance.
    prof=create_profile(name,dest,transcript=DESIGN_SCRIPT,direction=prompt,consent=True,own_voice=False)
    print('DESIGNED VOICE PROFILE:',prof['profile_id'],flush=True)
    return prof


def main():
    a=argparse.ArgumentParser()
    s=a.add_subparsers(dest='command',required=True)
    c=s.add_parser('clone');c.add_argument('--profile',required=True);c.add_argument('--text',required=True);c.add_argument('--output',required=True)
    d=s.add_parser('design');d.add_argument('--name',required=True);d.add_argument('--prompt',required=True);d.add_argument('--output',required=True)
    x=a.parse_args()
    if x.command=='clone':clone(x.profile,x.text,Path(x.output))
    else:design(x.name,x.prompt,Path(x.output))

if __name__=='__main__':
    try:main()
    except Exception as e:print('ERROR:',e,file=sys.stderr);sys.exit(1)
