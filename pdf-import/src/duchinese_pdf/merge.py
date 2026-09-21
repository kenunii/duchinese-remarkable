"""Combine completed, non-overlapping ranges of the same PDF without new API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from .prepare import write_json


def merge_batches(inputs, output):
    if output.exists():raise ValueError('Output already exists; choose a new collection directory')
    manifests=[json.loads((root/'manifest.json').read_text()) for root in inputs]
    if any(m['status']!='completed' for m in manifests):raise ValueError('Every input batch must be complete')
    if len({m['pdf_sha256'] for m in manifests})!=1:raise ValueError('Input batches belong to different PDFs')
    if len({m['dpi'] for m in manifests})!=1:raise ValueError('Input batches use different render resolution')
    records=sorted([(entry,root,m) for root,m in zip(inputs,manifests) for entry in m['pages']],key=lambda item:item[0]['page'])
    numbers=[entry['page'] for entry,_,_ in records]
    if not numbers or numbers!=list(range(numbers[0],numbers[-1]+1)):raise ValueError('Page ranges overlap or have gaps')
    # Verify all inputs before copying or publishing a new manifest.
    for entry,root,m in records:
        if entry['status'] not in ('validated','image-only'):raise ValueError('Input contains unfinished page')
        image=root/entry['image']
        if hashlib.sha256(image.read_bytes()).hexdigest()!=m['image_hashes'][str(entry['page'])]:raise ValueError('Input image hash mismatch')
        book=json.loads((root/entry['book']).read_text())
        if book['source_page']!=entry['page']:raise ValueError('Incorrect book page number')
    output.mkdir(parents=True)
    (output/'images').mkdir();(output/'pages').mkdir();(output/'ocr').mkdir()
    entries=[];hashes={}
    for entry,root,m in records:
        n=entry['page'];stem=f'page-{n:03d}'
        image=output/'images'/(stem+'.png');shutil.copy2(root/entry['image'],image)
        # Retain audit/request/response files, including documented interrupted attempts.
        shutil.copytree(root/'pages'/f'{n:03d}',output/'pages'/f'{n:03d}')
        shutil.copytree(root/'ocr'/stem,output/'ocr'/stem)
        copied=dict(entry,image=f'images/{stem}.png',book=f'pages/{n:03d}/book.json')
        entries.append(copied);hashes[str(n)]=m['image_hashes'][str(n)]
    manifest=dict(manifests[0],title='Contemporary Chinese 4',first_page=numbers[0],last_page=numbers[-1],pages=entries,image_hashes=hashes,
                  source_batches=[str(root.resolve()) for root in inputs],status='completed')
    # These fields describe the individual execution, not the merged collection.
    for key in ['ocr_exit_code','ocr_completed_pages','recovery_note']:manifest.pop(key,None)
    write_json(output/'manifest.json',manifest)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path);p.add_argument('inputs',nargs='+',type=Path)
    a=p.parse_args()
    try:m=merge_batches(a.inputs,a.output)
    except (ValueError,OSError,KeyError) as exc:p.exit(1,str(exc)+'\n')
    print(f"Merged PDF pages {m['first_page']}–{m['last_page']}")

if __name__=='__main__':main()
