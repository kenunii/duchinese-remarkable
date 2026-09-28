#!/usr/bin/env python3
"""Package reviewed PDF lookup data for the native document-view test."""
import json
import hashlib
from pathlib import Path
import re
import subprocess
import sys

collection = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
pdf = Path(sys.argv[3]).resolve()
manifest = json.loads((collection / "manifest.json").read_text())
if manifest["status"] != "completed":
    raise SystemExit("Collection must be complete")
if hashlib.sha256(pdf.read_bytes()).hexdigest() != manifest["pdf_sha256"]:
    raise SystemExit("Source PDF hash does not match collection")

info = subprocess.check_output(
    ["pdfinfo", "-f", str(manifest["first_page"]), "-l", str(manifest["last_page"]), "-box", str(pdf)],
    text=True,
)
page_boxes = {}
for line in info.splitlines():
    match = re.match(r"Page\s+(\d+)\s+(MediaBox|CropBox):\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)", line)
    if match:
        page_boxes.setdefault(int(match[1]), {})[match[2]] = tuple(map(float, match.groups()[2:]))

pages = {}
for entry in manifest["pages"]:
    if entry["status"] != "validated":
        continue
    book = json.loads((collection / entry["book"]).read_text())
    number = entry["page"]
    if book["source_page"] != number:
        raise SystemExit(f"Page mismatch at {number}")
    boxes = page_boxes.get(number, {})
    if "MediaBox" not in boxes or "CropBox" not in boxes:
        raise SystemExit(f"Missing PDF boxes for page {number}")
    media = boxes["MediaBox"]
    crop = boxes["CropBox"]
    scale_x = book["image_width"] / (media[2] - media[0])
    scale_y = book["image_height"] / (media[3] - media[1])
    pages[number] = {
        "width": book["image_width"],
        "height": book["image_height"],
        "crop": [
            (crop[0] - media[0]) * scale_x,
            (media[3] - crop[3]) * scale_y,
            (crop[2] - crop[0]) * scale_x,
            (crop[3] - crop[1]) * scale_y,
        ],
        "sentences": [
            {"text": sentence["text"], "translation": sentence.get("translation", "")}
            for sentence in book["sentences"]
        ],
        "words": [
            {
                "hanzi": word["hanzi"],
                "pinyin": word.get("pinyin", ""),
                "meaning": word.get("meaning", ""),
                "sentence": word.get("sentence", -1),
                "boxes": word["boxes"],
            }
            for word in book["words"]
            if word.get("pinyin") and word["boxes"]
        ],
    }

output.mkdir(parents=True, exist_ok=True)
(output / "LookupData.js").write_text(
    ".pragma library\n"
    + "var pdfSha256 = " + json.dumps(manifest["pdf_sha256"]) + ";\n"
    + "var pages = " + json.dumps(pages, ensure_ascii=False, separators=(",", ":")) + ";\n"
)
print(f"Packaged {len(pages)} validated pages")
