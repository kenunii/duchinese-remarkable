#!/usr/bin/env python3
"""Validate reviewed OCR + linguistic annotations and assemble an offline page.

Private document inputs and output belong outside tracked source (e.g. build/).
Character offsets use Unicode code points. Boxes use original raster pixels.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw


def assemble(characters, annotations, image_size):
    chars = characters['characters']
    text = ''.join(c['text'] for c in chars)
    width, height = image_size
    if 'image_size' in characters and list(image_size) != characters['image_size']:
        raise ValueError('Raster dimensions do not match prepared OCR')
    for i, char in enumerate(chars):
        if char['offset'] != i or len(char['text']) != 1:
            raise ValueError('Characters must have contiguous Unicode offsets')
        x, y, w, h = char['box']
        if not all(math.isfinite(v) for v in [x, y, w, h]) or min(x, y) < 0 or min(w, h) <= 0 or x+w > width or y+h > height:
            raise ValueError(f'Character {i} has an invalid box')
    cursor = 0
    words = []
    sentences = annotations['sentences']
    for item in annotations['words']:
        word = dict(item)
        start, end = word['start'], word['end']
        if start != cursor or end <= start or text[start:end] != word['hanzi']:
            raise ValueError(f'Annotation does not exactly match OCR at offset {cursor}')
        if not 0 <= word['sentence'] < len(sentences):
            raise ValueError('Invalid sentence reference')
        boxes = []
        last_line = None
        for char in chars[start:end]:
            x, y, w, h = char['box']
            if char['line'] == last_line:
                old = boxes[-1]
                right, bottom = max(old[0]+old[2], x+w), max(old[1]+old[3], y+h)
                old[0], old[1] = min(old[0], x), min(old[1], y)
                old[2], old[3] = right-old[0], bottom-old[1]
            else:
                boxes.append([x, y, w, h])
                last_line = char['line']
        word['boxes'] = boxes
        words.append(word)
        cursor = end
    if cursor != len(text):
        raise ValueError('Unannotated trailing text')
    for i, sentence in enumerate(sentences):
        actual = ''.join(w['hanzi'] for w in words if w['sentence'] == i)
        if actual != sentence['text'] or not sentence['translation'].strip():
            raise ValueError(f'Sentence {i} does not match its words or lacks translation')
    return {'schema_version': 1, 'image_width': width, 'image_height': height,
            'words': words, 'sentences': sentences}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('image', type=Path)
    p.add_argument('characters', type=Path)
    p.add_argument('annotations', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--title', default='Local PDF')
    p.add_argument('--page', type=int, required=True, help='One-based original PDF page')
    p.add_argument('--printed-page', default='')
    p.add_argument('--view', type=float, nargs=4, help='Initial view x y width height; original raster pixels')
    args = p.parse_args()
    characters = json.loads(args.characters.read_text())
    expected_hash = characters.get('provenance', {}).get('image_sha256')
    if expected_hash and hashlib.sha256(args.image.read_bytes()).hexdigest() != expected_hash:
        raise ValueError('Raster does not match the image used for prepared OCR')
    with Image.open(args.image) as image:
        book = assemble(characters, json.loads(args.annotations.read_text()), image.size)
        book.update(title=args.title, source_page=args.page, printed_page=args.printed_page,
                    view=args.view or [0, 0, *image.size])
        x,y,w,h = book['view']
        if min(x,y)<0 or min(w,h)<=0 or x+w>image.width or y+h>image.height:
            raise ValueError('Initial view outside raster')
        args.output.mkdir(parents=True, exist_ok=True)
        image.save(args.output/'page.png')
        (args.output/'book.json').write_text(json.dumps(book, ensure_ascii=False, indent=2)+'\n')
        (args.output/'Book.js').write_text('.pragma library\nvar book = '+json.dumps(book, ensure_ascii=False)+';\n')
        preview = image.convert('RGB')
        draw = ImageDraw.Draw(preview)
        for i,word in enumerate(book['words']):
            if not word['pinyin']: continue
            for x,y,w,h in word['boxes']:
                draw.rectangle((x,y,x+w,y+h),outline=['#c00000','#0060c0','#008040'][i%3],width=2)
        preview.save(args.output/'alignment-review.png')
        print(f"Assembled {len(book['words'])} tokens; source text and sentence alignment verified")

if __name__ == '__main__':
    main()
