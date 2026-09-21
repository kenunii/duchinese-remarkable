"""Command-line interface; heavyweight OCR dependencies load only on demand."""
import argparse
import importlib
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Prepare local PDF pages on the laptop. Page-range processing is available via batch.",
        epilog="Commands: ocr (rendered images), prepare (OCR geometry), annotate (LLM), assemble (annotated page), "
               "batch (rendered page range), retry (explicit failed-page rerun), merge (completed ranges), preview (offline page reader), score and viewer (five-page benchmark). Use COMMAND --help for options.",
    )
    parser.add_argument("command", choices=["ocr", "prepare", "annotate", "assemble", "batch", "retry", "merge", "preview", "score", "viewer"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sys.argv = [f"{parser.prog} {args.command}", *args.arguments]
    importlib.import_module(f"duchinese_pdf.{args.command}").main()


if __name__ == "__main__":
    main()
