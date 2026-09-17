# -*- coding: utf-8 -*-
"""Стол: ловушка левого игрока — рубашка вверх, перпендикулярно карте персонажа
(портретом, без наклона), ровно над персонажем и ролью; сверху — фигурка макибиси
(rules/media/fig/trap.webp). Прежний капкан боком между сердцами и колодой закрашивается
клоном текстуры. Аргументы: <src.webp> <out.webp>. Хелперы — из compose-table-backs.py."""
import sys, os, runpy
from PIL import Image, ImageDraw, ImageFilter, ImageOps
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\ninja_samurai\cardboard')
src, out = sys.argv[1:3]
im = Image.open(src).convert('RGBA')
S = 4
BACK = 'rules/media/cards/back.webp'

def down(l): return l.resize((max(1, round(l.width / S)), max(1, round(l.height / S))), Image.LANCZOS)
def shadow(layer, blur=3, dx=2, dy=3, op=0.45):
    a = layer.split()[3]
    sh = Image.new('RGBA', (layer.width + 2*blur + abs(dx), layer.height + 2*blur + abs(dy)), (0, 0, 0, 0))
    sh.paste(Image.new('RGBA', layer.size, (20, 10, 0, int(255*op))), (blur + max(dx, 0), blur + max(dy, 0)), a)
    return sh.filter(ImageFilter.GaussianBlur(blur)), (blur, blur)
def paste_center(base, layer, cx, cy, with_shadow=True):
    if with_shadow:
        sh, off = shadow(layer)
        base.alpha_composite(sh, (int(round(cx - layer.width/2 - off[0])), int(round(cy - layer.height/2 - off[1]))))
    base.alpha_composite(layer, (int(round(cx - layer.width/2)), int(round(cy - layer.height/2))))

def card_face(webp, w, h, b=1*S, outline=(120, 100, 70, 255)):
    art = Image.open(webp).convert('RGBA')
    tw = round(art.height * (w - 2*b) / (h - 2*b))
    if art.width > tw:
        x0 = (art.width - tw) // 2; art = art.crop((x0, 0, x0 + tw, art.height))
    art = art.resize((w - 2*b, h - 2*b), Image.LANCZOS)
    card = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w-1, h-1), 3*S, fill=255)
    card.paste((246, 240, 228, 255), (0, 0, w, h), m)
    card.alpha_composite(art, (b, b))
    d = ImageDraw.Draw(card); d.rounded_rectangle((0, 0, w-1, h-1), 3*S, outline=outline, width=S//2)
    return card

# прежняя ловушка боком (между сердцами и колодой) — на её место кладётся тот же
# кусок стола из исходника без дорисовок (media/obsolete/table-v1.webp), с мягкой маской
V1 = Image.open('rules/media/obsolete/table-v1.webp').convert('RGBA')
def restore(cx, cy, rx, ry):
    box = (int(cx - rx - 10), int(cy - ry - 10), int(cx + rx + 10), int(cy + ry + 10))
    tex = V1.crop(box)
    m = Image.new('L', (tex.width*S, tex.height*S), 0)
    ImageDraw.Draw(m).ellipse((10*S, 10*S, (10+2*rx)*S, (10+2*ry)*S), fill=255)
    m = m.resize(tex.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(4))
    tex.putalpha(m)
    im.alpha_composite(tex, box[:2])
restore(452, 560, 44, 44)

# новая: портретом, «над» персонажем и ролью с точки зрения игрока — ближе к центру стола,
# правее его карт и сердец, на месте прежнего капкана
TX, TY = 452, 580
trapback = down(card_face(BACK, 44*S, 70*S))
paste_center(im, trapback, TX, TY)
fig = Image.open('rules/media/fig/trap.webp').convert('RGBA')   # чёрная, как настоящая
fig = ImageOps.contain(fig, (34*S, 34*S), Image.LANCZOS)
# на чёрной туши рубашки чёрная фигурка пропадает — под неё светлый ореол (блик бумаги)
halo = Image.new('RGBA', (fig.width + 6*S, fig.height + 6*S), (0, 0, 0, 0))
halo.paste((255, 252, 240, 210), (3*S, 3*S, 3*S + fig.width, 3*S + fig.height), fig.getchannel('A'))
halo = halo.filter(ImageFilter.GaussianBlur(2*S))
paste_center(im, down(halo), TX, TY - 1, with_shadow=False)
paste_center(im, down(fig), TX, TY - 1)

im.save(out, 'WEBP', quality=90, method=6)
print('written', out, im.size)
