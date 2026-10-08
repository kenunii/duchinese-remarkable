#!/usr/bin/env python3
"""Package validated batch pages as local QML reader data, preserving originals."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pdf-import/src'))
from duchinese_pdf.collection import load_collection
root=Path(sys.argv[1]);out=Path(sys.argv[2])
m,pages=load_collection(root)
out.mkdir(parents=True,exist_ok=True)
for entry,book in zip(m['pages'],pages):
    shutil.copyfile(root/entry['image'],out/book['image_file'])
(out/'Book.js').write_text('.pragma library\nvar id = '+json.dumps(m['pdf_sha256'])+';\nvar pages = '+json.dumps(pages,ensure_ascii=False)+';\nvar book = pages[0];\n')
(out/'page-views.json').write_text(json.dumps([{'page':p['source_page'],'view':p['view'],'size':[p['image_width'],p['image_height']]} for p in pages],indent=2)+'\n')
print(f'Packaged {len(pages)} pages')
