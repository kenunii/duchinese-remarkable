"""Convert PaddleOCR character boxes into a stable, auditable annotation input."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from PIL import Image

HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003134f]')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate_source(source):
    width, height = source['image_size']
    if any(type(v) is not int or v <= 0 for v in (width, height)):
        raise ValueError('Invalid image dimensions')
    chars = source['characters']
    if not isinstance(chars, list) or not chars:
        raise ValueError('No characters to annotate')
    for i, char in enumerate(chars):
        if type(char['offset']) is not int or char['offset'] != i:
            raise ValueError('Source offsets must be contiguous Unicode code points')
        if not isinstance(char['text'], str) or len(char['text']) != 1:
            raise ValueError('Each source item must contain exactly one character')
        if type(char['line']) is not int or char['line'] < 0:
            raise ValueError('Invalid source line')
        box = char['box']
        if len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
            raise ValueError('Non-finite character box')
        x, y, w, h = box
        if min(x, y) < 0 or min(w, h) <= 0 or x+w > width or y+h > height:
            raise ValueError('Character box outside image')
    return ''.join(c['text'] for c in chars)


def prepare(raw, image_size, selected=None):
    raw = raw.get('res', raw)
    texts, tokens, boxes = raw['rec_texts'], raw['text_word'], raw['text_word_boxes']
    if not len(texts) == len(tokens) == len(boxes):
        raise ValueError('Paddle text/box arrays differ in length')
    if selected is not None and (not selected or any(i < 0 or i >= len(texts) for i in selected)):
        raise ValueError('Selected line outside OCR output')
    chars, lines, omitted = [], [], []
    for i, (text, words, regions) in enumerate(zip(texts, tokens, boxes)):
        if (selected is not None and i not in selected) or (selected is None and not HAN.search(text)):
            omitted.append({'line': i, 'text': text, 'reason': 'not selected' if selected is not None else 'no Chinese characters'})
            continue
        if len(words) != len(regions):
            raise ValueError(f'Line {i}: token/box count mismatch')
        if re.sub(r'\s', '', ''.join(words)) != re.sub(r'\s', '', text):
            raise ValueError(f'Line {i}: character tokens do not match recognized text')
        start = len(chars)
        for token, box in zip(words, regions):
            x0, y0, x1, y1 = box
            # Paddle groups Latin letters/numbers. Preserve that ORIGINAL region
            # for every code point; never invent per-letter coordinates.
            for char in token:
                if char.isspace():
                    continue
                chars.append({'offset': len(chars), 'text': char, 'line': i,
                              'box': [x0, y0, x1-x0, y1-y0]})
        if len(chars) == start:
            raise ValueError(f'Line {i}: no character geometry')
        lines.append({'line': i, 'start': start, 'end': len(chars), 'ocr_text': text})
    result = {'schema_version': 1, 'image_size': list(image_size), 'characters': chars,
              'lines': lines, 'omitted_lines': omitted,
              'normalization': 'Whitespace removed; original OCR retained. Multi-character tokens share their original box.'}
    validate_source(result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('ocr', type=Path)
    p.add_argument('image', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--lines', type=int, nargs='+', help='Optional zero-based OCR region IDs; default: all Chinese-containing regions')
    a = p.parse_args()
    if a.output.exists():
        p.error('Output already exists; choose a new path')
    with Image.open(a.image) as image:
        value = prepare(json.loads(a.ocr.read_text()), image.size,
                        set(a.lines) if a.lines is not None else None)
    value['provenance'] = {'ocr_sha256': hashlib.sha256(a.ocr.read_bytes()).hexdigest(),
                           'image_sha256': hashlib.sha256(a.image.read_bytes()).hexdigest()}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(a.output, value)
    print(f"Prepared {len(value['characters'])} characters; {len(value['omitted_lines'])} nonselected regions recorded")


if __name__ == '__main__':
    main()
