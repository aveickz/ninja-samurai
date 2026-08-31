#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка арта по трём критериям пригодности к офсету.

Критерии выведены 31.08.2026 замером шести забракованных карт против двух
починенных (см. SKILL.md, раздел «Пригодность к офсету»):

  светлое поле   >= 20%   доля кадра с L*>75 после прогона через Fogra39
  контраст теней >= 6.0   среднее |L - локальное среднее| внутри L*<35

Третий критерий из SKILL.md - «один субъект занимает >= трети кадра» - здесь
НЕ проверяется, и это осознанно. Прокси через крупнейшую связную область
одного тона проверен и отвергнут: удачная «Метка убийцы» получает по нему 20%
и заваливается, а перегруженный «Победный удар» - 37% и проходит. Метрика
меряет самое большое однотонное пятно, а не доминирующий субъект. Доминанту
проверяет глаз на превью (шаг 5 скилла).

Крупнейшее пятно печатается справочно - как индикатор дробности, не как зачёт.

ОСТОРОЖНО С МЕЛКИМ ИСХОДНИКОМ. Ширина нормируется до 900 px, но информацию это
не возвращает: арт, отрисованный мелким, физически не содержит того штриха,
который меряет контраст теней. Замер 01.09.2026: одна и та же картинка даёт
6.6 L* при ширине 1048 и 5.2 при 518 - то есть панель из раскладки `proto`
занижает контраст примерно на 1.4 L*. Обратный апскейл не помогает (проверено:
4.5 до и после). Поэтому на панелях прототипа смотри светлое поле и дробность,
а контраст теней засчитывай по финальному апскейлу. Скрипт сам предупреждает,
если исходник уже 800 px.

Использование:
    py -3 .claude/skills/cardimg/offset_check.py <файл.png> [ещё файлы...]

Выход 0 - все файлы прошли, 1 - хотя бы один завален.
"""
import pathlib
import sys

import numpy as np
from PIL import Image, ImageCms
from scipy import ndimage as nd

ROOT = pathlib.Path(__file__).resolve().parents[3]
ICC = ROOT / "profiles" / "Coated_Fogra39L_VIGC_300.icc"

LIGHT_MIN = 20.0   # % кадра
SHADOW_MIN = 6.0   # L*

_srgb = ImageCms.createProfile("sRGB")
_lab = ImageCms.createProfile("LAB")
_cmyk = ImageCms.ImageCmsProfile(str(ICC))
_to_cmyk = ImageCms.buildTransform(_srgb, _cmyk, "RGB", "CMYK",
                                   renderingIntent=ImageCms.Intent.PERCEPTUAL)
_to_rgb = ImageCms.buildTransform(_cmyk, _srgb, "CMYK", "RGB",
                                  renderingIntent=ImageCms.Intent.PERCEPTUAL)
_to_lab = ImageCms.buildTransform(_srgb, _lab, "RGB", "LAB")


def _flatten(im):
    """Альфу подкладываем на белую бумагу - печатать будут на белом."""
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        return bg
    return im.convert("RGB")


def measure(path):
    im = _flatten(Image.open(path))
    src_width = im.width
    # нормируем ширину: «мелочь» и контраст должны быть сравнимы между артами
    width = 900
    im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)

    cmyk = ImageCms.applyTransform(im, _to_cmyk)
    ink = np.asarray(cmyk).astype(float).sum(axis=2) / 255 * 100
    prn = ImageCms.applyTransform(cmyk, _to_rgb)
    L = np.asarray(ImageCms.applyTransform(prn, _to_lab))[:, :, 0].astype(float) * 100 / 255

    light = (L > 75).mean() * 100
    dark = L < 35
    shadow = float(np.abs(L - nd.uniform_filter(L, 5))[dark].mean()) if dark.mean() > 0.01 else 0.0

    # доминанта: крупнейшая связная область близких тонов (шаг 12 L*).
    # Каждый уровень размечаем отдельно - иначе nd.label слепляет все ненулевые
    # уровни в одну область и метрика всегда даёт 100%.
    levels = np.digitize(nd.median_filter(L, 5), np.arange(0, 100, 12))
    biggest = 0
    for lv in np.unique(levels):
        lab, n = nd.label(levels == lv)
        if n:
            biggest = max(biggest, int(np.bincount(lab.ravel())[1:].max()))
    dominant = biggest / L.size * 100

    muddy = ((L < 25) & (ink > 260)).mean() * 100
    return dict(light=light, shadow=shadow, dominant=dominant, src_width=src_width,
                muddy=muddy, ink95=float(np.percentile(ink, 95)), L=float(L.mean()))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    if not ICC.exists():
        print(f"нет ICC-профиля: {ICC}")
        return 2
    failed = False
    for arg in sys.argv[1:]:
        p = pathlib.Path(arg)
        if not p.exists():
            print(f"{p}: файла нет")
            failed = True
            continue
        m = measure(p)
        checks = [
            ("светлое поле", m["light"], LIGHT_MIN, "%"),
            ("контраст теней", m["shadow"], SHADOW_MIN, " L*"),
        ]
        bad = [n for n, v, lim, _ in checks if v < lim]
        verdict = "ПРОШЁЛ" if not bad else "ЗАВАЛЕН: " + ", ".join(bad)
        print(f"\n{p.name}  —  {verdict}")
        for name, value, limit, unit in checks:
            mark = "ok " if value >= limit else "МАЛО"
            print(f"  {mark} {name:16s} {value:6.1f}{unit}  (нужно >= {limit:.0f})")
        print(f"       справочно: мазня {m['muddy']:.1f}%, краска p95 {m['ink95']:.0f}%, "
              f"L* {m['L']:.1f}, крупнейшее пятно {m['dominant']:.0f}%")
        print("       доминанту (субъект >= трети кадра) проверь глазом - автоматом не меряется")
        if m["src_width"] < 800:
            print(f"       ВНИМАНИЕ: исходник {m['src_width']} px шириной - контраст теней "
                  f"занижен примерно на 1.4 L*; засчитывай его по финальному апскейлу")
        failed = failed or bool(bad)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
