#!/usr/bin/env python3
"""Offline diagnostics; never mutates or repairs provider answers."""
import difflib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from duchinese_pdf.prepare import write_json
from line_contract import payload
root=Path(sys.argv[1] if len(sys.argv)>1 else 'build/line-benchmark')
results=[]
for path in sorted(root.glob('*/answer.json')):
    answer=json.loads(path.read_text());source=json.loads((path.parent/'source.json').read_text())
    expected=payload(source)['lines']
    raw=''.join(c['text'] for c in source['characters'])
    words=''.join(w['text'] for s in answer.get('sentences',[]) for w in s.get('words',[]))
    lines=answer.get('lines',[])
    differences=[]
    for op,i,j,k,l in difflib.SequenceMatcher(None,raw,words,autojunk=False).get_opcodes():
        if op!='equal':differences.append({'operation':op,'start':i,'original':raw[i:j],'output':words[k:l]})
    results.append({'run':path.parent.name,'line_ids_match':[x['id'] for x in lines]==[x['id'] for x in expected],
                    'word_text_differences':differences,
                    'percentages_in_english': [s['translation'] for s in answer.get('sentences',[]) if '%' in s['translation']]})
write_json(root/'diagnostics.json',results)
for result in results:print(result['run'],result['line_ids_match'],result['word_text_differences'])
