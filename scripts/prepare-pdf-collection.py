#!/usr/bin/env python3
"""Package validated batch pages as local QML reader data, preserving originals."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pdf-import/src'))
from PIL import Image
from duchinese_pdf.page_view import content_view
root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
m=json.loads((root/'manifest.json').read_text())
if m['status']!='completed':raise ValueError('Batch is not complete')
pages=[]
for entry in m['pages']:
    if entry['status'] not in ('validated','image-only'):raise ValueError('Unvalidated page')
    image=root/entry['image'];number=entry['page']
    if hashlib.sha256(image.read_bytes()).hexdigest()!=m['image_hashes'][str(number)]:raise ValueError('Image hash mismatch')
    book=json.loads((root/entry['book']).read_text())
    if book['source_page']!=number:raise ValueError('Wrong page data')
    name=f'page-{number:03d}.png';shutil.copyfile(image,out/name)
    boxes=[box for word in book['words'] for box in word['boxes']]
    raw_path=root/'ocr'/image.stem/(image.stem+'_res.json')
    if raw_path.exists():
        raw=json.loads(raw_path.read_text());raw=raw.get('res',raw)
        boxes += [[x0,y0,x1-x0,y1-y0] for x0,y0,x1,y1 in raw.get('rec_boxes',[])]
    with Image.open(image) as raster:book['view']=content_view(raster,boxes)
    book['image_file']=name;pages.append(book)
if [p['source_page'] for p in pages]!=list(range(m['first_page'],m['last_page']+1)):raise ValueError('Missing or reordered pages')
(out/'Book.js').write_text('.pragma library\nvar id = '+json.dumps(m['pdf_sha256'])+';\nvar pages = '+json.dumps(pages,ensure_ascii=False)+';\nvar book = pages[0];\n')
(out/'page-views.json').write_text(json.dumps([{'page':p['source_page'],'view':p['view'],'size':[p['image_width'],p['image_height']]} for p in pages],indent=2)+'\n')
print(f'Packaged {len(pages)} pages')
