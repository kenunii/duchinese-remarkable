"""OCR and annotate a rendered PDF page range, preserving every per-page outcome."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from PIL import Image
from .annotate import run, read_api_key
from .assemble import assemble
from .prepare import HAN, prepare, write_json


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_page(number, image_path, raw_path, root, title):
    out=root/'pages'/f'{number:03d}';out.mkdir(parents=True)
    record={'page':number,'image':str(image_path.relative_to(root))}
    try:
        raw=json.loads(raw_path.read_text());data=raw.get('res',raw)
        with Image.open(image_path) as im: dimensions=list(im.size)
        provenance={'ocr_sha256':file_hash(raw_path),'image_sha256':file_hash(image_path)}
        if not any(HAN.search(t) for t in data['rec_texts']):
            record.update(status='image-only',reason='No Chinese detected by OCR',requests_sent=0)
            book={'schema_version':1,'image_width':dimensions[0],'image_height':dimensions[1],'words':[],'sentences':[]}
        else:
            source=prepare(raw,dimensions);source['provenance']=provenance
            write_json(out/'source.json',source)
            record['characters']=len(source['characters'])
            meta=run(source,out/'annotation',model='deepseek-flash',provider='deepseek')
            corrected=json.loads((out/'annotation/result/characters.json').read_text())
            annotations=json.loads((out/'annotation/result/annotations.json').read_text())
            book=assemble(corrected,annotations,dimensions)
            record.update(status='validated',requests_sent=meta['requests_sent'],usage=meta.get('usage'),corrections=meta['corrections'],words=len(book['words']))
        book.update(title=title,source_page=number,printed_page='',view=[0,0,*dimensions],image_path=record['image'],provenance=provenance)
        write_json(out/'book.json',book)
        record['book']=str((out/'book.json').relative_to(root))
    except Exception as exc:
        record.update(status='failed',error=str(exc))
        meta_path=out/'annotation/run.json'
        if meta_path.exists():
            meta=json.loads(meta_path.read_text());record.update(requests_sent=meta['requests_sent'],usage=meta.get('usage'))
    write_json(out/'status.json',record)
    print(json.dumps(record,ensure_ascii=False),flush=True)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path)
    parser.add_argument('output',type=Path,help='Directory already containing images/page-NNN.png at 240 dpi')
    parser.add_argument('--first',type=int,default=1)
    parser.add_argument('--last',type=int,required=True)
    parser.add_argument('--ocr-python',type=Path,required=True)
    parser.add_argument('--models',type=Path,required=True)
    parser.add_argument('--title',default='Local PDF')
    parser.add_argument('--key-file',type=Path,help='Optional local DeepSeek credential file')
    args=parser.parse_args()
    if args.first<1 or args.last<args.first:parser.error('Invalid page range')
    if args.key_file:os.environ['DEEPSEEK_API_KEY']=read_api_key(args.key_file)
    if not os.environ.get('DEEPSEEK_API_KEY'):parser.error('DEEPSEEK_API_KEY is required')
    root=args.output
    if (root/'manifest.json').exists():parser.error('Existing batch manifest: choose a new output directory; no implicit retries')
    images={n:root/'images'/f'page-{n:03d}.png' for n in range(args.first,args.last+1)}
    for path in images.values():
        if not path.is_file():parser.error(f'Missing rendered page: {path}')
    metadata={'schema_version':1,'pdf_sha256':file_hash(args.pdf),'title':args.title,'first_page':args.first,'last_page':args.last,
              'model':'deepseek-flash','thinking':True,'max_output_tokens':48000,'dpi':240,
              'image_hashes':{str(n):file_hash(p) for n,p in images.items()},'status':'running','pages':[]}
    write_json(root/'manifest.json',metadata)
    raw_root=root/'ocr'
    command=['systemd-run','--user','--scope','-p','MemoryMax=5G','-p','MemorySwapMax=512M',
             str(args.ocr_python),'-m','duchinese_pdf','ocr',*[str(p) for p in images.values()],
             '--models',str(args.models),'--output',str(raw_root)]
    env=dict(os.environ,OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
    # OCR does not need access to the API credential.
    env.pop('DEEPSEEK_API_KEY',None);env.pop('OPENAI_API_KEY',None)
    env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
    pending={};submitted=set();results={}
    with (root/'ocr.log').open('w') as log,ThreadPoolExecutor(max_workers=2) as pool:
        proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env)
        while True:
            report_path=raw_root/'run.json'
            try:completed={Path(p['image']).stem for p in json.loads(report_path.read_text())['pages']}
            except (OSError,json.JSONDecodeError):completed=set()
            for n,image_path in images.items():
                if n not in submitted and image_path.stem in completed:
                    submitted.add(n)
                    raw_path=raw_root/image_path.stem/(image_path.stem+'_res.json')
                    pending[pool.submit(process_page,n,image_path,raw_path,root,args.title)]=n
            changed=False
            for future,n in list(pending.items()):
                if future.done():
                    results[n]=future.result();del pending[future];changed=True
            if changed:
                metadata['pages']=[results[n] for n in sorted(results)];write_json(root/'manifest.json',metadata)
            if proc.poll() is not None:
                for n in images:
                    if n not in submitted:
                        results[n]={'page':n,'image':str(images[n].relative_to(root)),'status':'failed','error':f'OCR did not complete (exit {proc.returncode}); see ocr.log'}
                        submitted.add(n)
                if not pending:break
            time.sleep(1)
    metadata['pages']=[results[n] for n in sorted(results)]
    metadata['status']='completed-with-errors' if any(r['status']=='failed' for r in results.values()) else 'completed'
    metadata['ocr_exit_code']=proc.returncode
    write_json(root/'manifest.json',metadata)
    print(json.dumps({'status':metadata['status'],'pages':len(results),'failed':sum(r['status']=='failed' for r in results.values())}),flush=True)

if __name__=='__main__':main()
