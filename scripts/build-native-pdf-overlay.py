#!/usr/bin/env python3
"""Package validated lookup data for one or more native PDF documents."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import UUID


def package(collection: Path, pdf: Path):
    manifest = json.loads((collection / 'manifest.json').read_text())
    if manifest['status'] != 'completed':
        raise ValueError(f'Collection is incomplete: {collection}')
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != manifest['pdf_sha256']:
        raise ValueError(f'Source PDF hash does not match collection: {collection}')
    info = subprocess.check_output([
        'pdfinfo', '-f', str(manifest['first_page']), '-l', str(manifest['last_page']),
        '-box', str(pdf)], text=True)
    page_boxes = {}
    for line in info.splitlines():
        match = re.match(r'Page\s+(\d+)\s+(MediaBox|CropBox):\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)', line)
        if match:
            page_boxes.setdefault(int(match[1]), {})[match[2]] = tuple(map(float, match.groups()[2:]))
    pages = {}
    for entry in manifest['pages']:
        if entry['status'] != 'validated':
            continue
        book = json.loads((collection / entry['book']).read_text())
        number = entry['page']
        if book['source_page'] != number:
            raise ValueError(f'Page mismatch at {number}: {collection}')
        boxes = page_boxes.get(number, {})
        if 'MediaBox' not in boxes or 'CropBox' not in boxes:
            raise ValueError(f'Missing PDF boxes for page {number}: {pdf}')
        media, crop = boxes['MediaBox'], boxes['CropBox']
        scale_x = book['image_width'] / (media[2] - media[0])
        scale_y = book['image_height'] / (media[3] - media[1])
        pages[number] = {
            'width': book['image_width'], 'height': book['image_height'],
            'crop': [
                (crop[0] - media[0]) * scale_x,
                (media[3] - crop[3]) * scale_y,
                (crop[2] - crop[0]) * scale_x,
                (crop[3] - crop[1]) * scale_y,
            ],
            'sentences': [
                {'text': sentence['text'], 'translation': sentence.get('translation', '')}
                for sentence in book['sentences']
            ],
            'words': [
                {'hanzi': word['hanzi'], 'pinyin': word.get('pinyin', ''),
                 'meaning': word.get('meaning', ''), 'sentence': word.get('sentence', -1),
                 'boxes': word['boxes']}
                for word in book['words'] if word.get('pinyin') and word['boxes']
            ],
        }
    return {'pdfSha256': manifest['pdf_sha256'], 'pages': pages}


def main():
    if len(sys.argv) < 5 or (len(sys.argv) - 2) % 3:
        raise SystemExit('Usage: build-native-pdf-overlay.py OUTPUT COLLECTION PDF DOCUMENT_UUID [COLLECTION PDF DOCUMENT_UUID ...]')
    output = Path(sys.argv[1]).resolve()
    documents = {}
    for n in range(2, len(sys.argv), 3):
        collection = Path(sys.argv[n]).resolve()
        pdf = Path(sys.argv[n + 1]).resolve()
        document_id = str(UUID(sys.argv[n + 2]))
        data = package(collection, pdf)
        if document_id in documents:
            raise ValueError(f'Duplicate document ID: {document_id}')
        documents[document_id] = data
        print(f'Packaged {len(data["pages"])} validated pages for {document_id}')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'LookupData.js').write_text(
        '.pragma library\nvar documents = '
        + json.dumps(documents, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print(json.dumps(list(documents)))


if __name__ == '__main__':
    main()
