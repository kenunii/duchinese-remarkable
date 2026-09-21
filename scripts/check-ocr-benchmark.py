#!/usr/bin/env python3
"""Compatibility entry point for the PDF import checks."""
from pathlib import Path
import runpy
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "pdf-import" / "src"))
if __name__ == "__main__":
    runpy.run_path(str(root / "pdf-import" / "checks" / "test_scoring.py"), run_name="__main__")
