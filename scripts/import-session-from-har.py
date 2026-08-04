#!/usr/bin/env python3
"""Import only the DuChinese session cookie from a browser HAR file."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

COOKIE_NAME = "_reader-server_session"


def cookie_from_header(value: str) -> str | None:
    for part in value.split(";"):
        name, separator, cookie_value = part.strip().partition("=")
        if separator and name == COOKIE_NAME and cookie_value:
            return f"{name}={cookie_value}"
    return None


def find_cookie(har: dict) -> str:
    found = None
    for entry in har.get("log", {}).get("entries", []):
        request = entry.get("request", {})
        if urlparse(request.get("url", "")).hostname != "duchinese.net":
            continue
        for header in request.get("headers", []):
            if header.get("name", "").lower() == "cookie":
                found = cookie_from_header(header.get("value", "")) or found
        for header in entry.get("response", {}).get("headers", []):
            if header.get("name", "").lower() == "set-cookie":
                found = cookie_from_header(header.get("value", "")) or found
    if not found:
        raise SystemExit(f"No {COOKIE_NAME} cookie found in HAR")
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("har", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".config/duchinese-remarkable/session.json",
    )
    args = parser.parse_args()

    with args.har.open(encoding="utf-8") as source:
        cookie = find_cookie(json.load(source))

    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(args.output.parent, 0o700)
    temporary = args.output.with_name(f".{args.output.name}.{os.getpid()}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump({"cookie": cookie}, destination)
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Imported DuChinese session into {args.output} (cookie value hidden)")


if __name__ == "__main__":
    main()
