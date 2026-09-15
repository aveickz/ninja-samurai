# -*- coding: utf-8 -*-
"""Рендерит превью карт для новой вёрстки правил (rules/rules-new*.html):
для каждого ID открывает картотеку в embed-режиме headless-хромом,
берёт карту с белой каймой вокруг (как при печати из картотеки), скругляет углы и кладёт PNG в
rules/media/cards/<id>.webp (RU) и <id>-en.webp (EN).

Зачем не iframe: при печати правил внутри iframe срабатывает print.css
картотеки и кадрирование разъезжается; статичная картинка печатается как есть.
Минус — превью надо перерисовать после правки карты (арт, текст, значки):
    py -3 tools/render-card-previews.py            # только недостающие
    py -3 tools/render-card-previews.py --force    # все заново
    py -3 tools/render-card-previews.py 1 70 48    # конкретные ID
"""
import os, sys, subprocess, tempfile
from PIL import Image, ImageChops, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
OUT = 'rules/media/cards'
os.makedirs(OUT, exist_ok=True)

# ID карт-примеров — те же, что в rules-new (см. tools/build-rules-new.py)
DEFAULT_IDS = [201, 200, 202, 137, 1, 32, 33, 31, 70, 48, 43, 41, 1166, 60, 135, 138,
               91, 116, 64, 121, 124, 1200, 1204, 125, 1165]

SCALE = 2          # device scale factor: 240px карты → 480px PNG
BLEED = 0          # px (в масштабе 1) белого поля вокруг карты, как на печати
RADIUS = 6         # скругление углов растра; белую рамку и основное скругление рисует CSS-бокс (.card-embed)


def shoot(cid, lang):
    tmp = os.path.join(tempfile.gettempdir(), f'card_{cid}_{lang}.png')
    url = f'file:///{ROOT.replace(os.sep, "/")}/app.html?embed={cid}' + ('&lang=en' if lang == 'en' else '')
    subprocess.run([CHROME, '--headless', '--disable-gpu', '--hide-scrollbars',
                    '--virtual-time-budget=6000', f'--force-device-scale-factor={SCALE}',
                    f'--screenshot={tmp}', '--window-size=600,600', url],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    im = Image.open(tmp).convert('RGB')
    # Карта в embed-режиме стоит по центру окна блоком 240×384 (при
    # --window-size=600,600 и масштабе 2 — это (360,216)-(840,984)).
    # Берём её целиком плюс белое поле BLEED вокруг — как на печати из
    # картотеки: карта с белой каймой под обрез и скруглёнными углами.
    diff = ImageChops.difference(im, Image.new('RGB', im.size, (255, 255, 255))).convert('L').point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    if not box:
        raise RuntimeError(f'card {cid}: empty render')
    x0, y0, x1, y1 = box
    k = BLEED * SCALE
    card = im.crop((x0 - k, y0 - k, x1 + k, y1 + k))
    # скруглённые углы → прозрачность (webp с альфой)
    mask = Image.new('L', card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), RADIUS, fill=255)
    card = card.convert('RGBA'); card.putalpha(mask)
    dst = f'{OUT}/{cid}{"-en" if lang == "en" else ""}.webp'
    card.save(dst, 'WEBP', quality=86, method=6)
    return dst, card.size


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--force']
    force = '--force' in sys.argv
    ids = [int(a) for a in args] or DEFAULT_IDS
    for cid in ids:
        for lang in ('ru', 'en'):
            dst = f'{OUT}/{cid}{"-en" if lang == "en" else ""}.webp'
            if os.path.exists(dst) and not force and not args:
                continue
            print(shoot(cid, lang))
