# -*- coding: utf-8 -*-
"""Листы A4 для печати колоды в типографии — по 9 карт на листе, лица и
рубашки отдельными PDF.

Требования ottisk.com к открыткам и визиткам (они совпадают дословно,
https://ottisk.com/knowledgebase/requirement/postcards-and-invitations/):
PDF, CMYK FOGRA39, 300 ppi, все слои сведены в один Background, эффекты
растрированы, шрифты в кривых, вылеты и «влёты» по 5 мм, без рамок по
периметру, линии не тоньше 0,2 мм. Отсюда устройство:

  • Каждая страница PDF — ОДНА CMYK-картинка и больше ничего: ни шрифтов,
    ни кривых, ни прозрачности. «Свести в один слой» выполнено буквально.
  • Карта снимается headless-хромом с картотеки (app.html?embed=<id>) в
    печатном режиме — под @media print, как при печати из картотеки:
    шрифты карты заданы в pt, и экранная карта шириной 240 px разложила бы
    текст иначе, чем бумажная. Ширина — 611/300 дюйма, ровно 611 px маски
    при 300 ppi, так что рамка ложится пиксель в пиксель.
  • Вокруг рамки — белое поле PAD (2,1 мм): ячейка 661×1028 px = 56×87 мм,
    от рваного края рамки до реза 2,2–3,0 мм — запас и ножу, и глазу.
  • sRGB → FOGRA39 тем же профилем и интентом (perceptual), что
    CMYK-превью картотеки (tools/bake-cmyk-css.py).
  • Лист собирается в CMYK: сетка 3×3 встык по центру листа, метки реза,
    кресты приводки и подпись рисуются прямо в канал K — чистый 100K без
    пересчёта профилем.
  • Сетка, метки и кресты симметричны относительно вертикальной оси листа
    до пикселя, поэтому лист рубашек ложится на любой лист лиц при
    перевороте по длинной стороне. Скрипт проверяет это сам, на готовых PDF.
  • Страница = A4 + 5 мм белого вылета с каждой стороны, TrimBox = A4;
    `--sheet-bleed 0` даст ровно A4.

    py -3 tools/build-print-sheets.py                         # тест: EN, по 5 разных названий из группы
    py -3 tools/build-print-sheets.py --lang ru --per-group 0 # вся колода, по карте каждого вида
    py -3 tools/build-print-sheets.py --per-group 0 --qty     # вся колода в количестве qty
    py -3 tools/build-print-sheets.py --ids 1 49 57           # конкретные карты
    py -3 tools/build-print-sheets.py --preview DIR           # + PNG soft-proof листов и «на просвет»

Пишет print/sheets_<lang>[_test<N>]_<дата>_faces.pdf и …_backs.pdf.
"""
import argparse, datetime, io, os, re, sys, zlib

import numpy as np
from PIL import Image, ImageChops, ImageCms, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
ICC = 'profiles/Coated_Fogra39L_VIGC_300.icc'
BACK = 'media/backs/default.png'
LABEL_FONT = r'C:\Windows\Fonts\segoeui.ttf'

NON_PLAYABLE = ('role', 'character')

# Все размеры — в пикселях при 300 ppi; при --dpi 600 умножаются на K=2,
# поэтому симметрия раскладки сохраняется на любом разрешении.
CARD = (611, 978)        # рамка карты = mask_*.png, 51,73 × 82,80 мм
PAD = 25                 # белое поле вокруг рамки, 2,12 мм → ячейка 56 × 87 мм
COLS, ROWS = 3, 3
A4_MM = (210.0, 297.0)
SAFE_MM = 5.0            # «влёты»: ничего ближе к краю A4
MARK_OFF_MM = 2.0        # метка реза начинается в 2 мм от сетки
MARK_LEN_MM = 6.0
LINE_MM = 0.2            # минимум ottisk для одноцветной линии

# Печатный режим картотеки, приколоченный к пикселю: карта в (0,0),
# ширина 611/300 дюйма (при device scale 300/96 это ровно 611 px),
# без пунктира-направляющей из print.css.
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


# ── Отбор карт ────────────────────────────────────────────────────────
def group_order():
    src = open('js/app.js', encoding='utf-8').read()
    return re.findall(r"'(\w+)'", re.search(r'GROUP_ORDER\s*=\s*\[(.*?)\]', src, re.S).group(1))


def select(cards, lang, per_group, ids, qty):
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
            seen = set()
            for c in cards:
                tags = c.get('tags') or []
                if c.get('group') != g or 'trash' in tags or 'draft' in tags or title(c) in seen:
                    continue
                if per_group and len(seen) >= per_group:
                    break
                seen.add(title(c))
                picked.append(c)
    if qty:
        picked = [c for c in picked for _ in range(max(1, c.get('qty') or 1))]
    return picked


# ── Рендер карт headless-хромом ──────────────────────────────────────
def render(cards_wanted, lang, k):
    """{id: RGB Image CARD×k} — карта ровно в кадре, белое вокруг рамки."""
    from playwright.sync_api import sync_playwright
    dsf = 300 / 96 * k
    w_css, h_css = CARD[0] / 3.125, CARD[1] / 3.125
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)
        ctx = browser.new_context(viewport={'width': 400, 'height': 500}, device_scale_factor=dsf)
        ctx.add_init_script(INIT_JS % PRINT_CSS)
        page = ctx.new_page()
        page.emulate_media(media='print')
        all_cards = None
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
            # clip Playwright округляет до целых CSS-пикселей (195,52 → 195),
            # поэтому снимаем весь вьюпорт и режем в device-пикселях от угла
            png = page.screenshot()
            im = Image.open(io.BytesIO(png)).convert('RGB').crop((0, 0, CARD[0] * k, CARD[1] * k))
            if im.size != (CARD[0] * k, CARD[1] * k):
                raise RuntimeError(f'карта {cid}: снимок {im.size}, ждал {(CARD[0] * k, CARD[1] * k)}')
            out[cid] = im
            print(f'  {n:3d}  #{cid}', flush=True)
        browser.close()
    return out


def back_image(k):
    """Рубашка в кадре рамки: центр 5:8 из media/backs (по бокам там белое)."""
    im = Image.open(BACK).convert('RGB')
    # Фон рисунка — 252–254, а не 255: после профиля это 1–2 % краски
    # сплошным прямоугольником с жёстким краем вокруг рисунка. Это бумага,
    # а не тон, поэтому белая точка поднимается до 250.
    im = im.point(lambda v: min(255, round(v * 255 / 250)))
    w = round(im.height * CARD[0] / CARD[1])
    x0 = (im.width - w) // 2
    return im.crop((x0, 0, x0 + w, im.height)).resize((CARD[0] * k, CARD[1] * k), Image.LANCZOS)


# ── Геометрия листа ───────────────────────────────────────────────────
class Sheet:
    def __init__(self, k, sheet_bleed_mm):
        self.k = k
        self.px_mm = 300 * k / 25.4
        self.cw, self.ch = (CARD[0] + 2 * PAD) * k, (CARD[1] + 2 * PAD) * k
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

    def cell(self, i):
        r, c = divmod(i, COLS)
        return self.gx + c * self.cw, self.gy + r * self.ch

    def mm(self, v):
        return v * self.px_mm

    def compose(self, images):
        """images: до 9 RGB-картинок кадра CARD×k → RGB-лист, белое вокруг."""
        sheet = Image.new('RGB', (self.W, self.H), 'white')
        p = PAD * self.k
        for i, im in enumerate(images):
            x, y = self.cell(i)
            sheet.paste(im, (x + p, y + p))
        return sheet

    def marks(self):
        """Метки реза и кресты приводки, маска L. Рисуется левая половина
        и центральная ось, правая получается зеркалом: симметрия по
        построению, при любой толщине линии."""
        m = Image.new('L', (self.W, self.H), 0)
        d = ImageDraw.Draw(m)
        lw = max(2, round(self.mm(LINE_MM) + 0.5))
        lw += lw % 2                                   # чётная — линия встаёт ровно на границу пикселей
        h = lw // 2
        off, ln = self.mm(MARK_OFF_MM), self.mm(MARK_LEN_MM)
        gw, gh = self.cw * COLS, self.ch * ROWS
        # вертикальные линии реза (левая половина, включая центр) — метки сверху и снизу
        for c in range(COLS + 1):
            x = self.gx + c * self.cw
            if 2 * x > self.W:
                continue
            for y0, y1 in ((self.gy - off - ln, self.gy - off), (self.gy + gh + off, self.gy + gh + off + ln)):
                d.rectangle((x - h, round(y0), x + h - 1, round(y1)), fill=255)
        # горизонтальные линии реза — метки в левом поле
        for r in range(ROWS + 1):
            y = self.gy + r * self.ch
            d.rectangle((round(self.gx - off - ln), y - h, round(self.gx - off), y + h - 1), fill=255)
        # кресты приводки: по центру верхнего и нижнего поля, середина левого
        rad, arm = self.mm(2.0), self.mm(3.5)
        cx = (self.W - 1) / 2
        top_y = (self.ty + self.gy) / 2
        bot_y = self.H - 1 - top_y
        left_x = (self.tx + self.gx) / 2
        for x, y in ((cx, top_y), (cx, bot_y), (left_x, (self.H - 1) / 2)):
            x, y = round(x * 2) / 2, round(y * 2) / 2
            d.ellipse((x - rad, y - rad, x + rad, y + rad), outline=255, width=lw)
            d.rectangle((x - arm, y - h + 0.5, x + arm, y + h - 0.5), fill=255)
            d.rectangle((x - h + 0.5, y - arm, x + h - 0.5, y + arm), fill=255)
        return ImageChops.lighter(m, m.transpose(Image.FLIP_LEFT_RIGHT))

    def label_box(self):
        """Место подписи: нижнее поле, от левой метки до центрального креста.
        По высоте подпись ниже меток реза, так что линию реза она не задевает."""
        x0 = round(self.gx + self.mm(3))
        x1 = round((self.W - 1) / 2 - self.mm(6))
        y1 = round(self.H - self.ty - self.mm(SAFE_MM))
        y0 = round(y1 - self.mm(3.2))
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


def draw_label(sheet, text):
    x0, y0, x1, y1 = sheet.label_box()
    m = Image.new('L', (sheet.W, sheet.H), 0)
    font = ImageFont.truetype(LABEL_FONT, round(7 / 72 * 300 * sheet.k))   # 7 pt
    ImageDraw.Draw(m).text((x0, y1), text, font=font, fill=255, anchor='ls')
    bbox = m.getbbox()
    if bbox and (bbox[2] > x1 or bbox[1] < y0 - sheet.mm(1)):
        raise RuntimeError(f'подпись не влезла в поле: {bbox} vs {(x0, y0, x1, y1)}')
    return m


# ── PDF: одна CMYK-картинка на страницу ───────────────────────────────
def pdf_str(s):
    return '(' + s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') + ')'


def write_pdf(path, pages, sheet, title):
    """pages: CMYK Image, одинаковые объекты кладутся в файл один раз.
    OutputIntent — зарегистрированное условие FOGRA39 без вшитого профиля
    (8 МБ): для DeviceCMYK этого достаточно, профиль у типографии свой."""
    W, H = sheet.W, sheet.H
    k = 72 / (300 * sheet.k)
    wpt, hpt = W * k, H * k
    a4w, a4h = A4_MM[0] / 25.4 * 72, A4_MM[1] / 25.4 * 72
    tx, ty = (wpt - a4w) / 2, (hpt - a4h) / 2
    num = lambda v: f'{v:.4f}'.rstrip('0').rstrip('.')

    objs = [None] * 4    # 1 catalog, 2 pages, 3 output intent, 4 info

    def add(body):
        objs.append(body)
        return len(objs)

    def stream(dict_body, data):
        return f'<< {dict_body} /Length {len(data)} >>\nstream\n'.encode() + data + b'\nendstream'

    img_ref, kids = {}, []
    for im in pages:
        if id(im) not in img_ref:
            assert im.mode == 'CMYK' and im.size == (W, H)
            data = zlib.compress(im.tobytes(), 6)
            img_ref[id(im)] = add(stream(f'/Type /XObject /Subtype /Image /Width {W} /Height {H} '
                                         f'/ColorSpace /DeviceCMYK /BitsPerComponent 8 /Filter /FlateDecode', data))
        content = add(stream('', f'q {num(wpt)} 0 0 {num(hpt)} 0 0 cm /Im0 Do Q'.encode()))
        box = f'[0 0 {num(wpt)} {num(hpt)}]'
        kids.append(add(f'<< /Type /Page /Parent 2 0 R /MediaBox {box} /BleedBox {box} '
                        f'/TrimBox [{num(tx)} {num(ty)} {num(tx + a4w)} {num(ty + a4h)}] '
                        f'/Resources << /XObject << /Im0 {img_ref[id(im)]} 0 R >> >> '
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


# ── Самопроверка ──────────────────────────────────────────────────────
def check_pdf(path, rasters, sheet):
    """Перечитывает PDF: размер и TrimBox, на странице ровно одна
    CMYK-картинка 300·k ppi, ни шрифтов, ни текста, ни векторов, и пиксели
    картинки совпадают с собранным листом байт в байт."""
    import fitz
    doc = fitz.open(path)
    assert len(doc) == len(rasters), f'{path}: {len(doc)} стр., ждал {len(rasters)}'
    a4 = fitz.Rect(0, 0, A4_MM[0] / 25.4 * 72, A4_MM[1] / 25.4 * 72)
    for n, (page, im) in enumerate(zip(doc, rasters), 1):
        where = f'{os.path.basename(path)} стр. {n}'
        tb = page.trimbox
        assert abs(tb.width - a4.width) < 0.01 and abs(tb.height - a4.height) < 0.01, f'{where}: TrimBox {tb}'
        assert abs((tb.x0 + tb.x1) - page.rect.width) < 0.01, f'{where}: TrimBox не по центру'
        imgs = page.get_images(full=True)
        assert len(imgs) == 1, f'{where}: картинок {len(imgs)}'
        assert not page.get_fonts(), f'{where}: шрифты {page.get_fonts()}'
        assert not page.get_text().strip(), f'{where}: есть текст'
        assert not page.get_drawings(), f'{where}: есть векторы'
        xref, _, w, h, bpc, cs = imgs[0][:6]
        assert cs == 'DeviceCMYK' and bpc == 8 and (w, h) == im.size, f'{where}: {cs} {bpc} {w}×{h}'
        ppi = w / (page.rect.width / 72)
        assert abs(ppi - 300 * sheet.k) < 0.01, f'{where}: {ppi:.2f} ppi'
        pix = fitz.Pixmap(doc, xref)
        assert pix.n == 4 and pix.samples == im.tobytes(), f'{where}: пиксели в PDF не совпали с листом'
    doc.close()


def check_registration(faces, back, sheet, marks, face_cards, back_card, transform):
    """Лицо ↔ рубашка при перевороте по длинной стороне.
    1) ячейки зеркальны: ячейка (r, c) лица и (r, COLS-1-c) рубашки
       занимают на листе одно и то же место;
    2) в каждой ячейке каждого листа стоит ровно своя карта и ровно на своём
       месте — пиксель в пиксель с отдельно переведённой в CMYK картой;
       сдвиг на 1 px (0,08 мм) не пройдёт;
    3) метки и кресты на каждом листе зеркальны сами себе и одинаковы на
       лицах и рубашке (подпись из сравнения вырезается);
    4) вне сетки нет никакой краски, кроме меток и подписи;
    5) фон рисунка рубашки белый, а не бледная плашка."""
    for i in range(COLS * ROWS):
        r, c = divmod(i, COLS)
        (xf, yf), (xb, yb) = sheet.cell(i), sheet.cell(r * COLS + COLS - 1 - c)
        assert (xf, yf) == (sheet.W - xb - sheet.cw, yb), f'ячейка {i + 1}: лицо и рубашка разъехались'

    p = PAD * sheet.k
    cache = {}

    def expected(img):
        if id(img) not in cache:
            cell = Image.new('RGB', (sheet.cw, sheet.ch), 'white')
            cell.paste(img, (p, p))
            cache[id(img)] = np.array(to_cmyk(cell, transform))
        return cache[id(img)]
    blank = np.zeros((sheet.ch, sheet.cw, 4), np.uint8)
    sheets = [('рубашки', back, [back_card] * (COLS * ROWS))]
    sheets += [(f'лица {n}', f, cards) for n, (f, cards) in enumerate(zip(faces, face_cards), 1)]
    for name, im, cards in sheets:
        a = np.array(im)
        for i in range(COLS * ROWS):
            x, y = sheet.cell(i)
            want = expected(cards[i]) if i < len(cards) else blank
            assert np.array_equal(a[y:y + sheet.ch, x:x + sheet.cw], want),                 f'{name}, ячейка {i + 1}: карта не на своём месте или не та'

    x0, y0, x1, y1 = sheet.label_box()
    keep = np.ones((sheet.H, sheet.W), bool)
    keep[sheet.gy:sheet.H - sheet.gy, sheet.gx:sheet.W - sheet.gx] = False
    keep[y0 - sheet.k * 10:y1 + sheet.k * 10, x0:x1] = False
    k_marks = np.array(marks) > 0
    for name, im, _ in sheets:
        a = np.array(im)
        kch = (a[..., 3] > 0) & keep
        assert np.array_equal(kch, k_marks & keep), f'{name}: метки не совпали с эталоном'
        assert np.array_equal(kch, np.fliplr(kch)), f'{name}: метки несимметричны'
        assert not ((a.max(axis=2) > 0) & keep & ~k_marks).any(), f'{name}: краска вне сетки и меток'

    # белый фон рубашки: кайма кадра шириной 2 px почти вся без краски
    fr = expected(back_card)[p:-p, p:-p].max(axis=2) > 0
    ring = np.concatenate([fr[:2].ravel(), fr[-2:].ravel(), fr[:, :2].ravel(), fr[:, -2:].ravel()])
    assert ring.mean() < 0.1, f'фон рубашки не белый: {ring.mean():.0%} каймы кадра в краске'


_proof = []

def soft_proof(cmyk, width_px):
    if not _proof:
        _proof.append(ImageCms.buildTransform(ImageCms.getOpenProfile(ICC), ImageCms.createProfile('sRGB'),
                                              'CMYK', 'RGB', renderingIntent=ImageCms.Intent.PERCEPTUAL))
    rgb = ImageCms.applyTransform(cmyk, _proof[0])
    return rgb.resize((width_px, round(rgb.height * width_px / rgb.width)), Image.LANCZOS)


# ── main ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='Листы A4 3×3 для типографии: лица и рубашки отдельными PDF.')
    ap.add_argument('--lang', choices=('en', 'ru'), default='en')
    ap.add_argument('--per-group', type=int, default=5, help='разных названий из группы; 0 — все')
    ap.add_argument('--ids', type=int, nargs='+', help='конкретные ID вместо отбора по группам')
    ap.add_argument('--qty', action='store_true', help='каждую карту — в количестве qty')
    ap.add_argument('--dpi', type=int, choices=(300, 600), default=300)
    ap.add_argument('--sheet-bleed', type=float, default=5.0, help='белый вылет листа, мм (ottisk: 5)')
    ap.add_argument('--out', default='print', help='папка для PDF')
    ap.add_argument('--name', help='база имени файлов; по умолчанию sheets_<lang>[_test<N>]_<дата>')
    ap.add_argument('--preview', help='папка для PNG soft-proof листов и проверки «на просвет»')
    a = ap.parse_args()
    k = a.dpi // 300

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:   # колода — из самой картотеки, как её видит браузер
        b = p.chromium.launch(executable_path=CHROME)
        pg = b.new_page()
        pg.goto(f'file:///{ROOT.replace(os.sep, "/")}/app.html?embed=0', wait_until='load')
        cards = pg.evaluate('() => CARDS')
        b.close()
    picked = select(cards, a.lang, a.per_group, a.ids, a.qty)
    if not picked:
        sys.exit('нечего печатать')
    shown = (lambda c: c.get('enDesc') or c.get('desc') or '') if a.lang == 'en' else (lambda c: c.get('desc') or '')
    todo = [c['id'] for c in {c['id']: c for c in picked}.values() if 'TODO' in shown(c)]
    if todo:
        print('внимание: в тексте карт есть «TODO», он уйдёт в печать — ' + ', '.join(f'#{i}' for i in todo))
    today = datetime.date.today().isoformat()
    name = a.name or (f'sheets_{a.lang}' + (f'_test{a.per_group}' if a.per_group and not a.ids else '') + f'_{today}')
    print(f'{len(picked)} карт -> {-(-len(picked) // (COLS * ROWS))} лист(ов) A4, {a.dpi} ppi, {a.lang.upper()}')

    shots = render(picked, a.lang, k)
    sheet = Sheet(k, a.sheet_bleed)
    to_cmyk_t = ImageCms.buildTransform(ImageCms.createProfile('sRGB'), ImageCms.getOpenProfile(ICC),
                                        'RGB', 'CMYK', renderingIntent=ImageCms.Intent.PERCEPTUAL)
    marks = sheet.marks()

    per = COLS * ROWS
    chunks = [picked[i:i + per] for i in range(0, len(picked), per)]
    faces, face_cards = [], []
    for n, chunk in enumerate(chunks, 1):
        face_cards.append([shots[c['id']] for c in chunk])
        cmyk = burn_k(to_cmyk(sheet.compose(face_cards[-1]), to_cmyk_t), marks)
        label = f'Samurai vs Ninja · {a.lang.upper()} · faces {n}/{len(chunks)} · {today}'
        faces.append(burn_k(cmyk, draw_label(sheet, label)))
    back_card = back_image(k)
    back = burn_k(to_cmyk(sheet.compose([back_card] * per), to_cmyk_t), marks)

    os.makedirs(a.out, exist_ok=True)
    f_pdf = os.path.join(a.out, f'{name}_faces.pdf')
    b_pdf = os.path.join(a.out, f'{name}_backs.pdf')
    write_pdf(f_pdf, faces, sheet, f'Samurai vs Ninja — faces ({a.lang.upper()})')
    write_pdf(b_pdf, [back], sheet, 'Samurai vs Ninja — backs')

    check_pdf(f_pdf, faces, sheet)
    check_pdf(b_pdf, [back], sheet)
    check_registration(faces, back, sheet, marks, face_cards, back_card, to_cmyk_t)

    mm = lambda v: v / sheet.px_mm
    print(f'страница {mm(sheet.W):.2f} x {mm(sheet.H):.2f} мм, TrimBox A4; '
          f'карта {mm(sheet.cw):.2f} x {mm(sheet.ch):.2f} мм; поля до сетки от края A4: '
          f'{mm(sheet.gx) - mm(sheet.tx):.2f} мм слева/справа, {mm(sheet.gy) - mm(sheet.ty):.2f} мм сверху/снизу')
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
        # одна карта крупно — смотреть мелкий текст
        x, y = sheet.cell(0)
        crop = (x, y, x + sheet.cw, y + sheet.ch)
        soft_proof(faces[0].crop(crop), sheet.cw).save(os.path.join(a.preview, f'{name}_card1_actual.png'))

    print(f_pdf)
    print(b_pdf)


if __name__ == '__main__':
    main()
