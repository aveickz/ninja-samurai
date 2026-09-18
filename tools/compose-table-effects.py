# -*- coding: utf-8 -*-
"""Стол: у правого игрока вместо эффекта «Мастер боя» из фото — «Метка убийцы», над ней второй эффект
«Пыль в глаза» (столбик эффектов растёт от персонажа «вправо» с точки зрения игрока — вверх картинки);
плюс пример вмешательства союзника: верхний самурай — союзник атакующего — кладёт «Щитолом»
от себя к центру стола, ломая защиту правого ниндзя; плюс аура «Часовой» с фигуркой знамени
перед левым ниндзя, над его персонажем и ролью. Карты повёрнуты как остальные карты своего игрока (верх — к центру стола).
Аргументы: <src.webp> <out.webp>. Хелперы — как в compose-table-trap.py."""
import sys, os
from PIL import Image, ImageDraw, ImageFilter, ImageOps
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\ninja_samurai\cardboard')
src, out = sys.argv[1:3]
im = Image.open(src).convert('RGBA')
S = 4
CW, CH = 44, 70            # карта посреди стола; карты в зоне игрока на фото мельче — 37×60

def down(l): return l.resize((max(1, round(l.width / S)), max(1, round(l.height / S))), Image.LANCZOS)
def shadow(layer, blur=3, dx=2, dy=3, op=0.45):
    a = layer.split()[3]
    sh = Image.new('RGBA', (layer.width + 2*blur + abs(dx), layer.height + 2*blur + abs(dy)), (0, 0, 0, 0))
    sh.paste(Image.new('RGBA', layer.size, (20, 10, 0, int(255*op))), (blur + max(dx, 0), blur + max(dy, 0)), a)
    return sh.filter(ImageFilter.GaussianBlur(blur)), (blur, blur)
def paste_center(base, layer, cx, cy):
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
    ImageDraw.Draw(card).rounded_rectangle((0, 0, w-1, h-1), 3*S, outline=outline, width=S//2)
    return card
def rot(l, deg): return l.rotate(deg, Image.BICUBIC, expand=True)

# правый игрок: верх карт — влево (к центру), т.е. поворот на 90° против часовой
E = dict(w=37*S, h=60*S)
paste_center(im, down(rot(card_face('rules/media/cards/91.webp', **E), 90)), 877, 511)    # «Метка убийцы» — поверх «Мастера боя» с фото
paste_center(im, down(rot(card_face('rules/media/cards/97.webp', **E), 90)), 877, 469)    # «Пыль в глаза» — следующий эффект в столбике
# верхний игрок: верх карт — вниз (к центру), поворот на 180°; вмешательство — от него к центру стола
paste_center(im, down(rot(card_face('rules/media/cards/1031.webp'), 180)), 705, 447)  # «Щитолом» союзника — между его картами и сбросом

# левый игрок: аура — над персонажем и ролью (с его точки зрения «справа» — выше по картинке), с фигуркой знамени
paste_center(im, down(rot(card_face('rules/media/cards/1209.webp', w=37*S, h=60*S), -90)), 349, 497)
banner = Image.open('rules/media/fig/banner.webp').convert('RGBA')
banner = ImageOps.contain(banner, (22*S, 34*S), Image.LANCZOS).rotate(-90, Image.BICUBIC, expand=True)   # лежит «по игроку»: верх — к центру стола
paste_center(im, down(banner), 349, 494)

# холст шире на PAD слева — под дугу ауры за спиной левого ниндзя (table_fig.PAD)
PAD = 110
wide = Image.new('RGBA', (im.width + PAD, im.height), (0, 0, 0, 0)); wide.alpha_composite(im, (PAD, 0)); im = wide

im.save(out, 'WEBP', quality=90, method=6)
print('written', out, im.size)
