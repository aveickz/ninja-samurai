#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Оценка артов колоды на пригодность к офсетной печати по Fogra39.

Критерий взят из скилла cardimg: карте нужна светлая доминанта, занимающая
бОльшую часть кадра, потому что офсет темнит и глушит — то, что на экране
выглядит нормально, на бумаге садится в грязь.

Считаем по каждому арту:
  L*_scr   — средняя светлота на экране (CIELAB L*, 0..100)
  L*_prn   — то же после прогона sRGB → Fogra39 CMYK → sRGB (PERCEPTUAL)
  drop     — насколько село: L*_scr - L*_prn
  dark%    — доля пикселей темнее L*<35 после печати (забитые краской массы)
  light%   — доля пикселей светлее L*>75 после печати (та самая доминанта)
  TAC      — средняя суммарная заливка краской C+M+Y+K, % (потолок профиля 300)
  ink95    — 95-й перцентиль TAC: сколько краски в самых плотных местах

Альфа-канал подкладываем на белую бумагу — печатать будут на белом.
"""
import csv
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageCms

# Использование:
#   py -3 tools/print-darkness.py . report.csv [cards.json]
# Третий аргумент необязателен: без него скрипт просто обходит cards/*.png,
# с ним подтягивает id/название/тираж карты из выгрузки cards.js.
ROOT = pathlib.Path(sys.argv[1]).resolve()
OUT_CSV = pathlib.Path(sys.argv[2])
CARDS_JSON = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else None
ICC = ROOT / "profiles" / "Coated_Fogra39L_VIGC_300.icc"

srgb = ImageCms.createProfile("sRGB")
cmyk = ImageCms.ImageCmsProfile(str(ICC))
to_cmyk = ImageCms.buildTransform(srgb, cmyk, "RGB", "CMYK",
                                  renderingIntent=ImageCms.Intent.PERCEPTUAL)
to_srgb = ImageCms.buildTransform(cmyk, srgb, "CMYK", "RGB",
                                  renderingIntent=ImageCms.Intent.PERCEPTUAL)


def lstar(rgb):
    """sRGB uint8 (H,W,3) → CIELAB L* (H,W). Настоящая светлота, не сумма каналов."""
    c = rgb.astype(np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    y = lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722
    return np.where(y > 0.008856, 116.0 * np.cbrt(y) - 16.0, 903.3 * y)


def analyse(path):
    im = Image.open(path)
    # Прозрачность кладём на белую бумагу.
    if im.mode in ("RGBA", "LA") or "transparency" in im.info:
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = im.convert("RGB")
    im.thumbnail((300, 300), Image.LANCZOS)   # статистики хватает с головой

    scr = np.asarray(im)
    im_cmyk = ImageCms.applyTransform(im, to_cmyk)
    prn = np.asarray(ImageCms.applyTransform(im_cmyk, to_srgb))

    l_scr = lstar(scr)
    l_prn = lstar(prn)
    ink = np.asarray(im_cmyk).astype(np.float64) / 255.0 * 100.0
    tac = ink.sum(axis=2)

    # «Мазня» — то, что физически схлопывается на офсете: тёмный пиксель
    # с предельной заливкой краской. Там уже нет тонального запаса,
    # соседние оттенки сливаются в одну плашку.
    muddy = ((l_prn < 25) & (tac > 260))
    dark_mask = l_prn < 35
    # Разброс светлоты внутри тёмных масс:低 = плоская чернильная плашка,
    # деталей в тени не осталось.
    shadow_sd = float(l_prn[dark_mask].std()) if dark_mask.any() else 0.0

    return {
        "muddy_pct": float(muddy.mean() * 100),
        "shadow_sd": shadow_sd,
        "mid_pct": float((l_prn > 60).mean() * 100),
        "L_scr": float(l_scr.mean()),
        "L_prn": float(l_prn.mean()),
        "drop": float(l_scr.mean() - l_prn.mean()),
        "dark_pct": float((l_prn < 35).mean() * 100),
        "light_pct": float((l_prn > 75).mean() * 100),
        "tac": float(tac.mean()),
        "ink95": float(np.percentile(tac, 95)),
    }


if CARDS_JSON:
    cards = json.load(open(CARDS_JSON, encoding="utf-8"))
else:
    # Без выгрузки cards.js метаданных нет — обходим арты как файлы.
    cards = [{"id": f.stem, "title": f.stem, "group": "", "qty": 1, "tags": [],
              "img": f"cards/{f.name}"}
             for f in sorted((ROOT / "cards").glob("*.png"))]

seen, rows = set(), []
for c in cards:
    img = c.get("img")
    if not img or img in seen:
        continue
    seen.add(img)
    p = ROOT / img
    if not p.is_file():
        continue
    m = analyse(p)
    m.update(id=c["id"], title=c["title"], group=c.get("group", ""),
             qty=c.get("qty", 1), img=img,
             tags=" ".join(c.get("tags", [])))
    rows.append(m)

rows.sort(key=lambda r: -r["muddy_pct"])
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "id", "title", "group", "qty", "tags", "img",
        "L_scr", "L_prn", "drop", "dark_pct", "mid_pct", "light_pct",
        "muddy_pct", "shadow_sd", "tac", "ink95"])
    w.writeheader()
    for r in rows:
        w.writerow({k: (round(v, 1) if isinstance(v, float) else v)
                    for k, v in r.items()})
print(f"обработано артов: {len(rows)} -> {OUT_CSV}")
