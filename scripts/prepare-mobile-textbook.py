#!/usr/bin/env python3
"""Bundle an existing validated textbook collection; never invoke OCR or an LLM."""
import argparse
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pdf-import/src'))
from duchinese_pdf.collection import load_collection

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('collection',type=Path)
p.add_argument('--output',type=Path,default=Path('mobile/composeApp/src/commonMain/composeResources/files/textbook'))
a=p.parse_args()
m,prepared=load_collection(a.collection)
a.output.mkdir(parents=True,exist_ok=True)
pages=[]
for entry,book in zip(m['pages'],prepared):
    shutil.copyfile(a.collection/entry['image'],a.output/book['image_file'])
    pages.append({k:book[k] for k in ('source_page','image_width','image_height','words','sentences','image_file','view')})
(a.output/'book.json').write_text(json.dumps({'id':m['pdf_sha256'],'title':'Contemporary Chinese 4','pages':pages},ensure_ascii=False))
print(f'Bundled {len(pages)} original pages, {sum(len(p["words"]) for p in pages)} word tokens. No API calls.')
