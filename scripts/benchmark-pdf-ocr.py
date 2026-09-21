#!/usr/bin/env python3
"""Compatibility entry point; implementation lives in pdf-import/."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pdf-import" / "src"))
from duchinese_pdf.ocr import main

if __name__ == "__main__":
    main()
