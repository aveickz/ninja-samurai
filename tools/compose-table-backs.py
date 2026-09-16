# -*- coding: utf-8 -*-
"""Стол: все рубашки (колода, веера рук, карта ловушки) — новая белая рубашка с тушью
(rules/media/cards/back.webp = media/backs/default.png в 5:8). Старые нарисованные
веера и колода закрашиваются клоном текстуры стола, поверх кладутся новые слои.
Слои строятся в 4× и поворачиваются до уменьшения. Аргументы: <src.webp> <out.webp>"""
import sys, os, math
from PIL import Image, ImageDraw, ImageFilter, ImageOps
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\ninja_samurai\cardboard')
src, out = sys.argv[1:3]
im = Image.open(src).convert('RGBA')
S = 4
CW, CH = 40, 64            # карта в руке / колоде, px картинки
BACK = 'rules/media/cards/back.webp'

def down(l): return l.resize((max(1, round(l.width / S)), max(1, round(l.height / S))), Image.LANCZOS)
def rot(l, deg): return l.rotate(deg, Image.BICUBIC, expand=True)
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

def card_face(webp, w=CW*S, h=CH*S, b=1*S, outline=(120, 100, 70, 255)):
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

# --- клон текстуры стола: чистый кусок без предметов, кладём с мягкой эллиптической маской ---
PATCH = im.crop((330, 330, 470, 470))
def clean(cx, cy, rx, ry, ang=0):
    """Закрасить эллипс (центр, полуоси, поворот) текстурой стола."""
    w, h = int(rx*2 + 20), int(ry*2 + 20)
    tex = Image.new('RGBA', (w, h))
    for y in range(0, h, PATCH.height):
        for x in range(0, w, PATCH.width):
            tex.paste(PATCH, (x, y))
    m = Image.new('L', (w*S, h*S), 0)
    ImageDraw.Draw(m).ellipse((10*S, 10*S, (10+2*rx)*S, (10+2*ry)*S), fill=255)
    m = m.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(2))
    if ang:
        tex = tex.rotate(ang, Image.BICUBIC, expand=False); m = m.rotate(ang, Image.BICUBIC, expand=False)
    tex.putalpha(m)
    im.alpha_composite(tex, (int(cx - w/2), int(cy - h/2)))

BACKCARD = card_face(BACK)

def fan(cards):
    """cards: [(cx, cy, angle)] — снизу вверх по стопке."""
    for cx, cy, a in cards:
        paste_center(im, down(rot(BACKCARD, a)), cx, cy)

# ---------- 1. руки: четыре веера ----------
HANDS = {
 'top':    dict(clean=(716, 290, 52, 38, 0),   cards=[(699, 281, -40), (715, 286, -36), (731, 291, -32), (747, 296, -28)]),
 'left':   dict(clean=(300, 690, 40, 52, 0),   cards=[(287, 668, -35), (295, 683, -32), (303, 698, -29), (311, 713, -26)]),
 'right':  dict(clean=(930, 695, 46, 56, 0),   cards=[(936, 668, -60), (931, 685, -56), (928, 702, -52), (927, 719, -48)]),
 'bottom': dict(clean=(482, 878, 54, 40, 0),   cards=[(462, 878, -12), (482, 880, -8), (502, 880, -4)]),
}
for k, h in HANDS.items():
    clean(*h['clean']); fan(h['cards'])

# ---------- 2. колода в центре: стопка ----------
clean(578, 565, 34, 46)
DW, DH = 44, 70
deckcard = card_face(BACK, DW*S, DH*S)
for i in range(6, 0, -1):     # кромки стопки: смещённые слои, потемнее
    edge = Image.new('RGBA', deckcard.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle((0, 0, deckcard.width-1, deckcard.height-1), 3*S, fill=(200, 190, 172, 255), outline=(120, 100, 70, 255), width=S//2)
    paste_center(im, down(edge), 578 + i*0.6, 565 + i*0.8, with_shadow=(i == 6))
paste_center(im, down(deckcard), 578, 565, with_shadow=False)

# ---------- 3. ловушка левого игрока: та же рубашка боком + фигурка капкана ----------
trapback = down(rot(card_face(BACK, 44*S, 70*S), 90 - 8))
paste_center(im, trapback, 452, 560)
trap = Image.open('rules/media/fig/trap.webp').convert('RGBA')
trap = ImageOps.contain(trap, (40*S, 40*S), Image.LANCZOS)
paste_center(im, down(trap), 452, 558)

im.save(out, 'WEBP', quality=90, method=6)
print('written', out, im.size)
