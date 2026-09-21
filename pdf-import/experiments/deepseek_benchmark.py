#!/usr/bin/env python3
"""Small live annotation benchmark. Credentials stay in memory, not artifacts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib import request, error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from duchinese_pdf.annotate import make_request, compile_annotations, NoRedirect
from duchinese_pdf.prepare import write_json


def key_for(a):
    key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if key:
        return key
    if not a.key_file:
        raise ValueError('Set DEEPSEEK_API_KEY or pass --key-file PATH')
    content = a.key_file.expanduser().read_text()
    match = re.search(r'\bsk-[A-Za-z0-9_-]{20,}\b',content)
    if not match:
        raise ValueError('No DeepSeek credential found')
    return match.group(0)


def fetch(key, path, body=None):
    req=request.Request('https://api.deepseek.com/'+path,
                        data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,
                        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with request.build_opener(NoRedirect()).open(req,timeout=240) as r:return json.load(r)
    except error.HTTPError as e:
        raise RuntimeError(f'DeepSeek HTTP {e.code}') from None


def fixture():
    texts=['我喜欢自已学习。','他已经到了，巳时开始上课。','老师教我们汉语，也教会了我们怎样学习。',
           '这家银行的行长说，这个办法行不行，还得再看看。','音乐很好听，他听得很快乐。',
           '桌子上只有三本书，不是十三本。','因为收入太低，所以他不想再加班了。']
    chars=[]
    for line,text in enumerate(texts):
        for i,c in enumerate(text):chars.append({'offset':len(chars),'text':c,'line':line,'box':[i*20,line*30,20,20]})
    return {'image_size':[1000,500],'characters':chars,'test_description':'Synthetic linguistic challenge; exactly one intended correction: 自已 -> 自己. Synthetic geometry.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key-file',type=Path)
    p.add_argument('--work',type=Path,default=Path('build/deepseek-benchmark'))
    p.add_argument('--thinking',choices=['disabled','enabled'],default='disabled')
    p.add_argument('--cases',nargs='+',choices=['challenge','page26','page25'],default=['challenge','page26','page25'])
    a=p.parse_args();key=key_for(a)
    a.work.mkdir(parents=True,exist_ok=True)
    models=fetch(key,'models');write_json(a.work/'models.json',models)
    print('Available models:',[m['id'] for m in models.get('data',[])],flush=True)
    cases={'challenge':fixture(), 'page26':json.loads(Path('build/llm-step-check/page-26.json').read_text()),
           'page25':json.loads(Path('build/llm-step-check/page-25.json').read_text())}
    model_ids=['deepseek-flash','deepseek-v4-pro']
    def execute(job):
        model,name=job;out=a.work/(model+'-'+name);out.mkdir()
        source=cases[name];base=make_request(source,model)
        system=base['instructions']+'\nOutput JSON matching this schema:\n'+json.dumps(base['text']['format']['schema'],ensure_ascii=False)
        system+='\nExample shape (content is illustrative only): {"corrections":[],"sentences":[{"translation":"Study.","words":[{"text":"学习","pinyin":"xué xí","meaning":"to study"}]}]}'
        body={'model':model,'messages':[{'role':'system','content':system},*base['input']],
              'response_format':{'type':'json_object'},'thinking':{'type':a.thinking},
              'max_tokens':14000,'stream':False,'temperature':0}
        write_json(out/'request.json',body);write_json(out/'source.json',source)
        started=datetime.now(timezone.utc);t=time.monotonic()
        record={'requested_model':model,'case':name,'started_utc':started.isoformat(),'thinking':a.thinking}
        try:
            raw=fetch(key,'chat/completions',body);write_json(out/'response.json',raw)
            record.update(seconds=time.monotonic()-t,returned_model=raw.get('model'),usage=raw.get('usage'))
            choice=raw['choices'][0];record['finish_reason']=choice['finish_reason']
            if choice['finish_reason']!='stop':raise ValueError('Incomplete generation')
            answer=json.loads(choice['message']['content']);write_json(out/'answer.json',answer)
            corrected,annotations,corrections=compile_annotations(source,answer)
            write_json(out/'characters.json',corrected);write_json(out/'annotations.json',annotations);write_json(out/'corrections.json',corrections)
            record.update(valid=True,words=len(annotations['words']),sentences=len(annotations['sentences']),corrections=corrections['changes'])
        except Exception as exc:
            record.update(valid=False,error=type(exc).__name__+': '+str(exc),seconds=time.monotonic()-t)
        usage=record.get('usage') or {}
        # Official per-million-token tariffs, 2026-09-16. A reported model name
        # cannot prove the underlying weights; compare with the docs/model list.
        rates=(.003,.15,.6) if model=='deepseek-flash' else (.022,.66,1.98)
        hits=usage.get('prompt_cache_hit_tokens',0)
        misses=usage.get('prompt_cache_miss_tokens',usage.get('prompt_tokens',0)-hits)
        outputs=usage.get('completion_tokens',0)
        off=(hits*rates[0]+misses*rates[1]+outputs*rates[2])/1_000_000
        hour=started.hour+started.minute/60
        peak=started.weekday()<5 and (1<=hour<4 or 6<=hour<10)
        record.update(estimated_usd_off_peak=off,estimated_usd_peak=2*off,peak_at_start=peak,
                      estimated_usd_at_start=off*(2 if peak else 1))
        write_json(out/'result.json',record);print(json.dumps(record,ensure_ascii=False),flush=True)
        return record
    with ThreadPoolExecutor(max_workers=2) as pool:
        records=list(pool.map(execute,[(m,c) for c in a.cases for m in model_ids]))
    write_json(a.work/'summary.json',records)

if __name__=='__main__':main()
