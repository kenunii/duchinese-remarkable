"""Validate and prepare existing page data for both tablet and mobile readers."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from .page_view import content_view


def load_collection(root: Path):
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['status'] != 'completed':
        raise ValueError('Collection is not complete')
    entries = manifest['pages']
    if [e['page'] for e in entries] != list(range(manifest['first_page'], manifest['last_page'] + 1)):
        raise ValueError('Missing or reordered pages')
    pages = []
    for entry in entries:
        if entry['status'] not in ('validated', 'image-only'):
            raise ValueError('Unvalidated page')
        image = root / entry['image']
        number = entry['page']
        if hashlib.sha256(image.read_bytes()).hexdigest() != manifest['image_hashes'][str(number)]:
            raise ValueError('Image hash mismatch')
        book = json.loads((root / entry['book']).read_text())
        if book['source_page'] != number:
            raise ValueError('Wrong page data')
        boxes = [box for word in book['words'] for box in word['boxes']]
        raw_path = root / 'ocr' / image.stem / (image.stem + '_res.json')
        if raw_path.exists():
            raw = json.loads(raw_path.read_text())
            raw = raw.get('res', raw)
            boxes += [[x, y, right-x, bottom-y] for x, y, right, bottom in raw.get('rec_boxes', [])]
        with Image.open(image) as raster:
            book['view'] = content_view(raster, boxes)
        book['image_file'] = f'page-{number:03d}.png'
        pages.append(book)
    return manifest, pages
