#!/usr/bin/env python3
"""Repeat all 15 provider/case/settings trials with the experimental line contract."""
import argparse, json, os, re, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib import request, error
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from duchinese_pdf.annotate import NoRedirect
from duchinese_pdf.prepare import write_json, digest
from line_contract import messages, compile_lines


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,default=Path('build/line-benchmark'))
    parser.add_argument('--models',nargs='+',choices=['deepseek-flash','deepseek-v4-pro','gpt-5.6-luna'],default=['deepseek-flash','deepseek-v4-pro','gpt-5.6-luna'])
    parser.add_argument('--max-tokens',type=int,default=14000)
    parser.add_argument('--timeout',type=int,default=240)
    parser.add_argument('--thinking-page25-only',action='store_true')
    args=parser.parse_args()
    if args.max_tokens<=0 or args.timeout<=0:parser.error('Token limit and timeout must be positive')
    root=args.work;root.mkdir(exist_ok=False)
    keys={}
    for provider in sorted({'openai' if m.startswith('gpt') else 'deepseek' for m in args.models}):
        key=os.environ.get(provider.upper()+'_API_KEY','').strip()
        if not key:
            parser.error(f'Set {provider.upper()}_API_KEY')
        keys[provider]=key
    def run(job):
        model,thinking,case=job;provider='openai' if model.startswith('gpt') else 'deepseek'
        source=json.loads((Path('tests/deepseek-benchmark')/('deepseek-flash-'+case)/'source.json').read_text())
        body={'model':model,'messages':messages(source),'response_format':{'type':'json_object'},'stream':False}
        if provider=='openai':
            body.update(reasoning_effort='medium' if thinking else 'none',max_completion_tokens=args.max_tokens,store=False,service_tier='default')
            if not thinking:body['temperature']=0
        else:body.update(thinking={'type':'enabled' if thinking else 'disabled'},max_tokens=args.max_tokens,temperature=0)
        out=root/f'{model}-{"on" if thinking else "off"}-{case}';out.mkdir()
        write_json(out/'source.json',source);write_json(out/'request.json',body)
        started=datetime.now(timezone.utc);t=time.monotonic()
        record=dict(model=model,thinking=thinking,case=case,started_utc=started.isoformat(),messages_digest=digest(body['messages']),max_completion_tokens=args.max_tokens,http_timeout_seconds=args.timeout)
        key=keys[provider]
        try:
            url='https://api.openai.com/v1/chat/completions' if provider=='openai' else 'https://api.deepseek.com/chat/completions'
            req=request.Request(url,data=json.dumps(body,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            try:
                with request.build_opener(NoRedirect()).open(req,timeout=args.timeout) as r:raw=json.load(r)
            except error.HTTPError as e:raise RuntimeError(f'HTTP {e.code}') from None
            write_json(out/'response.json',raw);record.update(usage=raw.get('usage'),returned_model=raw.get('model'))
            choice=raw['choices'][0];record['finish_reason']=choice['finish_reason']
            if choice['finish_reason']!='stop':raise ValueError('Incomplete generation')
            answer=json.loads(choice['message']['content']);write_json(out/'answer.json',answer)
            corrected,annotations,corrections=compile_lines(source,answer)
            for name,value in [('characters',corrected),('annotations',annotations),('corrections',corrections)]:write_json(out/(name+'.json'),value)
            record.update(valid=True,words=len(annotations['words']),sentences=len(annotations['sentences']),corrections=corrections['changes'])
        except Exception as e:record.update(valid=False,error=(type(e).__name__+': '+str(e)).replace(key,'[redacted]'))
        record['seconds']=time.monotonic()-t
        u=record.get('usage')
        if u:
            if provider=='openai':
                details=u.get('prompt_tokens_details',{});hits=details.get('cached_tokens',0);writes=details.get('cache_write_tokens',0)
                cost=(hits*.02+(u['prompt_tokens']-hits)*.20+writes*.05+u['completion_tokens']*1.20)/1e6
                record['estimated_usd']=cost
            else:
                rates=(.003,.15,.6) if model=='deepseek-flash' else (.022,.66,1.98)
                hits=u.get('prompt_cache_hit_tokens',0);miss=u.get('prompt_cache_miss_tokens',u['prompt_tokens']-hits)
                cost=(hits*rates[0]+miss*rates[1]+u['completion_tokens']*rates[2])/1e6
                hour=started.hour+started.minute/60;peak=started.weekday()<5 and (1<=hour<4 or 6<=hour<10)
                record.update(estimated_usd_off_peak=cost,peak_at_start=peak,estimated_usd=cost*(2 if peak else 1))
        write_json(out/'result.json',record);print(json.dumps(record,ensure_ascii=False),flush=True)
        return record
    settings=[(False,c) for c in ['challenge','page26','page25']]+[(True,c) for c in ['challenge','page25']]
    if args.thinking_page25_only:settings=[(True,'page25')]
    jobs=[(m,t,c) for t,c in settings for m in args.models]
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,jobs))
    write_json(root/'summary.json',results)
if __name__=='__main__':main()
