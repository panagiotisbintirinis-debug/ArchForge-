"""Install only the core assets referenced by the accompanying S03 project.

Existing files are preserved. This does not open or modify any project.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


def main():
    source=Path(__file__).resolve().parent/'library_assets'
    if os.environ.get('ARCHFORGE_DATA'):
        data=Path(os.environ['ARCHFORGE_DATA'])
    elif sys.platform.startswith('win'):
        data=Path(os.environ.get('APPDATA',str(Path.home())))/'ArchForge'
    else:
        data=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'ArchForge'
    destination=data/'library/assets'
    records=[]
    for path in sorted(source.glob('*.json')):
        record=json.loads(path.read_text(encoding='utf-8'))
        digest=hashlib.sha1(json.dumps([record['vertices'],record['triangles']]).encode()).hexdigest()[:16]
        if record['id']!='a'+digest or path.name!=record['id']+'.json':
            raise ValueError(f'Asset identity check failed: {path.name}')
        records.append(path)
    if not records:
        raise ValueError('No packaged assets found')
    destination.mkdir(parents=True,exist_ok=True)
    for path in records:
        target=destination/path.name
        if target.exists():
            print('Preserved existing:',path.name)
        else:
            shutil.copyfile(path,target)
            print('Installed:',path.name)
    print('Done. Open the S03 .archforge project in ArchForge.')


if __name__=='__main__':main()
