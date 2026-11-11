#!/usr/bin/env python3
"""Вывести текущую очередь перерисовки арта из KVDB картотеки."""

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ART_KEY_PREFIX = "art_status_"


def load_redraw_ids():
    html = (ROOT / "app.html").read_text(encoding="utf-8")
    match = re.search(r"window\.KVDB_CONFIG\s*=\s*\{(.*?)\};", html, re.DOTALL)
    config = match[1] if match else ""
    bucket = re.search(r"""^\s*bucket\s*:\s*(['"])([^'"]+)\1""", config, re.MULTILINE)
    if not bucket:
        raise ValueError("В app.html не задан KVDB_CONFIG.bucket")

    headers = {"Accept": "application/json"}
    token = re.search(r"""^\s*writeKey\s*:\s*(['"])([^'"]+)\1""", config, re.MULTILINE)
    if token:
        headers["Authorization"] = f"Bearer {token[2]}"

    query = urlencode({"prefix": ART_KEY_PREFIX, "values": "true", "format": "json"})
    url = f"https://kvdb.io/{quote(bucket[2], safe='')}/?{query}"
    with urlopen(Request(url, headers=headers), timeout=10) as response:
        entries = json.load(response)
    if not isinstance(entries, list):
        raise ValueError("KVDB вернул неожиданный формат списка")

    return {
        entry[0][len(ART_KEY_PREFIX):]
        for entry in entries
        if isinstance(entry, list) and len(entry) == 2
        and isinstance(entry[0], str) and entry[0].startswith(ART_KEY_PREFIX)
        and entry[1] == "requires_redraw"
    }


def load_card_titles():
    js = (
        "const fs = require('node:fs');"
        "const src = fs.readFileSync('js/cards.js', 'utf8');"
        "const cards = new Function(src + ';return CARDS;')();"
        "process.stdout.write(JSON.stringify(cards.map(({ id, title }) => ({ id, title }))));"
    )
    result = subprocess.run(
        ["node", "-e", js], cwd=ROOT, capture_output=True,
        encoding="utf-8", check=True, timeout=10,
    )
    return json.loads(result.stdout)


def main():
    try:
        redraw_ids = load_redraw_ids()
        cards = [card for card in load_card_titles() if str(card["id"]) in redraw_ids]
    except HTTPError as error:
        raise SystemExit(f"Не удалось прочитать очередь REDRAW: KVDB вернул HTTP {error.code}") from None
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Не удалось получить очередь REDRAW: {error}") from None

    print(f"Карт на перерисовку: {len(cards)}")
    for card in sorted(cards, key=lambda card: card["id"]):
        print(f"#{card['id']} — {card['title']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
