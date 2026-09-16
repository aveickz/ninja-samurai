# -*- coding: utf-8 -*-
"""Дорисовка стола: бутылка яда вместо жетона у правого игрока, карта защиты
у него же напротив атаки, ловушка (рубашка + фигурка) у левого игрока.
Слои строятся в 4× и поворачиваются до уменьшения — края чистые.
Аргументы: <src.webp> <poison.png> <trap.png> <out.webp>"""
import sys, os
from PIL import Image, ImageDraw, ImageFilter, ImageOps
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\ninja_samurai\cardboard')
src, poison_png, trap_png, out = sys.argv[1:5]

im = Image.open(src).convert('RGBA')
S = 4                       # внутренний масштаб построения слоёв
CW, CH = 44, 70             # карта на столе, px картинки

def alpha_bbox_crop(img):
    a = img.split()[3].point(lambda v: 255 if v > 24 else 0)
    return img.crop(a.getbbox())

def shadow(layer, blur=3, dx=2, dy=3, op=0.45):
    a = layer.split()[3]
    sh = Image.new('RGBA', (layer.width + 2*blur + abs(dx), layer.height + 2*blur + abs(dy)), (0, 0, 0, 0))
    black = Image.new('RGBA', layer.size, (20, 10, 0, int(255*op)))
    sh.paste(black, (blur + max(dx, 0), blur + max(dy, 0)), a)
    return sh.filter(ImageFilter.GaussianBlur(blur)), (blur, blur)

def paste_center(base, layer, cx, cy, with_shadow=True):
    if with_shadow:
        sh, off = shadow(layer)
        base.alpha_composite(sh, (int(cx - layer.width/2 - off[0]), int(cy - layer.height/2 - off[1])))
    base.alpha_composite(layer, (int(cx - layer.width/2), int(cy - layer.height/2)))

def down(layer):
    return layer.resize((max(1, round(layer.width / S)), max(1, round(layer.height / S))), Image.LANCZOS)

def rot(layer, deg):
    return layer.rotate(deg, Image.BICUBIC, expand=True)

def card_face(webp, w=CW*S, h=CH*S, b=1*S):
    """Карта с тонкой кремовой каймой и скруглением, как остальные на столе (4×).
    Растр шире 5:8 (рубашка 1052×1494) обрезается по центру до пропорции карты."""
    art = Image.open(webp).convert('RGBA')
    tw = round(art.height * (w - 2*b) / (h - 2*b))
    if art.width > tw:
        x0 = (art.width - tw) // 2; art = art.crop((x0, 0, x0 + tw, art.height))
    art = art.resize((w - 2*b, h - 2*b), Image.LANCZOS)
    card = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w-1, h-1), 3*S, fill=255)
    card.paste((240, 230, 210, 255), (0, 0, w, h), m)
    card.alpha_composite(art, (b, b))
    return card

def card_back(w=CW*S, h=CH*S):
    """Рубашка в стиле рисунка: коричневая со светлым контуром (4×)."""
    big = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle((0, 0, w-1, h-1), 3*S, fill=(100, 66, 18, 255), outline=(214, 180, 130, 255), width=S)
    d.rounded_rectangle((3*S, 3*S, w-1-3*S, h-1-3*S), 2*S, outline=(140, 100, 45, 255), width=S//2)
    return big

# --- 1. Карта защиты правого игрока: перед ним, рядом с выложенной атакой,
#        повёрнута как его карты (лежит боком к нижнему игроку) ---
defense = down(rot(card_face('rules/media/cards/48.webp'), 90 + 6))
paste_center(im, defense, 806, 704)

# --- 2. Ловушка левого игрока: настоящая рубашка (media/backs/default_real.png)
#        боком + фигурка капкана сверху ---
back = down(rot(card_face('media/backs/default_real.png'), 90 - 8))
paste_center(im, back, 452, 560)          # рядом с картами левого ниндзя, между сердцами и колодой
trap = alpha_bbox_crop(Image.open(trap_png).convert('RGBA'))
trap = ImageOps.contain(trap, (40*S, 40*S), Image.LANCZOS)
paste_center(im, down(trap), 452, 558)

# --- 3. Бутылка яда вместо жетона на карте роли правого игрока ---
poison = alpha_bbox_crop(Image.open(poison_png).convert('RGBA'))
poison = ImageOps.contain(poison, (36*S, 40*S), Image.LANCZOS)
paste_center(im, down(poison), 879, 556)

im.save(out, 'WEBP', quality=90, method=6)
print('written', out, im.size)
