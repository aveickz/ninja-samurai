# -*- coding: utf-8 -*-
"""Стол: бутылка яда на карте роли правого игрока — повёрнута на 90° влево, как и его карты
(его «верх» — к центру стола). Под ней в исходнике (table-v1) лежит старый жетон яда: место
сначала восстанавливается из v1, потом бутылка кладётся так, чтобы жетон полностью закрыть.
Аргументы: <src.webp> <out.webp>"""
import sys, os
from PIL import Image, ImageDraw, ImageFilter, ImageOps
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\ninja_samurai\cardboard')
src, out = sys.argv[1:3]
im = Image.open(src).convert('RGBA')
S = 4
CX, CY = 879, 556

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

# 1. место бутылки — из исходника (там жетон яда, его закроет бутылка)
V1 = Image.open('rules/media/obsolete/table-v1.webp').convert('RGBA')
r = 26
box = (CX - r - 8, CY - r - 8, CX + r + 8, CY + r + 8)
tex = V1.crop(box)
m = Image.new('L', (tex.width*S, tex.height*S), 0)
ImageDraw.Draw(m).ellipse((8*S, 8*S, (8+2*r)*S, (8+2*r)*S), fill=255)
m = m.resize(tex.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(3))
tex.putalpha(m)
im.alpha_composite(tex, box[:2])

# 2. бутылка, повёрнутая на 90° против часовой (горлышком к центру стола)
bottle = Image.open('rules/media/fig/poison.webp').convert('RGBA')
bottle = ImageOps.contain(bottle, (36*S, 44*S), Image.LANCZOS).rotate(90, Image.BICUBIC, expand=True)
paste_center(im, down(bottle), CX, CY)

im.save(out, 'WEBP', quality=90, method=6)
print('written', out, im.size)
