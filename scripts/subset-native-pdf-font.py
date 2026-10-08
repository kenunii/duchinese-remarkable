#!/usr/bin/env python3
"""Keep only glyphs displayed by this private native PDF lookup bundle."""
import argparse
from pathlib import Path
import string

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font', type=Path)
    parser.add_argument('lookup_data', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('ui_sources', nargs='*', type=Path)
    args = parser.parse_args()

    # The generated glyph set covers every word, sentence, pinyin, gloss, and
    # translation. QML sources add fixed labels such as the fallback message.
    text = args.lookup_data.read_text(encoding='utf-8') + string.printable
    text += ''.join(path.read_text(encoding='utf-8') for path in args.ui_sources)
    wanted = {ord(character) for character in text}
    font = TTFont(args.font, recalcTimestamp=False)
    available = set(font.getBestCmap())
    missing_han = [codepoint for codepoint in wanted - available
                   if 0x3400 <= codepoint <= 0x9fff]
    if missing_han:
        parser.error(f'Source font lacks {len(missing_han)} required Chinese glyphs')

    options = Options()
    options.layout_features = ['*']
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=wanted & available)
    subsetter.subset(font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output)
    print(f'Subset PDF popup font: {args.font.stat().st_size} -> '
          f'{args.output.stat().st_size} bytes, {len(wanted & available)} glyphs')


if __name__ == '__main__':
    main()
