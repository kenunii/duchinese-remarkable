"""Explicitly regenerate selected rejected pages once, retaining every prior attempt."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from .annotate import make_deepseek_request, read_api_key, run
from .assemble import assemble
from .prepare import write_json


def retry_pages(root, numbers, workers=2):
    if workers < 1: raise ValueError('Workers must be positive')
    manifest=json.loads((root/'manifest.json').read_text())
    if manifest['status'] not in ('completed','completed-with-errors'):raise ValueError('Wait for the original batch to finish')
    entries={r['page']:r for r in manifest['pages']}
    numbers=list(dict.fromkeys(numbers))
    for n in numbers:
        if n not in entries or entries[n]['status']!='failed':raise ValueError(f'Page {n} is not failed')
        page=root/'pages'/f'{n:03d}'
        if (page/'annotation-retry-1').exists():raise ValueError(f'Page {n} already has an explicit retry; inspect it first')
        source=json.loads((page/'source.json').read_text())
        if make_deepseek_request(source)!=json.loads((page/'annotation/request.json').read_text()):raise ValueError('Retry settings differ from original request')
    backup=root/'manifest-before-explicit-retry.json'
    if backup.exists():raise ValueError('An explicit retry batch already exists')
    write_json(backup,manifest)
    def process(n):
        page=root/'pages'/f'{n:03d}';attempt=page/'annotation-retry-1'
        source=json.loads((page/'source.json').read_text());record=dict(entries[n])
        record.update(annotation=str(attempt.relative_to(root)),previous_annotation=f'pages/{n:03d}/annotation')
        try:
            meta=run(source,attempt)
            corrected=json.loads((attempt/'result/characters.json').read_text())
            annotations=json.loads((attempt/'result/annotations.json').read_text())
            book=assemble(corrected,annotations,source['image_size'])
            book.update(title=manifest['title'],source_page=n,printed_page='',view=[0,0,*source['image_size']],image_path=record['image'],provenance=source['provenance'])
            write_json(page/'book.json',book)
            record.update(status='validated',requests_sent=meta['requests_sent'],usage=meta.get('usage'),corrections=meta['corrections'],words=len(book['words']),book=f'pages/{n:03d}/book.json')
            record.pop('error',None)
        except Exception as exc:
            record.update(status='failed',error=str(exc))
            if (attempt/'run.json').exists():
                meta=json.loads((attempt/'run.json').read_text());record.update(requests_sent=meta['requests_sent'],usage=meta.get('usage'))
        write_json(page/'status.json',record);print(json.dumps(record,ensure_ascii=False),flush=True)
        return record
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for record in pool.map(process,numbers):
            entries[record['page']]=record
            manifest['pages']=[entries[n] for n in sorted(entries)];write_json(root/'manifest.json',manifest)
    manifest['status']='completed-with-errors' if any(r['status']=='failed' for r in entries.values()) else 'completed'
    manifest['explicit_retry_pages']=numbers
    write_json(root/'manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work',type=Path);parser.add_argument('--pages',nargs='+',type=int,required=True);parser.add_argument('--key-file',type=Path)
    parser.add_argument('--workers',type=int,default=2,help='Concurrent retry requests (default: 2)')
    args=parser.parse_args()
    if args.key_file:os.environ['DEEPSEEK_API_KEY']=read_api_key(args.key_file)
    if not os.environ.get('DEEPSEEK_API_KEY'):parser.error('DEEPSEEK_API_KEY or --key-file required')
    try:m=retry_pages(args.work,args.pages,args.workers)
    except (ValueError,OSError,KeyError) as exc:parser.exit(1,str(exc)+'\n')
    print(m['status'])

if __name__=='__main__':main()
