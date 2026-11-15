#!/usr/bin/env python3
"""Builds a code-only update asset suitable for a GitHub Release.
Run once for each new version, then upload the resulting ZIP to a verified
Crow's Nest GitHub release with the matching vX.Y.Z tag.
"""
from __future__ import annotations
import hashlib
import sys
import zipfile
from pathlib import Path
from update_engine import ALLOWED_CODE, REQUIRED_CODE, VERSION, validate_archive
ROOT=Path(__file__).resolve().parent

def build(destination:Path|None=None)->Path:
    name=f'Crows_Nest_Studio_Update_v{VERSION}.zip'
    out=destination or ROOT/name
    files=[ROOT/n for n in sorted(ALLOWED_CODE) if (ROOT/n).is_file()]
    files+=sorted(p for p in (ROOT/'assets'/'branding').rglob('*') if p.is_file())
    files=list(dict.fromkeys(files))
    names={p.relative_to(ROOT).as_posix() for p in files}
    if not REQUIRED_CODE.issubset(names):raise ValueError('A required program file is missing.')
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in files:z.write(f,f.relative_to(ROOT).as_posix())
    validate_archive(out,VERSION)
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    print(f'Built {out}\nSHA-256: {digest}\nTag: v{VERSION}')
    return out

if __name__=='__main__':build(Path(sys.argv[1]) if len(sys.argv)>1 else None)
