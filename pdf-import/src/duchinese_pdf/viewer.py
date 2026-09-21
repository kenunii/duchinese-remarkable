"""Build an offline viewer for the five-page textbook benchmark."""
import argparse
import json
from pathlib import Path
from importlib.resources import files

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('work',type=Path);a=p.parse_args()
    pages={}
    for page in range(22,27):
        pages[str(page)]={engine:json.loads((a.work/'evaluation'/f'{engine}-{page}'/'score.json').read_text()) for engine in ['paddle','tesseract']}
    html=files('duchinese_pdf').joinpath('templates/comparison.html').read_text(encoding='utf-8')
    html=html.replace('PAGES',''.join(f'<option value="{p}">PDF {p} / printed {p-18}</option>' for p in range(22,27))).replace('DATA',json.dumps(pages,ensure_ascii=False).replace('<','\\u003c'))
    (a.work/'comparison.html').write_text(html)
    print(a.work/'comparison.html')

if __name__ == "__main__":
    main()
