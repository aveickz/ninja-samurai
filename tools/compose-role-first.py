# -*- coding: utf-8 -*-
"""Роль «Самурай» первого хода (карта #202): арт сгенерирован /img по арту роли «Самурай» с сасимоно «I»
за спиной (исходник с альфой — ref/banner/role-samurai-first-src2.png; знамя отдельно — ref/banner/banner-I.png).
Здесь — только посадка в формат арта роли 960×1536 на белом: знамя поднимается выше головы, поэтому фигура
уменьшена и прижата к низу, чтобы верхняя четверть (название карты) осталась пустой.
compose-role-first.py [scale=0.9] [bottom_margin_px=40]"""
import sys, os
import numpy as np
from PIL import Image
os.chdir(r'C:\ninja_samurai\cardboard')
K = float(sys.argv[1]) if len(sys.argv) > 1 else 0.9
M = int(sys.argv[2]) if len(sys.argv) > 2 else 40
W, H = 960, 1536
src = Image.open('ref/banner/role-samurai-first-src2.png').convert('RGBA')
bg = Image.new('RGBA', src.size, (255, 255, 255, 255)); bg.alpha_composite(src); bg = bg.convert('RGB')
a = np.array(bg); ink = (a < 235).any(axis=2); ys, xs = np.where(ink)
fig = bg.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
fig = fig.resize((round(fig.width * K), round(fig.height * K)), Image.LANCZOS)
out = Image.new('RGB', (W, H), (255, 255, 255))
out.paste(fig, ((W - fig.width) // 2, H - M - fig.height))
out.save('cards/card_role_samurai_first.png')
print('fig', fig.size, 'top at %.1f%%' % ((H - M - fig.height) / H * 100))
