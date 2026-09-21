#!/usr/bin/env python3
"""Score untouched OCR against independent Chinese-only reference transcriptions.

This is an evaluation tool. It never changes OCR text or boxes. The page-23 body
region excludes illustration labels with ambiguous inter-bubble reading order.
"""
import argparse
import json
import re
import statistics
from pathlib import Path
from PIL import Image,ImageDraw
from lxml import etree

HAN=re.compile(r'[\u3400-\u9fff]')
def han(text):return ''.join(HAN.findall(text))

def edit_distance(ref,hyp):
    # Unit-cost Levenshtein, with trace to distinguish substitutions/deletions/insertions.
    matrix=[list(range(len(hyp)+1))]
    for i,a in enumerate(ref,1):
        row=[i]
        for j,b in enumerate(hyp,1):row.append(min(matrix[-1][j]+1,row[-1]+1,matrix[-1][j-1]+(a!=b)))
        matrix.append(row)
    i,j=len(ref),len(hyp);edits=[]
    while i or j:
        if i and j and matrix[i][j]==matrix[i-1][j-1]+(ref[i-1]!=hyp[j-1]):
            if ref[i-1]!=hyp[j-1]:edits.append({'kind':'substitution','reference':ref[i-1],'ocr':hyp[j-1],'reference_offset':i-1,'ocr_offset':j-1})
            i-=1;j-=1
        elif i and matrix[i][j]==matrix[i-1][j]+1:
            edits.append({'kind':'deletion','reference':ref[i-1],'ocr':'','reference_offset':i-1,'ocr_offset':j});i-=1
        else:
            edits.append({'kind':'insertion','reference':'','ocr':hyp[j-1],'reference_offset':i,'ocr_offset':j-1});j-=1
    return matrix[-1][-1],list(reversed(edits))

def spatial_order(lines):
    # Evaluation-only alternative: cluster nearby baselines, then read left-to-right.
    # Raw OCR order remains the primary score and is preserved unchanged.
    ordered=sorted(lines,key=lambda l:(l['box'][1]+l['box'][3])/2)
    rows=[]
    for line in ordered:
        center=(line['box'][1]+line['box'][3])/2
        height=line['box'][3]-line['box'][1]
        if rows and abs(center-rows[-1][0])<=min(height,rows[-1][1])*.4:
            rows[-1][2].append(line)
        else:rows.append([center,height,[line]])
    return [line for _,_,row in rows for line in sorted(row,key=lambda l:l['box'][0])]

def paddle_lines(path):
    value=json.loads(path.read_text());value=value.get('res',value)
    lines=[]
    for i,(text,box,score) in enumerate(zip(value['rec_texts'],value['rec_boxes'],value['rec_scores'])):
        chars=[]
        regions=value.get('text_word_region')
        if regions is not None:
            polygons=regions[i]
        else:
            polygons=[[[x0,y0],[x1,y0],[x1,y1],[x0,y1]] for x0,y0,x1,y1 in value.get('text_word_boxes',[[]]*len(value['rec_texts']))[i]]
        for token,poly in zip(value.get('text_word',[[]]*len(value['rec_texts']))[i],polygons):
            chars.append({'text':token,'polygon':poly})
        lines.append({'text':text,'box':box,'confidence':score,'characters':chars})
    return lines

def tess_lines(path):
    r=etree.parse(str(path));lines=[]
    for line in r.xpath('//*[starts-with(@id,"line_")]'):
        box=list(map(int,re.search(r'bbox (\d+) (\d+) (\d+) (\d+)',line.get('title')).groups()))
        chars=[]
        for c in line.xpath('.//*[contains(@class,"ocrx_cinfo")]'):
            x0,y0,x1,y1=map(int,re.search(r'x_bboxes (\d+) (\d+) (\d+) (\d+)',c.get('title')).groups())
            chars.append({'text':c.text or '', 'polygon':[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]})
        scores=[int(re.search(r'x_wconf (\d+)',w.get('title')).group(1))/100 for w in line.xpath('.//*[contains(@class,"ocrx_word")]')]
        lines.append({'text':''.join(c['text'] for c in chars),'box':box,'confidence':statistics.mean(scores) if scores else 0,'characters':chars})
    return lines

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('work',type=Path);p.add_argument('references',type=Path)
    p.add_argument('--engines',nargs='+',choices=['paddle','tesseract'],default=['paddle','tesseract'])
    p.add_argument('--pages',nargs='+',type=int,default=list(range(22,27)))
    args=p.parse_args();reports=[]
    for page in args.pages:
        source=Image.open(args.work/f'page-{page}.png').convert('RGB')
        ref=(args.references/f'page-{page}.txt').read_text()
        if page==23:ref=ref[ref.index('（在茶馆'):]
        ref=han(ref)
        for engine in args.engines:
            if engine=='paddle':
                path=next((args.work/'paddle'/f'page-{page}').glob('*.json'));lines=paddle_lines(path)
            else:lines=tess_lines(args.work/'tesseract'/f'page-{page}.hocr')
            selected=[line for line in lines if page!=23 or (line['box'][1]+line['box'][3])/2>source.height*.60]
            hyp=han(''.join(line['text'] for line in selected))
            distance,edits=edit_distance(ref,hyp)
            spatial_hyp=han(''.join(line['text'] for line in spatial_order(selected)))
            spatial_distance,_=edit_distance(ref,spatial_hyp)
            han_lines=[line for line in selected if han(line['text'])]
            record={'page':page,'engine':engine,'reference_characters':len(ref),'ocr_characters':len(hyp),'errors':distance,'cer':distance/len(ref),'spatial_errors':spatial_distance,'spatial_cer':spatial_distance/len(ref),'edits':edits,'chinese_lines':len(han_lines),'lines_below_090':sum(line['confidence']<.9 for line in han_lines),'lines_below_095':sum(line['confidence']<.95 for line in han_lines),'lines':lines,'scored_ocr':hyp,'reference':ref}
            report_dir=args.work/'evaluation'/f'{engine}-{page}';report_dir.mkdir(parents=True,exist_ok=True)
            (report_dir/'score.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
            (report_dir/'text.txt').write_text('\n'.join(f"{i:03} [{line['confidence']:.3f}] {line['text']}" for i,line in enumerate(lines)))
            overlay=source.copy();draw=ImageDraw.Draw(overlay)
            for i,line in enumerate(lines):
                for j,c in enumerate(line['characters']):
                    if not han(c['text']):continue
                    poly=[tuple(p) for p in c['polygon']]
                    draw.line(poly+[poly[0]], fill=['#d00000','#0060c0','#008040'][j%3],width=2)
                x0,y0,x1,y1=line['box'];draw.text((x0,max(0,y0-18)),str(i),fill='#a000a0')
            overlay.save(report_dir/'boxes.png')
            reports.append({k:v for k,v in record.items() if k not in ['lines','edits','scored_ocr','reference']})
            print(page,engine,f'{distance}/{len(ref)} = {100*distance/len(ref):.2f}% CER',flush=True)
    (args.work/'evaluation'/'summary.json').write_text(json.dumps(reports,indent=2))

if __name__=='__main__':main()
