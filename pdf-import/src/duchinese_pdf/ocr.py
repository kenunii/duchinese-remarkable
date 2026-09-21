#!/usr/bin/env python3
"""Run uncorrected PP-OCRv5 on rendered pages, preserving raw output and timing.

Use an isolated environment containing paddlepaddle and paddleocr. No reference
transcriptions are loaded by this runner. Inputs/outputs should be ignored local
files, since they may contain private textbook material.

The tested CPU runtime is PaddlePaddle 3.2.2. Version 3.3.1 failed with a
oneDNN PIR conversion error; disabling oneDNN exceeded the memory budget.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK','True')
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE','bos')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('images',nargs='+',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--threads',type=int,default=4)
    p.add_argument('--legacy-ir',action='store_true',help='Try the legacy Paddle execution IR')
    p.add_argument('--models',type=Path,help='Directory containing downloaded PP-OCRv5_server_*_infer models')
    args=p.parse_args()
    from paddleocr import PaddleOCR
    args.output.mkdir(parents=True,exist_ok=True)
    settings=dict(text_detection_model_name='PP-OCRv5_server_det',
                  text_recognition_model_name='PP-OCRv5_server_rec',
                  use_doc_orientation_classify=False,use_doc_unwarping=False,
                  use_textline_orientation=False,return_word_box=True,
                  device='cpu',cpu_threads=args.threads,
                  enable_mkldnn=True,text_recognition_batch_size=1,text_det_limit_side_len=1536,
                  text_det_limit_type='max')
    if args.legacy_ir:
        settings.update(engine='paddle_static',engine_config={
            'run_mode':'mkldnn','cpu_threads':args.threads,'enable_new_ir':False})
    if args.models:
        settings['text_detection_model_dir']=str(args.models/'PP-OCRv5_server_det_infer')
        settings['text_recognition_model_dir']=str(args.models/'PP-OCRv5_server_rec_infer')
    started=time.monotonic()
    ocr=PaddleOCR(**settings)
    report={'python':platform.python_version(),'settings':settings,
            'packages':{n:importlib.metadata.version(n) for n in ['paddlepaddle','paddleocr','paddlex']},
            'init_seconds':time.monotonic()-started,'pages':[]}
    for path in args.images:
        output=args.output/path.stem
        output.mkdir(exist_ok=True)
        start=time.monotonic()
        results=list(ocr.predict(str(path)))
        elapsed=time.monotonic()-start
        for result in results:
            result.save_to_json(str(output))
        stats={'image':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'seconds':elapsed}
        report['pages'].append(stats)
        (args.output/'run.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(stats),flush=True)

if __name__=='__main__':main()
