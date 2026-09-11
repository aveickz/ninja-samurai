# -*- coding: utf-8 -*-
"""
Белая гуашевая подложка под бейдж второго типа: media/icon_badge*.png.

Три слоя бейджа: эта подложка снизу, поверх — ровный CSS-круг цвета
группы, сверху — SVG-силуэт. Подложка одна на все группы, потому что
цвет в ней не живёт.

Две версии одной формы:
  icon_badge.png       — мазок ЛЕЖИТ на карте: белый круг и мягкая
                         тень вниз-вправо, запечённая в PNG;
  icon_badge_inset.png — мазок ВРЕЗАН в карту, как трещина: тень
                         внутри по верхней кромке, свет по нижней.

Кромка рваная, чернильная — та же, что у обода значка типа и рамки
карты: один набор параметров шума, чтобы все три читались одной
кистью. Первая версия была гуашевой, с гладкой «дышащей» кромкой, и
рядом с рамкой выглядела чужой.
"""
import sys
import zlib
import numpy as np
from PIL import Image
from scipy import ndimage

SIZE = 320
# Радиус мазка. 118 оставлял бейдж на 74% холста, и на карте он
# усыхал до 24 px. 140 — почти в край: остаток ровно под тень
# (сдвиг 7 + размытие 5 сигм).
R = 132.0                    # + до 14 px рванины + 6 px туши, дальше тень
SHADOW_DX, SHADOW_DY = 5, 7  # тень вниз-вправо, свет сверху-слева
SHADOW_SIGMA, SHADOW_A = 4.0, 0.55


def ring_noise(n, sigma, rng):
    v = ndimage.gaussian_filter1d(rng.standard_normal(n).astype(np.float32),
                                  sigma, mode="wrap")
    return v / (v.std() + 1e-6)


# Параметры кромки — те же, что у обода значка типа (type_disc.py):
# кромка бейджа обязана рваться той же рукой, что полукруг под
# названием и рамка карты.
EDGE = dict(lf=110, lf_amp=0.009, hf=15, hf_amp=0.011,
            warp=70, warp_sigma=140, mod=200, mod_base=0.30, mod_amp=1.25,
            ro_lo=5.0, ro_hi=14.0)


def blob_alpha(seed, grow=0.0):
    """Альфа белого круга с рваной чернильной кромкой, 0..1."""
    rng = np.random.default_rng(seed)
    c = (SIZE - 1) / 2.0
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    r = np.hypot(x - c, y - c)
    th = np.arctan2(y - c, x - c)
    n_ang = 2048
    idx = ((th + np.pi) / (2 * np.pi) * n_ang).astype(np.int32) % n_ang

    # Шум с постоянной сигмой даёт ровные фестоны по всему кругу — ту
    # же «гребёнку», что лезла на рамке. Лечится домен-варпом (сдвигаем
    # саму координату шума другим шумом) и амплитудной модуляцией (шум
    # то громче, то тише вдоль кромки).
    pos = np.arange(n_ang, dtype=np.float32)
    warp = ring_noise(n_ang, EDGE["warp_sigma"], rng) * EDGE["warp"]
    hf = np.interp((pos + warp) % n_ang, pos,
                   ring_noise(n_ang, EDGE["hf"], rng), period=n_ang)
    amod = np.clip(EDGE["mod_base"]
                   + ring_noise(n_ang, EDGE["mod"], rng) * EDGE["mod_amp"],
                   0.0, None)
    lf = ring_noise(n_ang, EDGE["lf"], rng)
    edge = (lf * EDGE["lf_amp"] + hf * EDGE["hf_amp"] * amod) * SIZE
    ro = np.clip(R + edge, R - EDGE["ro_lo"], R + EDGE["ro_hi"]) + grow
    # Переход кромки в 2/3 px вместо пикселя: после ужатия холста в
    # девять раз обычный антиалиас читался мыльной каймой.
    return np.clip((ro[idx] - r + 0.5) * 1.5, 0.0, 1.0)


def save(rgb, alpha, path):
    out = np.zeros((SIZE, SIZE, 4), np.uint8)
    out[..., :3] = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    out[..., 3] = (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(path)


def main():
    outdir = sys.argv[1].rstrip("/\\")
    a = blob_alpha(zlib.crc32(b"badge-gouache"))

    # ── лежит на карте: тень под мазком ─────────────────────────────
    sh = ndimage.shift(a, (SHADOW_DY, SHADOW_DX), order=1, mode="constant")
    sh = ndimage.gaussian_filter(sh, SHADOW_SIGMA) * SHADOW_A
    # композит: чёрная тень снизу, белый мазок сверху (premultiplied)
    alpha = a + sh * (1 - a)
    white = a                                  # белого столько, сколько мазка
    rgb = np.zeros((SIZE, SIZE, 3), np.float32)
    nz = alpha > 1e-6
    for k in range(3):
        rgb[..., k][nz] = white[nz] / alpha[nz]
    save(rgb, alpha, f"{outdir}/icon_badge.png")

    # ── врезан в карту: белый мазок без тени + отдельный слой тени ──
    # Подложка тут чисто белая: тень врезки лежит в ДРУГОМ файле,
    # icon_badge_shade.png, который в разметке идёт ПОВЕРХ цветной
    # заливки. Иначе тень падала бы только на белый ободок, а заливка
    # оставалась плоской — и врезка на 32 px не читалась вовсе.
    save(np.ones((SIZE, SIZE, 3), np.float32), a, f"{outdir}/icon_badge_inset.png")

    # Тень по верхней кромке внутрь. Сигма 7: при 14 полоса выходила
    # ~20 px на холсте и на карте читалась мутным градиентом, а не
    # ребром врезки; при 7 это ~10 px, то есть ~1 px резкого ребра на
    # 32-пиксельном бейдже. Плотность поднята, чтобы узкая полоса не
    # потеряла в весе. Снизу изнутри — слабый блик освещённой стенки.
    sm = ndimage.gaussian_filter(a, 7.0)
    gy, gx = np.gradient(sm)
    mag = np.hypot(gx, gy)
    proj = np.zeros_like(mag)
    nz = mag > 1e-6
    proj[nz] = (gx[nz] * -0.7071 + gy[nz] * -0.7071) / mag[nz]
    rim = np.clip(mag / mag.max(), 0, 1) * a
    dark = np.clip(-proj, 0, 1) * rim * 0.82
    light = np.clip(proj, 0, 1) * rim * 0.35
    take_light = light > dark
    shade = np.zeros((SIZE, SIZE, 4), np.float32)
    shade[..., :3] = np.where(take_light[..., None], 1.0, 0.0)
    shade[..., 3] = np.where(take_light, light, dark)
    save(shade[..., :3], shade[..., 3], f"{outdir}/icon_badge_shade.png")

    # ── чёрный чернильный контур: обод снаружи белого ───────────────
    # Наружная кромка обода — та же рваная, что у белого, но чуть
    # шире; внутренняя совпадает с белым. Получается кольцо туши вокруг
    # мазка, как обод у значка типа. Два файла: с тенью и без.
    INK = 6.0
    ring_alpha = blob_alpha(zlib.crc32(b"badge-gouache"), grow=INK)
    ink = np.clip(ring_alpha - a, 0.0, 1.0)
    for name, with_shadow in (("icon_badge_outline.png", True),
                              ("icon_badge_outline_flat.png", False)):
        base_a = np.clip(a + ink, 0, 1)                       # белое + тушь
        if with_shadow:
            sh2 = ndimage.shift(base_a, (SHADOW_DY, SHADOW_DX), order=1,
                                mode="constant")
            sh2 = ndimage.gaussian_filter(sh2, SHADOW_SIGMA) * SHADOW_A
        else:
            sh2 = np.zeros_like(base_a)
        alpha3 = base_a + sh2 * (1 - base_a)
        rgb3 = np.zeros((SIZE, SIZE, 3), np.float32)
        nz3 = alpha3 > 1e-6
        # белого ровно столько, сколько мазка; тушь и тень чёрные
        for k in range(3):
            rgb3[..., k][nz3] = a[nz3] / alpha3[nz3]
        save(rgb3, alpha3, f"{outdir}/{name}")

    # окно под CSS-заливку. Заливка обязана лежать под белым и в самом
    # узком месте рванины: от минимального радиуса кромки отступаем на
    # ободок.
    rim_px = 20.0
    fill_r = (R - EDGE["ro_lo"]) - rim_px
    print(f"мазок R={R:.0f} px из {SIZE}; заливка r={fill_r:.0f} px "
          f"-> inset {(SIZE / 2 - fill_r) / SIZE * 100:.1f}%; "
          f"ободок {rim_px:.0f} px; тушь снаружи {INK:.0f} px")


main()
