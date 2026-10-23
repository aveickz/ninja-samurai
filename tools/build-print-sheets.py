# -*- coding: utf-8 -*-
"""PDF колоды для печати в типографии: лица и рубашка отдельными файлами.

Требования ottisk.com (общие для открыток, листовок и визиток,
https://ottisk.com/knowledgebase/requirement/): PDF, CMYK FOGRA39, 300 ppi,
все слои сведены в один Background, эффекты растрированы, шрифты в кривых,
без рамок по периметру, линии не тоньше 0,2 мм. Ответ менеджера 20.10.2026:
спуск на листы SRA3 типография делает сама, поэтому нужны отдельные файлы
«в размер карты 56 × 87 мм» — лица и одна рубашка; пунктир не нужен (он
пропечатается); безопасное поле от рамки до реза — не меньше 5 мм, иначе
при погрешности резки 1–2 мм рамки выйдут несимметричными. Отсюда:

  • Каждая страница PDF — ОДНА CMYK-картинка и больше ничего: ни шрифтов,
    ни кривых, ни прозрачности. «Свести в один слой» выполнено буквально.
  • Карта снимается headless-хромом с картотеки (app.html?embed=<id>) в
    печатном режиме — под @media print, как при печати из картотеки:
    шрифты карты заданы в pt, и экранная карта шириной 240 px разложила бы
    текст иначе, чем бумажная.
  • Обрезной формат карты TRIM — 661×1028 px = 56 × 87 мм. Рамка карты
    (mask_*.png, 611×978 px) уменьшена так, чтобы от неё до реза было не
    меньше CUT_SAFE_MM (5 мм) со всех сторон: ≈ 0,885, рамка 45,8 × 73,3 мм,
    поля 5,1 мм по бокам и 6,9 мм сверху и снизу. Снимается сразу в этом
    размере (device scale хрома), а не ужимается потом, — текст чётче.
  • Рисунок рубашки — BACK_SCALE (90 %) того же кадра, по центру.
  • sRGB → FOGRA39 тем же профилем и интентом (perceptual), что
    CMYK-превью картотеки (tools/bake-cmyk-css.py).

Раскладки (--layout):

  card  (по умолчанию) — под типографию: страница = карта 56 × 87 мм, одна
        карта на странице, с --qty повторы идут подряд; рубашка — файл из
        одной страницы того же размера. TrimBox = MediaBox: поля карты белые,
        вылет не нужен. Без пунктира и меток. Скрипт проверяет, что ни у
        одной карты краска не подходит к резу ближе 5 мм.
  sheet — для домашней печати: листы A4 по 9 карт, карты с промежутком
        GAP (6 мм), по линии реза лица — серый пунктир (50 % K, 0,26 мм) со
        скруглёнными углами R 3 мм, метки реза и кресты приводки в 100K,
        подпись листа. Сетка и метки симметричны до пикселя, лист рубашек
        ложится на любой лист лиц при перевороте по длинной стороне —
        скрипт проверяет и это. Страница = A4 + 5 мм вылета, TrimBox = A4.

    py -3 tools/build-print-sheets.py                         # тест: EN, по 5 разных названий из группы
    py -3 tools/build-print-sheets.py --lang ru --per-group 0 # вся колода, по карте каждого вида
    py -3 tools/build-print-sheets.py --per-group 0 --qty     # вся колода в количестве qty
    py -3 tools/build-print-sheets.py --ids 1 49 57           # конкретные карты
    py -3 tools/build-print-sheets.py --per-group 0 --qty --drafts --exclude 319 321   # с черновиками, без недоделанных
    py -3 tools/build-print-sheets.py --layout sheet          # листы A4 3×3 для домашней печати
    py -3 tools/build-print-sheets.py --preview DIR           # + PNG soft-proof
    py -3 tools/build-print-sheets.py --split print/X.pdf     # порезать готовый PDF на части до 20 МБ под почту

Пишет print/cards_<lang>[_test<N>]_<дата>_faces.pdf и …_back.pdf
(раскладка sheet — print/sheets_…_faces.pdf и …_backs.pdf).
"""
import argparse, datetime, io, math, os, re, sys, zlib

import numpy as np
from PIL import Image, ImageChops, ImageCms, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
ICC = 'profiles/Coated_Fogra39L_VIGC_300.icc'
BACK = 'media/backs/default.png'
LABEL_FONT = r'C:\Windows\Fonts\segoeui.ttf'

NON_PLAYABLE = ('role', 'character')

# Все размеры — в пикселях при 300 ppi; при --dpi 600 умножаются на k=2.
CARD = (611, 978)        # рамка карты = mask_*.png, 51,73 × 82,80 мм в натуральную величину
TRIM = (661, 1028)       # обрезной формат карты в px, 55,96 × 87,04 мм ≈ 56 × 87
TRIM_MM = (56.0, 87.0)   # …а страница PDF раскладки card — ровно 56 × 87 мм
CUT_SAFE_MM = 5.0        # от рамки до реза — не меньше (ottisk: погрешность резки 1–2 мм)
BACK_SCALE = 0.9         # рисунок рубашки — 90 % кадра, по центру
# раскладка sheet
COLS, ROWS = 3, 3
A4_MM = (210.0, 297.0)
SAFE_MM = 5.0            # «влёты» листа: ничего ближе к краю A4
MARK_OFF_MM = 2.0        # метка реза — не ближе 2 мм к карте
LINE_MM = 0.2            # минимум ottisk для одноцветной линии
GAP_MM = 6.0             # белый промежуток между картами
RADIUS_MM = 3.0          # скругление углов карты, как у игральных карт
OUTLINE_MM = 25.4 / 96   # пунктир по линии реза: 1 CSS-пиксель = 0,26 мм
OUTLINE_K = 0.5          # …серый, 50 % K
DASH_MM, DASH_GAP_MM = 1.5, 1.0

# Печатный режим картотеки, приколоченный к пикселю: карта в (0,0),
# ширина 611/300 дюйма, без пунктира-направляющей из print.css.
PRINT_CSS = """
body.embed-mode { padding: 0 !important; margin: 0 !important; display: block !important; min-height: 0 !important; }
body.embed-mode .card-item:not(.card--hidden) {
  position: fixed !important; left: 0 !important; top: 0 !important; margin: 0 !important;
  width: calc(611in / 300) !important; outline: none !important; }
body.embed-mode .card-item .card { width: calc(611in / 300) !important; box-shadow: none !important; border-radius: 0 !important; }
"""
INIT_JS = ("document.addEventListener('DOMContentLoaded', function () {"
           " var s = document.createElement('style'); s.textContent = %r;"
           " document.head.appendChild(s); });")

READY_JS = """() => document.fonts.status === 'loaded'
  && [...document.images].every(i => i.complete)
  && !!document.querySelector('.card-item:not(.card--hidden) .card')"""


# ── Геометрия карты ───────────────────────────────────────────────────
class CardGeom:
    """Обрезной формат tw×th, внутри по центру — рамка cw×ch, уменьшенная
    так, чтобы до реза оставалось не меньше CUT_SAFE_MM. Остатки по обеим
    осям чётные: рамка стоит ровно по центру."""

    def __init__(self, k):
        self.k = k
        self.px_mm = 300 * k / 25.4
        self.tw, self.th = TRIM[0] * k, TRIM[1] * k
        safe = math.ceil(CUT_SAFE_MM * self.px_mm)
        self.cw = self.tw - 2 * safe
        ch = round(CARD[1] * self.cw / CARD[0])
        self.ch = ch - (self.th - ch) % 2
        self.ox, self.oy = (self.tw - self.cw) // 2, (self.th - self.ch) // 2
        assert self.oy >= safe
        self.scale = self.cw / (CARD[0] * k)

    def mm(self, px):
        return px / self.px_mm

    def canvas(self, content):
        """Рамка cw×ch (RGB) → карта tw×th на белом."""
        assert content.size == (self.cw, self.ch), content.size
        out = Image.new('RGB', (self.tw, self.th), 'white')
        out.paste(content, (self.ox, self.oy))
        return out


# ── Отбор карт ────────────────────────────────────────────────────────
def group_order():
    src = open('js/app.js', encoding='utf-8').read()
    return re.findall(r"'(\w+)'", re.search(r'GROUP_ORDER\s*=\s*\[(.*?)\]', src, re.S).group(1))


def select(cards, lang, per_group, ids, qty, exclude=(), drafts=False):
    if ids:
        by_id = {c['id']: c for c in cards}
        missing = [i for i in ids if i not in by_id]
        if missing:
            sys.exit(f'нет таких карт: {missing}')
        picked = [by_id[i] for i in ids]
    else:
        title = (lambda c: c.get('enTitle') or c['title']) if lang == 'en' else (lambda c: c['title'])
        picked = []
        for g in group_order():
            if g in NON_PLAYABLE:
                continue
            # в тестовой выборке — разные названия (5 вариантов Катаны тест
            # не украшают); во всей колоде — каждый вид, хоть и тёзка
            seen = set()
            for c in cards:
                tags = c.get('tags') or []
                if c.get('group') != g or 'trash' in tags or ('draft' in tags and not drafts):
                    continue
                if per_group and title(c) in seen:
                    continue
                if per_group and len(seen) >= per_group:
                    break
                seen.add(title(c))
                picked.append(c)
    picked = [c for c in picked if c['id'] not in exclude]
    if qty:
        picked = [c for c in picked for _ in range(max(1, c.get('qty') or 1))]
    return picked


# ── Рендер карт headless-хромом ──────────────────────────────────────
def render(cards_wanted, lang, geom):
    """{id: RGB Image cw×ch} — рамка карты, снятая сразу в уменьшенном
    размере: device scale = 300/96·k·scale, ширина карты в CSS та же."""
    from playwright.sync_api import sync_playwright
    dsf = 300 / 96 * geom.k * geom.scale
    w_css, h_css = CARD[0] / 3.125, CARD[1] / 3.125
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)
        ctx = browser.new_context(viewport={'width': 400, 'height': 500}, device_scale_factor=dsf)
        ctx.add_init_script(INIT_JS % PRINT_CSS)
        page = ctx.new_page()
        page.emulate_media(media='print')
        for n, cid in enumerate(dict.fromkeys(c['id'] for c in cards_wanted), 1):
            url = f'file:///{ROOT.replace(os.sep, "/")}/app.html?embed={cid}' + ('&lang=en' if lang == 'en' else '')
            page.goto(url, wait_until='load')
            page.wait_for_function(READY_JS, timeout=20000)
            # positionDescWrap досчитывает в requestAnimationFrame — пара кадров тишины
            page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
            page.wait_for_timeout(150)
            r = page.evaluate("""() => { const b = document.querySelector('.card-item:not(.card--hidden) .card')
                                          .getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; }""")
            if abs(r[0]) > 1e-3 or abs(r[1]) > 1e-3 or abs(r[2] - w_css) > 0.01 or abs(r[3] - h_css) > 0.05:
                raise RuntimeError(f'карта {cid}: кадр {r}, ждал (0, 0, {w_css:.2f}, {h_css:.2f})')
            # clip Playwright округляет до целых CSS-пикселей, поэтому
            # снимаем весь вьюпорт и режем в device-пикселях от угла
            png = page.screenshot()
            im = Image.open(io.BytesIO(png)).convert('RGB').crop((0, 0, geom.cw, geom.ch))
            out[cid] = im
            print(f'  {n:3d}  #{cid}', flush=True)
        browser.close()
    return out


def back_box(geom, scale):
    """Прямоугольник рисунка рубашки внутри рамки cw×ch: (x, y, w, h).
    Остатки чётные — рисунок ровно по центру."""
    def fit(n):
        v = round(n * scale)
        return v - (n - v) % 2
    w, h = fit(geom.cw), fit(geom.ch)
    return (geom.cw - w) // 2, (geom.ch - h) // 2, w, h


def back_image(geom, scale):
    """Рубашка в рамке cw×ch: рисунок из media/backs уменьшен до scale и
    стоит по центру, вокруг — белое. Вырез из исходника — в пропорции
    рисунка, так что уменьшение изотропное."""
    im = Image.open(BACK).convert('RGB')
    # Фон рисунка — 252–254, а не 255: после профиля это 1–2 % краски
    # сплошным прямоугольником с жёстким краем вокруг рисунка. Это бумага,
    # а не тон, поэтому белая точка поднимается до 250.
    im = im.point(lambda v: min(255, round(v * 255 / 250)))
    x, y, w, h = back_box(geom, scale)
    cw = round(im.height * w / h)                      # центр исходника в пропорции рисунка
    x0 = (im.width - cw) // 2
    art = im.crop((x0, 0, x0 + cw, im.height)).resize((w, h), Image.LANCZOS)
    out = Image.new('RGB', (geom.cw, geom.ch), 'white')
    out.paste(art, (x, y))
    return out


# ── Раскладка sheet: лист A4 3×3 ─────────────────────────────────────
class Sheet:
    """Лист: страница W×H px, сетка ячеек COLS×ROWS по центру. Ячейка —
    карта (обрезной формат tw×th) плюс по полпромежутка g2 со всех сторон,
    так что ячейки стоят встык, а карты — с промежутком 2·g2. Метки,
    кресты и подпись — только снаружи сетки ячеек."""

    def __init__(self, geom, sheet_bleed_mm, gap_mm=GAP_MM, radius_mm=RADIUS_MM):
        self.k = geom.k
        self.px_mm = geom.px_mm
        self.radius_mm = radius_mm
        self.tw, self.th = geom.tw, geom.th
        self.g2 = round(self.mm(gap_mm) / 2)
        self.cw, self.ch = self.tw + 2 * self.g2, self.th + 2 * self.g2
        gw, gh = self.cw * COLS, self.ch * ROWS

        def fit(mm, grid):   # целые пиксели листа с чётным остатком — сетка встаёт ровно по центру
            n = round(mm * self.px_mm)
            if (n - grid) % 2:
                n += 1 if mm * self.px_mm > n else -1
            return n
        self.W = fit(A4_MM[0] + 2 * sheet_bleed_mm, gw)
        self.H = fit(A4_MM[1] + 2 * sheet_bleed_mm, gh)
        self.gx, self.gy = (self.W - gw) // 2, (self.H - gh) // 2
        assert 2 * self.gx + gw == self.W and 2 * self.gy + gh == self.H
        # край A4 внутри страницы (дробный: страница в целых пикселях)
        self.tx = (self.W - A4_MM[0] * self.px_mm) / 2
        self.ty = (self.H - A4_MM[1] * self.px_mm) / 2
        # полосы полей под метки: от «влёта» до сетки (и не ближе MARK_OFF к карте)
        off = self.mm(MARK_OFF_MM)
        self.band_y = (self.ty + self.mm(SAFE_MM), min(self.gy, self.gy + self.g2 - off))
        self.band_x = (self.tx + self.mm(SAFE_MM), min(self.gx, self.gx + self.g2 - off))
        if min(self.band_y[1] - self.band_y[0], self.band_x[1] - self.band_x[0]) < self.mm(2):
            sys.exit(f'на метки реза не осталось поля: промежуток {gap_mm} мм слишком велик')
        self._outline = None

    def cell(self, i):
        r, c = divmod(i, COLS)
        return self.gx + c * self.cw, self.gy + r * self.ch

    def mm(self, v):
        return v * self.px_mm

    def compose(self, canvases):
        """canvases: до 9 RGB-карт tw×th → RGB-лист, белое вокруг."""
        sheet = Image.new('RGB', (self.W, self.H), 'white')
        for i, im in enumerate(canvases):
            x, y = self.cell(i)
            sheet.paste(im, (x + self.g2, y + self.g2))
        return sheet

    def outline(self):
        """L-маска одной ячейки: пунктир по линии реза со скруглёнными
        углами. Центр линии — на границе обрезного формата; штрих стоит
        по центру каждого угла, шаг подогнан, чтобы контур замкнулся без
        обрубка. Рисуется в 4× и ужимается — края сглажены."""
        if self._outline is not None:
            return self._outline
        ss = 4
        s = self.px_mm * ss
        x0 = y0 = self.g2 * ss
        x1, y1 = (self.g2 + self.tw) * ss, (self.g2 + self.th) * ss
        R = self.radius_mm * s

        def arc(cx, cy, a0):
            n = max(8, int(R * math.pi / 2))
            return [(cx + R * math.cos(math.radians(a0 + 90 * t / n)),
                     cy + R * math.sin(math.radians(a0 + 90 * t / n))) for t in range(n + 1)]

        def seg(p, q):
            n = max(1, int(math.dist(p, q)))
            return [(p[0] + (q[0] - p[0]) * t / n, p[1] + (q[1] - p[1]) * t / n) for t in range(1, n)]
        corners = [arc(x0 + R, y0 + R, 180), arc(x1 - R, y0 + R, 270),
                   arc(x1 - R, y1 - R, 0), arc(x0 + R, y1 - R, 90)]
        path = []
        for i, c in enumerate(corners):
            path += c + seg(c[-1], corners[(i + 1) % 4][0])
        pts = np.array(path + path)                         # дважды — штрих может перейти через начало
        cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
        per = cum[len(path)]
        n = max(16, round(per / ((DASH_MM + DASH_GAP_MM) * s)))
        period = per / n
        dash = period * DASH_MM / (DASH_MM + DASH_GAP_MM)
        start = R * math.pi / 4 - dash / 2                   # первый штрих — по центру левого верхнего угла
        m = Image.new('L', (self.cw * ss, self.ch * ss), 0)
        d = ImageDraw.Draw(m)
        width = round(OUTLINE_MM * s)
        for j in range(n):
            a, b = start + j * period, start + j * period + dash
            sel = pts[(cum >= a) & (cum <= b)]
            if len(sel) > 1:
                d.line([tuple(q) for q in sel], fill=255, width=width, joint='curve')
        self._outline = m.resize((self.cw, self.ch), Image.BOX)
        return self._outline

    def outlines(self, n):
        """Пунктиры первых n ячеек листа, L-маска листа."""
        m = Image.new('L', (self.W, self.H), 0)
        for i in range(n):
            m.paste(self.outline(), self.cell(i))
        return m

    def marks(self):
        """Метки реза и кресты приводки, маска L. Рисуется левая половина
        и центральная ось, правая получается зеркалом: симметрия по
        построению, при любой толщине линии."""
        m = Image.new('L', (self.W, self.H), 0)
        d = ImageDraw.Draw(m)
        lw = max(2, round(self.mm(LINE_MM) + 0.5))
        lw += lw % 2                                   # чётная — линия встаёт ровно на границу пикселей
        h = lw // 2
        # полосы — полуоткрытые [от, до): последняя строка перед сеткой — до − 1
        (by0, by1), (bx0, bx1) = self.band_y, self.band_x
        ty0, ty1 = math.ceil(by0), math.floor(by1) - 1          # верхнее поле, включительно
        yb0, yb1 = self.H - 1 - ty1, self.H - 1 - ty0           # нижнее — зеркало верхнего
        # вертикальные линии реза: левый и правый край каждой карты; метки сверху и снизу
        for c in range(COLS):
            for x in (self.gx + c * self.cw + self.g2, self.gx + c * self.cw + self.g2 + self.tw):
                if 2 * x > self.W:
                    continue
                for y0, y1 in ((ty0, ty1), (yb0, yb1)):
                    d.rectangle((x - h, y0, x + h - 1, y1), fill=255)
        # горизонтальные линии реза — метки в левом поле
        for r in range(ROWS):
            for y in (self.gy + r * self.ch + self.g2, self.gy + r * self.ch + self.g2 + self.th):
                d.rectangle((math.ceil(bx0), y - h, math.floor(bx1) - 1, y + h - 1), fill=255)

        # кресты приводки: по центру верхнего и нижнего поля, середина левого
        def cross(x, y, band):
            arm = min(self.mm(3.5), band / 2 - lw)
            rad = arm * 0.57
            x, y = round(x * 2) / 2, round(y * 2) / 2
            d.ellipse((x - rad, y - rad, x + rad, y + rad), outline=255, width=lw)
            d.rectangle((x - arm, y - h + 0.5, x + arm, y + h - 0.5), fill=255)
            d.rectangle((x - h + 0.5, y - arm, x + h - 0.5, y + arm), fill=255)
        cx, cy = (self.W - 1) / 2, (by0 + by1) / 2
        cross(cx, cy, by1 - by0)
        cross(cx, self.H - 1 - cy, by1 - by0)
        cross((bx0 + bx1) / 2, (self.H - 1) / 2, bx1 - bx0)
        return ImageChops.lighter(m, m.transpose(Image.FLIP_LEFT_RIGHT))

    def label_box(self):
        """Место подписи: нижнее поле под первой картой — между метками её
        левого и правого края, от «влёта» до сетки."""
        x0 = round(self.gx + self.g2 + self.mm(2))
        x1 = round(self.gx + self.g2 + self.tw - self.mm(2))
        y0 = self.H - math.floor(self.band_y[1])
        y1 = self.H - 1 - math.ceil(self.band_y[0])
        return x0, y0, x1, y1


def to_cmyk(rgb, transform):
    return ImageCms.applyTransform(rgb, transform)


def burn_k(cmyk, mask):
    """Маску — в канал K на 100%, CMY под ней обнулить (белые поля и так 0)."""
    c, m, y, kk = cmyk.split()
    zero = Image.new('L', cmyk.size, 0)
    c, m, y = (Image.composite(zero, ch, mask) for ch in (c, m, y))
    kk = ImageChops.lighter(kk, mask)
    return Image.merge('CMYK', (c, m, y, kk))


def burn_gray(cmyk, mask, level=OUTLINE_K):
    """Маску — в K долей level (серый пунктир); CMY не трогаются."""
    c, m, y, kk = cmyk.split()
    return Image.merge('CMYK', (c, m, y, ImageChops.lighter(kk, mask.point(lambda v: round(v * level)))))


def draw_label(sheet, text):
    x0, y0, x1, y1 = sheet.label_box()
    for pt in (7, 6.5, 6):                             # 6 pt — минимум ottisk
        m = Image.new('L', (sheet.W, sheet.H), 0)
        font = ImageFont.truetype(LABEL_FONT, round(pt / 72 * 300 * sheet.k))
        ImageDraw.Draw(m).text((x0, y1), text, font=font, fill=255, anchor='ls')
        bbox = m.getbbox()
        if bbox and bbox[2] <= x1 and bbox[1] >= y0:
            return m
    raise RuntimeError(f'подпись не влезла в поле: {bbox} vs {(x0, y0, x1, y1)}')


# ── PDF: одна CMYK-картинка на страницу ───────────────────────────────
def pdf_str(s):
    return '(' + s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') + ')'


def write_pdf(path, pages, k, title, trim_mm=None, page_mm=None):
    """pages: CMYK Image страницы, одинаковые объекты кладутся в файл
    один раз. trim_mm — обрезной формат по центру страницы (лист A4);
    None — TrimBox = вся страница (карта в размер). page_mm — размер
    страницы ровно в мм (картинка растягивается на неё: 661×1028 px в
    56×87 мм — это 299,8 × 300,1 ppi); None — страница по пикселям, 300·k ppi."""
    cache, raw = {}, []
    s = 72 / (300 * k)
    for im in pages:
        if id(im) not in cache:
            assert im.mode == 'CMYK'
            cache[id(im)] = zlib.compress(im.tobytes(), 6)
        w, h = im.size
        wpt, hpt = (page_mm[0] / 25.4 * 72, page_mm[1] / 25.4 * 72) if page_mm else (w * s, h * s)
        if trim_mm:
            tw, th = trim_mm[0] / 25.4 * 72, trim_mm[1] / 25.4 * 72
            trim = ((wpt - tw) / 2, (hpt - th) / 2, (wpt + tw) / 2, (hpt + th) / 2)
        else:
            trim = (0, 0, wpt, hpt)
        raw.append(dict(data=cache[id(im)], w=w, h=h, media=(0, 0, wpt, hpt), trim=trim))
    write_pdf_raw(path, raw, title)


def write_pdf_raw(path, pages, title):
    """pages: dict(data — Flate-поток CMYK-картинки, w, h — её пиксели,
    media, trim — прямоугольники в pt). Одинаковые data (один объект)
    кладутся в файл один раз. OutputIntent — зарегистрированное условие
    FOGRA39 без вшитого профиля (8 МБ): для DeviceCMYK этого достаточно,
    профиль у типографии свой."""
    num = lambda v: f'{v:.4f}'.rstrip('0').rstrip('.')
    arr = lambda r: '[' + ' '.join(num(v) for v in r) + ']'
    objs = [None] * 4    # 1 catalog, 2 pages, 3 output intent, 4 info

    def add(body):
        objs.append(body)
        return len(objs)

    def stream(dict_body, data):
        return f'<< {dict_body} /Length {len(data)} >>\nstream\n'.encode() + data + b'\nendstream'

    img_ref, kids = {}, []
    for pg in pages:
        if id(pg['data']) not in img_ref:
            img_ref[id(pg['data'])] = add(stream(
                f'/Type /XObject /Subtype /Image /Width {pg["w"]} /Height {pg["h"]} '
                f'/ColorSpace /DeviceCMYK /BitsPerComponent 8 /Filter /FlateDecode', pg['data']))
        x0, y0, x1, y1 = pg['media']
        content = add(stream('', f'q {num(x1 - x0)} 0 0 {num(y1 - y0)} {num(x0)} {num(y0)} cm /Im0 Do Q'.encode()))
        kids.append(add(f'<< /Type /Page /Parent 2 0 R /MediaBox {arr(pg["media"])} /BleedBox {arr(pg["media"])} '
                        f'/TrimBox {arr(pg["trim"])} '
                        f'/Resources << /XObject << /Im0 {img_ref[id(pg["data"])]} 0 R >> >> '
                        f'/Contents {content} 0 R >>'.encode()))
    objs[0] = b'<< /Type /Catalog /Pages 2 0 R /OutputIntents [3 0 R] >>'
    objs[1] = f'<< /Type /Pages /Kids [{" ".join(f"{i} 0 R" for i in kids)}] /Count {len(kids)} >>'.encode()
    objs[2] = (b'<< /Type /OutputIntent /S /GTS_PDFX /OutputConditionIdentifier (FOGRA39) '
               b'/OutputCondition (Coated FOGRA39 \\(ISO 12647-2:2004\\)) '
               b'/RegistryName (http://www.color.org) /Info (Coated FOGRA39) >>')
    now = datetime.datetime.now().strftime('D:%Y%m%d%H%M%S')
    objs[3] = (f'<< /Title {pdf_str(title)} /Producer (tools/build-print-sheets.py) '
               f'/CreationDate ({now}) /ModDate ({now}) /Trapped /False >>').encode()

    out = io.BytesIO()
    out.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f'{i} 0 obj\n'.encode() + body + b'\nendobj\n')
    xref = out.tell()
    out.write(f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode())
    for o in offsets:
        out.write(f'{o:010d} 00000 n \n'.encode())
    fid = os.urandom(16).hex()
    out.write(f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 4 0 R /ID [<{fid}> <{fid}>] >>\n'
              f'startxref\n{xref}\n%%EOF\n'.encode())
    with open(path, 'wb') as f:
        f.write(out.getvalue())


def split_pdf(path, limit_mb):
    """Режет готовый PDF на части не больше limit_mb (вложения почты: у
    Gmail 25 МБ на письмо). Порядок страниц сохраняется, страница не
    дробится; поток картинки, размеры и TrimBox копируются байт в байт,
    после записи каждая часть сверяется с исходником."""
    import fitz
    src = fitz.open(path)
    nums = lambda key, x: tuple(float(v) for v in src.xref_get_key(x, key)[1].strip('[]').split())
    pages, streams = [], {}
    for p in src:
        x = p.get_images(full=True)[0][0]
        if x not in streams:                               # повторы карт — один поток, как в исходнике
            streams[x] = src.xref_stream_raw(x)
        pages.append(dict(data=streams[x], w=int(src.xref_get_key(x, 'Width')[1]),
                          h=int(src.xref_get_key(x, 'Height')[1]),
                          media=nums('MediaBox', p.xref), trim=nums('TrimBox', p.xref)))
    title = src.metadata.get('title') or ''
    limit = limit_mb * 1e6 - 100_000                      # запас на обвязку PDF
    groups, cur, size, held = [], [], 0, set()
    for i, pg in enumerate(pages):
        add = 0 if id(pg['data']) in held else len(pg['data'])
        if cur and size + add > limit:
            groups.append(cur)
            cur, size, held = [], 0, set()
            add = len(pg['data'])
        cur.append(i)
        held.add(id(pg['data']))
        size += add
    groups.append(cur)
    base = os.path.splitext(path)[0]
    out = []
    for n, g in enumerate(groups, 1):
        part = f'{base}_part{n:02d}of{len(groups):02d}.pdf'
        write_pdf_raw(part, [pages[i] for i in g], f'{title} — part {n}/{len(groups)}')
        d = fitz.open(part)
        assert len(d) == len(g), part
        for pp, i in zip(d, g):
            x = pp.get_images(full=True)[0][0]
            assert d.xref_stream_raw(x) == pages[i]['data'], f'{part}: стр. {i + 1} не совпала с исходником'
            assert abs(pp.trimbox.width - src[i].trimbox.width) < 0.01, f'{part}: TrimBox стр. {i + 1}'
        d.close()
        mb = os.path.getsize(part) / 1e6
        assert mb <= limit_mb or len(g) == 1, f'{part}: {mb:.1f} МБ'
        out.append(part)
        print(f'  {os.path.basename(part)}: стр. {g[0] + 1}–{g[-1] + 1}, {mb:.1f} МБ')
    return out


# ── Самопроверка ──────────────────────────────────────────────────────
def check_pdf(path, rasters, k, trim_mm=None, page_mm=None):
    """Перечитывает PDF: размер страницы (page_mm, если задан), TrimBox
    (trim_mm по центру или вся страница), на странице ровно одна
    CMYK-картинка 300·k ppi (при page_mm — в пределах 0,5 %), ни шрифтов,
    ни текста, ни векторов, и пиксели картинки совпадают с собранной
    страницей байт в байт."""
    import fitz
    doc = fitz.open(path)
    assert len(doc) == len(rasters), f'{path}: {len(doc)} стр., ждал {len(rasters)}'
    decoded, wanted = {}, {}
    for n, (page, im) in enumerate(zip(doc, rasters), 1):
        where = f'{os.path.basename(path)} стр. {n}'
        tb, pr = page.trimbox, page.rect
        tw, th = (trim_mm[0] / 25.4 * 72, trim_mm[1] / 25.4 * 72) if trim_mm else (pr.width, pr.height)
        assert abs(tb.width - tw) < 0.01 and abs(tb.height - th) < 0.01, f'{where}: TrimBox {tb}'
        assert abs((tb.x0 + tb.x1) - pr.width) < 0.01, f'{where}: TrimBox не по центру'
        imgs = page.get_images(full=True)
        assert len(imgs) == 1, f'{where}: картинок {len(imgs)}'
        assert not page.get_fonts(), f'{where}: шрифты {page.get_fonts()}'
        assert not page.get_text().strip(), f'{where}: есть текст'
        assert not page.get_drawings(), f'{where}: есть векторы'
        if page_mm:
            assert abs(pr.width - page_mm[0] / 25.4 * 72) < 0.01 and abs(pr.height - page_mm[1] / 25.4 * 72) < 0.01, \
                f'{where}: страница {pr.width / 72 * 25.4:.2f}×{pr.height / 72 * 25.4:.2f} мм, ждал {page_mm}'
        xref, _, w, h, bpc, cs = imgs[0][:6]
        assert cs == 'DeviceCMYK' and bpc == 8 and (w, h) == im.size, f'{where}: {cs} {bpc} {w}×{h}'
        for ppi in (w / (pr.width / 72), h / (pr.height / 72)):
            tol = 300 * k * 0.005 if page_mm else 0.01
            assert abs(ppi - 300 * k) < tol, f'{where}: {ppi:.2f} ppi'
        if xref not in decoded:
            pix = fitz.Pixmap(doc, xref)
            assert pix.n == 4, where
            decoded[xref] = pix.samples
        if id(im) not in wanted:
            wanted[id(im)] = im.tobytes()
        assert decoded[xref] == wanted[id(im)], f'{where}: пиксели в PDF не совпали со страницей'
    doc.close()


def check_cut_safe(pages, geom, names):
    """Ни у одной карты краска не подходит к резу ближе CUT_SAFE_MM.
    Возвращает наименьшее поле в мм."""
    safe = math.ceil(CUT_SAFE_MM * geom.px_mm)
    worst = None
    for im, name in zip(pages, names):
        a = np.array(im).max(axis=2) > 0
        ys, xs = np.nonzero(a)
        m = min(xs.min(), ys.min(), a.shape[1] - 1 - xs.max(), a.shape[0] - 1 - ys.max())
        assert m >= safe, f'{name}: краска в {geom.mm(m):.2f} мм от реза, нужно не меньше {CUT_SAFE_MM:g}'
        worst = m if worst is None else min(worst, m)
    return geom.mm(worst)


def check_back_white(back_canvas_cmyk, geom, scale):
    """Фон рисунка рубашки белый, а не бледная плашка: кайма прямоугольника
    рисунка шириной 2 px почти вся без краски."""
    x, y, w, h = back_box(geom, scale)
    x, y = x + geom.ox, y + geom.oy
    fr = np.array(back_canvas_cmyk)[y:y + h, x:x + w].max(axis=2) > 0
    ring = np.concatenate([fr[:2].ravel(), fr[-2:].ravel(), fr[:, :2].ravel(), fr[:, -2:].ravel()])
    assert ring.mean() < 0.1, f'фон рубашки не белый: {ring.mean():.0%} каймы рисунка в краске'


def check_registration(faces, back, sheet, marks, face_cards, back_card, transform):
    """Раскладка sheet: лицо ↔ рубашка при перевороте по длинной стороне.
    1) ячейки зеркальны: ячейка (r, c) лица и (r, COLS-1-c) рубашки
       занимают на листе одно и то же место;
    2) в каждой ячейке каждого листа стоит ровно своя карта и ровно на своём
       месте — пиксель в пиксель с отдельно переведённой в CMYK картой;
       сдвиг на 1 px (0,08 мм) не пройдёт;
    3) метки и кресты на каждом листе зеркальны сами себе и одинаковы на
       лицах и рубашке (подпись из сравнения вырезается);
    4) вне сетки нет никакой краски, кроме меток и подписи."""
    for i in range(COLS * ROWS):
        r, c = divmod(i, COLS)
        (xf, yf), (xb, yb) = sheet.cell(i), sheet.cell(r * COLS + COLS - 1 - c)
        assert (xf, yf) == (sheet.W - xb - sheet.cw, yb), f'ячейка {i + 1}: лицо и рубашка разъехались'

    cache = {}

    def expected(canvas, outlined):
        if (id(canvas), outlined) not in cache:
            cell = Image.new('RGB', (sheet.cw, sheet.ch), 'white')
            cell.paste(canvas, (sheet.g2, sheet.g2))
            cell = to_cmyk(cell, transform)
            cache[id(canvas), outlined] = np.array(burn_gray(cell, sheet.outline()) if outlined else cell)
        return cache[id(canvas), outlined]
    blank = np.zeros((sheet.ch, sheet.cw, 4), np.uint8)
    sheets = [('рубашки', back, [back_card] * (COLS * ROWS), False)]
    sheets += [(f'лица {n}', f, cards, True) for n, (f, cards) in enumerate(zip(faces, face_cards), 1)]
    for name, im, cards, outlined in sheets:
        a = np.array(im)
        for i in range(COLS * ROWS):
            x, y = sheet.cell(i)
            want = expected(cards[i], outlined) if i < len(cards) else blank
            assert np.array_equal(a[y:y + sheet.ch, x:x + sheet.cw], want), \
                f'{name}, ячейка {i + 1}: карта не на своём месте или не та'

    x0, y0, x1, y1 = sheet.label_box()
    keep = np.ones((sheet.H, sheet.W), bool)
    keep[sheet.gy:sheet.H - sheet.gy, sheet.gx:sheet.W - sheet.gx] = False
    keep[y0 - sheet.k * 10:y1 + sheet.k * 10, x0:x1] = False
    k_marks = np.array(marks) > 0
    for name, im, _, _ in sheets:
        a = np.array(im)
        kch = (a[..., 3] > 0) & keep
        assert np.array_equal(kch, k_marks & keep), f'{name}: метки не совпали с эталоном'
        assert np.array_equal(kch, np.fliplr(kch)), f'{name}: метки несимметричны'
        assert not ((a.max(axis=2) > 0) & keep & ~k_marks).any(), f'{name}: краска вне сетки и меток'


_proof = []

def soft_proof(cmyk, width_px):
    if not _proof:
        _proof.append(ImageCms.buildTransform(ImageCms.getOpenProfile(ICC), ImageCms.createProfile('sRGB'),
                                              'CMYK', 'RGB', renderingIntent=ImageCms.Intent.PERCEPTUAL))
    rgb = ImageCms.applyTransform(cmyk, _proof[0])
    return rgb.resize((width_px, round(rgb.height * width_px / rgb.width)), Image.LANCZOS)


def contact_sheet(cards, thumb_w, cols):
    """Обзор карт сеткой на сером: soft-proof, край карты = линия реза."""
    thumbs = [soft_proof(c, thumb_w) for c in cards]
    th = thumbs[0].height
    rows = -(-len(thumbs) // cols)
    gap = 8
    out = Image.new('RGB', (cols * (thumb_w + gap) + gap, rows * (th + gap) + gap), '#9a9a9a')
    for i, t in enumerate(thumbs):
        out.paste(t, (gap + (i % cols) * (thumb_w + gap), gap + (i // cols) * (th + gap)))
    return out


# ── main ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='PDF колоды для типографии: лица и рубашка отдельными файлами.')
    ap.add_argument('--lang', choices=('en', 'ru'), default='en')
    ap.add_argument('--layout', choices=('card', 'sheet'), default='card',
                    help='card — страница = карта 56×87 (типография делает спуск сама); sheet — листы A4 3×3')
    ap.add_argument('--per-group', type=int, default=5, help='разных названий из группы; 0 — все')
    ap.add_argument('--ids', type=int, nargs='+', help='конкретные ID вместо отбора по группам')
    ap.add_argument('--qty', action='store_true', help='каждую карту — в количестве qty')
    ap.add_argument('--exclude', type=int, nargs='+', default=[], help='ID, которые в этот раз не печатать')
    ap.add_argument('--drafts', action='store_true', help='печатать и черновики (тег draft)')
    ap.add_argument('--dpi', type=int, choices=(300, 600), default=300)
    ap.add_argument('--back-scale', type=float, default=BACK_SCALE, help='размер рисунка рубашки от кадра')
    ap.add_argument('--sheet-bleed', type=float, default=5.0, help='sheet: белый вылет листа, мм (ottisk: 5)')
    ap.add_argument('--gap', type=float, default=GAP_MM, help='sheet: промежуток между картами, мм')
    ap.add_argument('--radius', type=float, default=RADIUS_MM, help='sheet: радиус скругления углов пунктира, мм')
    ap.add_argument('--out', default='print', help='папка для PDF')
    ap.add_argument('--name', help='база имени файлов; по умолчанию cards_|sheets_<lang>[_test<N>]_<дата>')
    ap.add_argument('--preview', help='папка для PNG soft-proof')
    ap.add_argument('--split', metavar='PDF', help='не собирать, а порезать готовый PDF на части под почту')
    ap.add_argument('--split-mb', type=float, default=20, help='предел части для --split, МБ (Gmail — 25 на письмо)')
    a = ap.parse_args()
    k = a.dpi // 300
    if a.split:
        print(f'{a.split} -> части до {a.split_mb:g} МБ')
        split_pdf(a.split, a.split_mb)
        return

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:   # колода — из самой картотеки, как её видит браузер
        b = p.chromium.launch(executable_path=CHROME)
        pg = b.new_page()
        pg.goto(f'file:///{ROOT.replace(os.sep, "/")}/app.html?embed=0', wait_until='load')
        cards = pg.evaluate('() => CARDS')
        b.close()
    picked = select(cards, a.lang, a.per_group, a.ids, a.qty, set(a.exclude), a.drafts)
    if not picked:
        sys.exit('нечего печатать')
    shown = (lambda c: c.get('enDesc') or c.get('desc') or '') if a.lang == 'en' else (lambda c: c.get('desc') or '')
    todo = [c['id'] for c in {c['id']: c for c in picked}.values() if 'TODO' in shown(c)]
    if todo:
        print('внимание: в тексте карт есть «TODO», он уйдёт в печать — ' + ', '.join(f'#{i}' for i in todo))
    today = datetime.date.today().isoformat()
    prefix = 'cards' if a.layout == 'card' else 'sheets'
    name = a.name or (f'{prefix}_{a.lang}' + (f'_test{a.per_group}' if a.per_group and not a.ids else '') + f'_{today}')
    kinds = len({c['id'] for c in picked})
    if a.layout == 'card':
        print(f'{len(picked)} карт ({kinds} видов) -> {len(picked)} стр. 56×87 мм, {a.dpi} ppi, {a.lang.upper()}')
    else:
        print(f'{len(picked)} карт -> {-(-len(picked) // (COLS * ROWS))} лист(ов) A4, {a.dpi} ppi, {a.lang.upper()}')

    geom = CardGeom(k)
    shots = render(picked, a.lang, geom)
    to_cmyk_t = ImageCms.buildTransform(ImageCms.createProfile('sRGB'), ImageCms.getOpenProfile(ICC),
                                        'RGB', 'CMYK', renderingIntent=ImageCms.Intent.PERCEPTUAL)
    canvases = {cid: geom.canvas(im) for cid, im in shots.items()}
    back_canvas = geom.canvas(back_image(geom, a.back_scale))
    os.makedirs(a.out, exist_ok=True)
    f_pdf = os.path.join(a.out, f'{name}_faces.pdf')

    if a.layout == 'card':
        cmyk = {cid: to_cmyk(c, to_cmyk_t) for cid, c in canvases.items()}
        faces = [cmyk[c['id']] for c in picked]           # повторы — тот же объект, в PDF один поток
        back = to_cmyk(back_canvas, to_cmyk_t)
        b_pdf = os.path.join(a.out, f'{name}_back.pdf')
        write_pdf(f_pdf, faces, k, f'Samurai vs Ninja — faces ({a.lang.upper()})', page_mm=TRIM_MM)
        write_pdf(b_pdf, [back], k, 'Samurai vs Ninja — back', page_mm=TRIM_MM)
        check_pdf(f_pdf, faces, k, page_mm=TRIM_MM)
        check_pdf(b_pdf, [back], k, page_mm=TRIM_MM)
        check_back_white(back, geom, a.back_scale)
        least = check_cut_safe(list(cmyk.values()) + [back], geom, [f'#{cid}' for cid in cmyk] + ['рубашка'])
        print(f'страница = карта {TRIM_MM[0]:g} x {TRIM_MM[1]:g} мм ({geom.tw} x {geom.th} px), TrimBox = страница; '
              f'рамка уменьшена до {geom.scale:.3f}: {geom.mm(geom.cw):.1f} x {geom.mm(geom.ch):.1f} мм, '
              f'поля {geom.mm(geom.ox):.2f} / {geom.mm(geom.oy):.2f} мм')
        print(f'проверка: одна CMYK-картинка на страницу, ни шрифтов, ни векторов; '
              f'краска не ближе {least:.2f} мм к резу (нужно {CUT_SAFE_MM:g}) — OK')
        if a.preview:
            os.makedirs(a.preview, exist_ok=True)
            contact_sheet(list(cmyk.values()), 220, 9).save(os.path.join(a.preview, f'{name}_faces.png'))
            soft_proof(back, geom.tw).save(os.path.join(a.preview, f'{name}_back.png'))
            soft_proof(faces[0], geom.tw).save(os.path.join(a.preview, f'{name}_card1_actual.png'))
    else:
        sheet = Sheet(geom, a.sheet_bleed, a.gap, a.radius)
        marks = sheet.marks()
        per = COLS * ROWS
        chunks = [picked[i:i + per] for i in range(0, len(picked), per)]
        faces, face_cards = [], []
        for n, chunk in enumerate(chunks, 1):
            face_cards.append([canvases[c['id']] for c in chunk])
            cmyk = burn_k(to_cmyk(sheet.compose(face_cards[-1]), to_cmyk_t), marks)
            cmyk = burn_gray(cmyk, sheet.outlines(len(chunk)))
            label = f'Samurai vs Ninja · {a.lang.upper()} · faces {n}/{len(chunks)} · {today}'
            faces.append(burn_k(cmyk, draw_label(sheet, label)))
        back = burn_k(to_cmyk(sheet.compose([back_canvas] * per), to_cmyk_t), marks)
        b_pdf = os.path.join(a.out, f'{name}_backs.pdf')
        write_pdf(f_pdf, faces, k, f'Samurai vs Ninja — faces ({a.lang.upper()})', trim_mm=A4_MM)
        write_pdf(b_pdf, [back], k, 'Samurai vs Ninja — backs', trim_mm=A4_MM)
        check_pdf(f_pdf, faces, k, A4_MM)
        check_pdf(b_pdf, [back], k, A4_MM)
        check_registration(faces, back, sheet, marks, face_cards, back_canvas, to_cmyk_t)
        check_back_white(to_cmyk(back_canvas, to_cmyk_t), geom, a.back_scale)
        mm = lambda v: v / sheet.px_mm
        print(f'страница {mm(sheet.W):.2f} x {mm(sheet.H):.2f} мм, TrimBox A4; '
              f'карта {mm(sheet.tw):.2f} x {mm(sheet.th):.2f} мм, углы R {sheet.radius_mm:g}, '
              f'промежуток {mm(2 * sheet.g2):.2f} мм; от края A4 до карт '
              f'{mm(sheet.gx + sheet.g2 - sheet.tx):.2f} мм слева/справа, {mm(sheet.gy + sheet.g2 - sheet.ty):.2f} мм сверху/снизу')
        print('проверка: одна CMYK-картинка на страницу, ни шрифтов, ни векторов; '
              'метки и сетка зеркальны, рубашка ложится на каждое лицо — OK')
        if a.preview:
            os.makedirs(a.preview, exist_ok=True)
            for n, f in enumerate(faces, 1):
                soft_proof(f, 1600).save(os.path.join(a.preview, f'{name}_faces_{n}.png'))
            soft_proof(back, 1600).save(os.path.join(a.preview, f'{name}_backs.png'))
            # «на просвет»: лицо 1 и отражённая рубашка, перемножены
            light = ImageChops.multiply(soft_proof(faces[0], 1600),
                                        soft_proof(back, 1600).transpose(Image.FLIP_LEFT_RIGHT))
            light.save(os.path.join(a.preview, f'{name}_registration.png'))

    print(f_pdf)
    print(b_pdf)


if __name__ == '__main__':
    main()
