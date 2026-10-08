"""Annotate a page range from completed OCR, with safe restart after interruption."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
from pathlib import Path

from .annotate import read_api_key
from .batch import file_hash, process_page
from .prepare import write_json


def annotate_existing(pdf, images_dir, ocr_dir, output, first, last, workers,
                      title, key_file, dpi=240):
    if first < 1 or last < first or workers < 1:
        raise ValueError('Invalid page range or worker count')
    images = {n: images_dir / f'page-{n:03d}.png' for n in range(first, last + 1)}
    raw = {n: ocr_dir / f'page-{n:03d}' / f'page-{n:03d}_res.json'
           for n in images}
    missing = [n for n in images if not images[n].is_file() or not raw[n].is_file()]
    if missing:
        raise ValueError(f'Missing image or completed OCR for pages: {missing}')
    pdf_hash = file_hash(pdf)
    hashes = {str(n): file_hash(image) for n, image in images.items()}
    ocr_hashes = {str(n): file_hash(raw[n]) for n in images}
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    with (output / '.runner-lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for name, target in (('images', images_dir), ('ocr', ocr_dir)):
            link = output / name
            if link.is_symlink():
                if link.resolve() != target.resolve():
                    raise ValueError(f'{name} link points to a different input')
            elif link.exists():
                raise ValueError(f'{name} exists and is not an input symlink')
            else:
                link.symlink_to(target.resolve(), target_is_directory=True)
        (output / 'pages').mkdir(exist_ok=True)
        manifest_path = output / 'manifest.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if (manifest['pdf_sha256'] != pdf_hash or
                manifest['image_hashes'] != hashes or
                manifest['ocr_hashes'] != ocr_hashes or
                manifest['first_page'] != first or manifest['last_page'] != last or
                manifest['model'] != 'deepseek-flash' or
                manifest['thinking'] is not True):
                raise ValueError('Existing manifest does not match these inputs')
            if manifest['status'] != 'running':
                raise ValueError('Existing batch has finished; inspect failures separately')
        else:
            manifest = {'schema_version': 1, 'pdf_sha256': pdf_hash, 'title': title,
                        'first_page': first, 'last_page': last, 'dpi': dpi,
                        'model': 'deepseek-flash', 'thinking': True,
                        'max_output_tokens': 48000,
                        'ocr_provider': 'google-cloud-vision',
                        'annotation_workers': workers, 'image_hashes': hashes,
                        'ocr_hashes': ocr_hashes,
                        'status': 'running', 'pages': []}
            write_json(manifest_path, manifest)
        api_key = read_api_key(key_file)
        records = {}
        todo = []
        for n in images:
            page = output / 'pages' / f'{n:03d}'
            status = page / 'status.json'
            if status.exists():
                records[n] = json.loads(status.read_text())
            elif (page / 'annotation').exists():
                # An interrupted request may have reached the provider. Never
                # submit it again without an explicit audit/retry decision.
                record = {'page': n, 'image': f'images/page-{n:03d}.png',
                          'status': 'failed',
                          'error': 'Interrupted annotation; inspect saved attempt before retry'}
                write_json(status, record)
                records[n] = record
            else:
                todo.append(n)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = {pool.submit(process_page, n,
                                   output / 'images' / images[n].name,
                                   output / 'ocr' / images[n].stem /
                                   f'{images[n].stem}_res.json', output, title,
                                   api_key): n
                       for n in todo}
            for future in as_completed(pending):
                n = pending[future]
                records[n] = future.result()
                manifest['pages'] = [records[i] for i in sorted(records)]
                write_json(manifest_path, manifest)
        manifest['pages'] = [records[n] for n in sorted(records)]
        manifest['status'] = ('completed-with-errors' if any(
            record['status'] == 'failed' for record in records.values()) else 'completed')
        write_json(manifest_path, manifest)
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('images', type=Path)
    parser.add_argument('ocr', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--first', type=int, required=True)
    parser.add_argument('--last', type=int, required=True)
    parser.add_argument('--workers', type=int, default=64)
    parser.add_argument('--title', default='Local PDF')
    parser.add_argument('--dpi', type=int, default=240)
    parser.add_argument('--key-file', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = annotate_existing(args.pdf, args.images, args.ocr, args.output,
                                   args.first, args.last, args.workers,
                                   args.title, args.key_file, args.dpi)
    except (OSError, KeyError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps({'status': result['status'], 'pages': len(result['pages']),
                      'failed': sum(p['status'] == 'failed' for p in result['pages'])}))


if __name__ == '__main__':
    main()
