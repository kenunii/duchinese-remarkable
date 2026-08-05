#!/usr/bin/env python3
"""Create a DuChinese mobile API session without storing the password."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "https://api.duchinese.app/api/v2"
USER_AGENT = "duchinese-remarkable/0.1"


def request_json(path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API_URL + path,
        data=data,
        method="GET" if data is None else "POST",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get("error")
        except (json.JSONDecodeError, AttributeError, OSError):
            message = None
        raise RuntimeError(message or f"DuChinese returned HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach DuChinese: {error.reason}") from None
    if not isinstance(value, dict):
        raise RuntimeError("DuChinese returned an unexpected response")
    return value


def save_session(path: Path, uuid: str, token: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".mobile-session-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump({"uuid": uuid, "token": token}, output)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".config/duchinese-remarkable/mobile-session.json",
    )
    args = parser.parse_args()

    email = input("DuChinese email: ").strip()
    password = getpass.getpass("DuChinese password: ")
    if not email or not password:
        raise SystemExit("Email and password are required")

    vendor_id = secrets.token_hex(8)
    device = request_json(f"/user_devices/new?vendor_id={vendor_id}")
    uuid = device.get("uuid")
    token = device.get("token")
    if not isinstance(uuid, str) or not uuid or not isinstance(token, str) or not token:
        raise SystemExit("DuChinese did not return mobile device credentials")

    request_json("/user_devices", {"user": {"uuid": uuid, "token": token}})

    signed_in = request_json(
        "/users/sign_in",
        {"user": {"uuid": uuid, "token": token, "email": email, "password": password}},
    )
    if not isinstance(signed_in.get("email"), str):
        raise SystemExit("DuChinese login succeeded with an unexpected response")
    save_session(args.output, uuid, token)
    print(f"Mobile session saved to {args.output} (credentials hidden)")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
