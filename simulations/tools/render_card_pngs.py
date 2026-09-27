# -*- coding: utf-8 -*-
"""Small PNG previews of every card for the simulation viewer.

For each card the cardboard app is opened in embed mode (app.html?embed=<id>&lang=en)
by headless Chrome, the card is cropped by the embed geometry (same recipe as
tools/render-card-previews.py) and shrunk to a small PNG with rounded corners:

    simulations/media/cards/<id>.png            every non-trash card + roles + characters
    simulations/media/cards/back.png            deck back      (media/backs/default.png)
    simulations/media/cards/back-role.png       role back      (media/backs/role.png)
    simulations/media/cards/back-character.png  character back (media/backs/character.png)
    simulations/media/fig/poison.webp, trap.webp, banner.webp — figurines copied from rules/media/fig

Usage (from anywhere):
    py -3 simulations/tools/render_card_pngs.py            # only missing files
    py -3 simulations/tools/render_card_pngs.py --force    # everything again
    py -3 simulations/tools/render_card_pngs.py 1 48 137   # specific ids
    py -3 simulations/tools/render_card_pngs.py backs      # only backs + figurines

Output width is WIDTH px (default 160 → 160×256): the viewer shows cards at 60–90 px,
so 160 px stays crisp on 2× screens without bloating the folder.
"""
import json, os, shutil, subprocess, sys, tempfile
from PIL import Image, ImageChops, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
os.chdir(ROOT)
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
OUT = 'simulations/media/cards'
FIG_OUT = 'simulations/media/fig'
CARDS_JSON = 'simulations/data/cards.json'
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG_OUT, exist_ok=True)

SCALE = 2            # device scale factor for the screenshot
WIDTH = 160          # output width in px; height follows the 240×384 embed box (5:8)
HEIGHT = WIDTH * 8 // 5
RADIUS = 5           # rounded corners of the small PNG


def shoot(cid):
    tmp = os.path.join(tempfile.gettempdir(), f'simcard_{cid}.png')
    url = f'file:///{ROOT.replace(os.sep, "/")}/app.html?embed={cid}&lang=en'
    subprocess.run([CHROME, '--headless', '--disable-gpu', '--hide-scrollbars',
                    '--virtual-time-budget=6000', f'--force-device-scale-factor={SCALE}',
                    f'--screenshot={tmp}', '--window-size=600,600', url],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    im = Image.open(tmp).convert('RGB')
    # embed mode centres a 240×384 card box in the 600×600 window
    W, CW, CH = 600, 240, 384
    x0, y0 = (W - CW) // 2 * SCALE, (W - CH) // 2 * SCALE
    x1, y1 = x0 + CW * SCALE, y0 + CH * SCALE
    diff = ImageChops.difference(im, Image.new('RGB', im.size, (255, 255, 255))).convert('L').point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    if not box:
        raise RuntimeError(f'card {cid}: empty render')
    if box[0] < x0 - 2 or box[1] < y0 - 2 or box[2] > x1 + 2 or box[3] > y1 + 2:
        raise RuntimeError(f'card {cid}: render {box} outside the expected frame {(x0, y0, x1, y1)}')
    card = im.crop((x0, y0, x1, y1)).resize((WIDTH, HEIGHT), Image.LANCZOS)
    return rounded(card)


def rounded(card):
    mask = Image.new('L', card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), RADIUS, fill=255)
    card = card.convert('RGBA')
    card.putalpha(mask)
    return card


BACKS = {'back': 'default', 'back-role': 'role', 'back-character': 'character'}


def back(name, src_key):
    im = Image.open(f'media/backs/{src_key}.png').convert('RGB')
    w = round(im.height * 5 / 8)
    x0 = (im.width - w) // 2
    card = im.crop((x0, 0, x0 + w, im.height)).resize((WIDTH, HEIGHT), Image.LANCZOS)
    dst = f'{OUT}/{name}.png'
    rounded(card).save(dst, 'PNG', optimize=True)
    return dst


def figurines():
    out = []
    for name in ('poison', 'trap', 'banner', 'banner-green'):
        src = f'rules/media/fig/{name}.webp'
        if os.path.exists(src):
            dst = f'{FIG_OUT}/{name}.webp'
            shutil.copyfile(src, dst)
            out.append(dst)
    return out


def card_ids():
    cards = json.load(open(CARDS_JSON, encoding='utf-8'))
    return [c['id'] for c in cards if 'trash' not in (c.get('tags') or [])]


def main(argv):
    force = '--force' in argv
    args = [a for a in argv if a != '--force']
    if args == ['backs']:
        ids = []
    elif args:
        ids = [int(a) for a in args]
    else:
        ids = card_ids()
    done, skipped, failed = [], [], []
    if not args or args == ['backs']:
        for name, key in BACKS.items():
            dst = f'{OUT}/{name}.png'
            if force or not os.path.exists(dst):
                back(name, key); done.append(dst)
            else:
                skipped.append(dst)
        done += figurines()
    for cid in ids:
        dst = f'{OUT}/{cid}.png'
        if not force and os.path.exists(dst):
            skipped.append(dst); continue
        try:
            shoot(cid).save(dst, 'PNG', optimize=True)
            done.append(dst)
            print('ok', dst, flush=True)
        except Exception as e:  # noqa: BLE001
            failed.append((cid, str(e)))
            print('FAIL', cid, e, flush=True)
    print(f'done {len(done)}, skipped {len(skipped)}, failed {len(failed)}')
    for cid, err in failed:
        print('  failed', cid, err)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
