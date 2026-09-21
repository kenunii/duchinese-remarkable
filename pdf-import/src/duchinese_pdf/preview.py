"""Create a server-free preview of validated page-range data and original images."""
import argparse
import json
from pathlib import Path
from importlib.resources import files


def build_preview(root):
    manifest=json.loads((root/'manifest.json').read_text())
    statuses={p['page']:p for p in manifest['pages']}
    pages=[]
    for n in range(manifest['first_page'],manifest['last_page']+1):
        status=statuses.get(n,{'page':n,'status':'pending','image':f'images/page-{n:03d}.png'})
        entry=dict(status)
        if status.get('book'):
            entry['data']=json.loads((root/status['book']).read_text())
        pages.append(entry)
    data={'title':manifest['title'],'pages':pages}
    template=files('duchinese_pdf').joinpath('templates/preview.html').read_text()
    result=template.replace('__BOOK_DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
    path=root/'preview.html';path.write_text(result,encoding='utf-8')
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('work',type=Path);a=p.parse_args()
    print(build_preview(a.work))

if __name__=='__main__':main()
