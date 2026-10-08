"""Trial Google Vision document OCR on rendered pages, retaining character boxes.

The direct image endpoint avoids Cloud Storage for page images under the JSON
request limit. Keep outputs under an ignored, private work directory.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import stat
import time
from urllib import error, request

from .annotate import NoRedirect
from .prepare import HAN, write_json

ENDPOINT = 'https://vision.googleapis.com/v1/images:annotate'
MAX_REQUEST_BYTES = 10_000_000


def symbol_box(symbol, width, height):
    poly = symbol.get('boundingBox') or {}
    vertices = poly.get('vertices')
    if not vertices:
        raise ValueError('OCR symbol has no character box')
    xs = [v.get('x', 0) for v in vertices]
    ys = [v.get('y', 0) for v in vertices]
    x0, x1 = max(0, min(xs)), min(width, max(xs))
    y0, y1 = max(0, min(ys)), min(height, max(ys))
    if x1 <= x0 or y1 <= y0:
        raise ValueError('OCR symbol has an empty or out-of-image box')
    return [x0, y0, x1, y1]


def convert_response(response):
    """Produce the existing prepare() input shape from Vision symbol geometry."""
    if response.get('error'):
        raise ValueError('Vision returned a page-level error')
    annotation = response.get('fullTextAnnotation') or {}
    texts, tokens, boxes = [], [], []
    spatial = False
    for page in annotation.get('pages', []):
        width, height = page['width'], page['height']
        paragraphs = []
        for block in page.get('blocks', []):
            for paragraph in block.get('paragraphs', []):
                chars, regions = [], []
                for word in paragraph.get('words', []):
                    for symbol in word.get('symbols', []):
                        value = symbol.get('text', '')
                        if not value or value.isspace():
                            continue
                        chars.append(value)
                        regions.append(symbol_box(symbol, width, height))
                if chars:
                    paragraphs.append((chars, regions))
        # Vision sometimes traverses exercise blanks in the wrong order. A
        # substantial upward jump between Chinese paragraphs flags those pages.
        chinese = [(chars, regions) for chars, regions in paragraphs
                   if HAN.search(''.join(chars))]
        tops = [min(box[1] for box in regions) for _, regions in chinese]
        spatial = any(next_top < top - max(25, height * 0.015)
                      for top, next_top in zip(tops, tops[1:]))
        if spatial:
            symbols = [(char, box) for chars, regions in paragraphs
                       for char, box in zip(chars, regions)]
            symbols.sort(key=lambda item: (item[1][1] + item[1][3]) / 2)
            rows = []
            for char, box in symbols:
                center = (box[1] + box[3]) / 2
                size = box[3] - box[1]
                if rows and abs(center - rows[-1][0]) <= min(size, rows[-1][1]) * 0.4:
                    rows[-1][2].append((char, box))
                else:
                    rows.append([center, size, [(char, box)]])
            paragraphs = []
            for _, _, row in rows:
                ordered = sorted(row, key=lambda item: item[1][0])
                region = []
                for item in ordered:
                    if region:
                        previous = region[-1][1]
                        gap = item[1][0] - previous[2]
                        size = max(previous[3] - previous[1], item[1][3] - item[1][1])
                        if gap > 1.5 * size:
                            paragraphs.append(([char for char, _ in region],
                                               [box for _, box in region]))
                            region = []
                    region.append(item)
                if region:
                    paragraphs.append(([char for char, _ in region],
                                       [box for _, box in region]))
        for chars, regions in paragraphs:
            texts.append(''.join(chars))
            tokens.append(chars)
            boxes.append(regions)
    return {'rec_texts': texts, 'text_word': tokens,
            'text_word_boxes': boxes, 'provider': 'google-cloud-vision',
            'reading_order': 'spatial-rows' if spatial else 'vision-paragraphs'}


def call_vision(image, api_key):
    content = base64.b64encode(image.read_bytes()).decode('ascii')
    body = json.dumps({'requests': [{'image': {'content': content},
                                     'features': [{'type': 'DOCUMENT_TEXT_DETECTION'}]}]},
                      separators=(',', ':')).encode()
    if len(body) > MAX_REQUEST_BYTES:
        raise ValueError('Image exceeds Vision inline JSON size limit')
    req = request.Request(ENDPOINT, data=body, method='POST',
                          headers={'x-goog-api-key': api_key,
                                   'Content-Type': 'application/json'})
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=180) as reply:
            result = json.load(reply)
    except error.HTTPError as exc:
        raise RuntimeError(f'Vision request failed with HTTP {exc.code}') from None
    except (error.URLError, TimeoutError):
        raise RuntimeError('Vision request failed or timed out') from None
    responses = result.get('responses', [])
    if len(responses) != 1:
        raise ValueError('Expected one Vision page response')
    return responses[0]


def read_key(path):
    path = path.expanduser()
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('API key file must be private (chmod 600)')
    key = path.read_text().strip()
    if not key or any(c.isspace() for c in key):
        raise ValueError('API key file must contain only the key')
    return key


def run(images, output, api_key, workers=8):
    if workers < 1:
        raise ValueError('Workers must be positive')
    if output.exists():
        raise ValueError('Output directory already exists')
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    records = {}

    def process(image):
        started = time.monotonic()
        page = output / image.stem
        page.mkdir(mode=0o700)
        record = {'image': str(image), 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
        try:
            response = call_vision(image, api_key)
            write_json(page / 'vision-response.json', response)
            converted = convert_response(response)
            write_json(page / f'{image.stem}_res.json', converted)
            record.update(status='completed', regions=len(converted['rec_texts']),
                          characters=sum(len(text) for text in converted['rec_texts']))
        except Exception as exc:
            record.update(status='failed', error=str(exc))
        record['seconds'] = round(time.monotonic() - started, 3)
        write_json(page / 'status.json', record)
        return record

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process, image): image.stem for image in images}
        for future in as_completed(futures):
            records[futures[future]] = future.result()
            write_json(output / 'run.json', {'provider': 'google-cloud-vision',
                                             'pages': [records[n] for n in sorted(records)]})
            print(json.dumps(records[futures[future]], ensure_ascii=False), flush=True)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--key-file', required=True, type=Path)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not all(image.is_file() for image in args.images):
        parser.error('All image paths must exist')
    if len({image.stem for image in args.images}) != len(args.images):
        parser.error('Image names must be unique')
    try:
        records = run(args.images, args.output, read_key(args.key_file), args.workers)
        if any(record['status'] == 'failed' for record in records.values()):
            parser.exit(1, 'One or more Vision pages failed; inspect private output/status.json files\n')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
