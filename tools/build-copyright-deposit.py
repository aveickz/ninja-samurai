# -*- coding: utf-8 -*-
"""Собирает единый PDF для депонирования авторских прав на игру (nris.ru):
титул и содержание, правила и памятка, реестр и изображения всех карт,
рубашки, фигурки и жетоны (3D) — сначала русская версия, потом общее
(рубашки, фигурки), потом английская. Реквизиты (название, автор,
репозиторий) — из copyright.md, там же состав и журнал депонирований.

Всё рендерит headless Chrome по file:// (правила и картотека — теми же
print-css, что и обычная печать), склеивает PyMuPDF: каждая страница
вписывается в A4, снизу справа — сквозной номер, по разделам — закладки.

Разделы рендерятся по одному в кэш print/copyright_deposit_parts/<ключ>.pdf
(уже с пережатыми картинками); сборка берёт готовые куски и перерисовывает
только недостающие — полный прогон картотеки занимает минуту на язык.

    py -3 tools/build-copyright-deposit.py                 # недостающие разделы + сборка → print/copyright_deposit_<дата>.pdf
    py -3 tools/build-copyright-deposit.py --redo cards-ru,registry-ru   # перерисовать эти разделы, остальные из кэша
    py -3 tools/build-copyright-deposit.py --redo all      # всё заново
    py -3 tools/build-copyright-deposit.py --list          # разделы и состояние кэша, без сборки
    py -3 tools/build-copyright-deposit.py --out X.pdf --quality 75
"""
import os, sys, re, json, html, zipfile, hashlib, argparse, datetime, subprocess
import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
SEGOE = r'C:\Windows\Fonts\segoeui.ttf'
PARTS_DIR = os.path.join('print', 'copyright_deposit_parts')
A4 = (595.276, 841.89)          # pt, портрет
MM = 72 / 25.4

# Порядок групп — как в картотеке (js/app.js GROUP_ORDER); печать идёт в этом же порядке.
GROUP_ORDER = ['weapon', 'trap', 'defense', 'stance', 'modifier', 'aoe', 'aura',
               'effect', 'action', 'intervention', 'character', 'role']
TYPE_LABEL = {
    'ru': dict(action='Действие', weapon='Оружие', trap='Ловушка', character='Персонаж',
               modifier='Модификатор', defense='Защита', stance='Стойка', effect='Эффект',
               intervention='Вмешательство', aoe='Групповая', role='Роль', aura='Аура'),
    'en': dict(action='Action', weapon='Weapon', trap='Trap', character='Character',
               modifier='Modifier', defense='Defense', stance='Stance', effect='Effect',
               intervention='Intervention', aoe='Group', role='Role', aura='Aura'),
}
GROUP_LABEL = {
    'ru': dict(weapon='Оружие', trap='Ловушки', defense='Защита', stance='Стойки', modifier='Модификаторы',
               aoe='Групповые', aura='Ауры', effect='Эффекты', action='Действия', intervention='Вмешательства',
               character='Персонажи', role='Роли'),
    'en': dict(weapon='Weapons', trap='Traps', defense='Defense', stance='Stances', modifier='Modifiers',
               aoe='Group cards', aura='Auras', effect='Effects', action='Actions', intervention='Interventions',
               character='Characters', role='Roles'),
}
BACKS = [('default', 'Рубашка карт колоды', 'Deck card back'),
         ('role', 'Рубашка карт ролей', 'Role card back'),
         ('character', 'Рубашка карт персонажей', 'Character card back')]
# Модели для печати (.3mf Bambu) — превью с плиты лежит внутри архива.
MODELS_3MF = [('3d/flag.3mf', 'Знамя ауры'),
              ('3d/heart_bambu.3mf', 'Жетоны жизни'),
              ('3d/honor_bambu.3mf', 'Очки победы'),
              ('3d/poison_prj.3mf', 'Бутылка яда'),
              ('3d/trap.3mf', 'Ловушка — макибиси'),
              ('3d/stencil.3mf', 'Трафарет самурая и ниндзя')]
# Рендеры фигурок для правил/памятки и тушевые иллюстрации.
FIG_RENDERS = [('rules/media/fig/banner.webp', 'Знамя ауры'),
               ('rules/media/fig/banner-green.webp', 'Знамя ауры'),
               ('rules/media/fig/trap.webp', 'Ловушка — макибиси'),
               ('rules/media/fig/poison.webp', 'Бутылка яда'),
               ('rules/media/fig/hearts-arc.webp', 'Жетоны жизни'),
               ('rules/media/fig/vp-fan.webp', 'Очки победы')]
FIG_INK = [('rules/media/fig/ink/banner-fig.webp', 'Знамя ауры'),
           ('rules/media/fig/ink/poison-fig.webp', 'Бутылка яда'),
           ('rules/media/fig/ink/trap-fig.webp', 'Ловушка — макибиси')]


# ── Реквизиты и окружение ────────────────────────────────────────────

def read_meta():
    """«- **Ключ:** значение» из copyright.md; продолжение значения — строки с отступом."""
    text = open('copyright.md', encoding='utf-8').read()
    def field(name):
        m = re.search(r'^\s*-\s*\*\*' + re.escape(name) + r':\*\*\s*(.+?)\s*$((?:\n[ \t]+\S.*)*)', text, re.M)
        return ' '.join((m.group(1) + m.group(2)).split()) if m else ''
    meta = dict(title=field('Название'), alt=field('Рабочее название'), author=field('Автор'),
                kind=field('Вид произведения'), year=field('Год создания'), repo=field('Репозиторий'))
    if not meta['title']:
        sys.exit('copyright.md: не нашёл строку «- **Название:** …»')
    if not meta['author'] or 'заполнить' in meta['author']:
        print('ВНИМАНИЕ: автор в copyright.md не заполнен — на титуле будет прочерк', file=sys.stderr)
        meta['author'] = '—'
    return meta


def git_rev():
    try:
        h = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
        d = subprocess.run(['git', 'log', '-1', '--format=%cd', '--date=format:%d.%m.%Y'], capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True).stdout.strip())
        return h + (' (с незакоммиченными правками)' if dirty else ''), d
    except Exception:
        return '—', '—'


def load_cards():
    """js/cards.js → список карт; читает node, как simulations/engine/export_cards.mjs."""
    js = ("const fs=require('fs');const src=fs.readFileSync('js/cards.js','utf8');"
          "process.stdout.write(JSON.stringify(new Function(src+';return CARDS;')()));")
    out = subprocess.run(['node', '-e', js], capture_output=True, text=True, encoding='utf-8', check=True).stdout
    cards = json.loads(out)
    by_group = {}
    for c in cards:
        by_group.setdefault(c.get('group') or 'action', []).append(c)
    ordered = [c for g in GROUP_ORDER for c in by_group.get(g, [])]
    # то же, что печать из картотеки: корзина не входит, черновики входят
    return [c for c in ordered if 'trash' not in (c.get('tags') or [])]


def chrome_pdf(url, out, budget=10000):
    out = os.path.abspath(out)     # относительный путь Chrome разрешает не от нашего cwd
    subprocess.run([CHROME, '--headless', '--disable-gpu', '--hide-scrollbars', '--no-pdf-header-footer',
                    f'--virtual-time-budget={budget}', f'--print-to-pdf={out}', url],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if not os.path.exists(out) or os.path.getsize(out) < 1000:
        sys.exit(f'Chrome не напечатал {url}')
    return out


def file_url(rel, query=''):
    return 'file:///' + os.path.join(ROOT, rel).replace(os.sep, '/') + query


# ── Служебные страницы — HTML, печатается тем же Chrome ─────────────

CSS = """
@page { size: A4 portrait; margin: 18mm 16mm 20mm 18mm; }
html, body { margin: 0; padding: 0; background: #fff; color: #1a1a1a;
  font-family: "Segoe UI", -apple-system, Roboto, sans-serif; font-size: 10.5pt; line-height: 1.35; }
h1 { font-size: 30pt; font-weight: 600; letter-spacing: .02em; margin: 0 0 4mm; }
h2 { font-size: 16pt; font-weight: 600; margin: 0 0 6mm; padding-bottom: 2mm; border-bottom: .6pt solid #999; }
h3 { font-size: 11.5pt; font-weight: 600; margin: 8mm 0 3mm; }
p { margin: 0 0 3mm; }
a { color: inherit; text-decoration: none; }
.muted { color: #666; }
.small { font-size: 8.5pt; }
.pb { page-break-before: always; break-before: page; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 1.2mm 1.6mm; border-bottom: .4pt solid #ccc; }
th { font-weight: 600; background: #f1f1f1; border-bottom: .6pt solid #888; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; break-inside: avoid; }
/* титул */
.cover { text-align: center; padding-top: 2mm; }
.cover img { width: 100mm; display: block; margin: 0 auto 6mm; }
.cover .kicker { font-size: 12pt; letter-spacing: .25em; text-transform: uppercase; color: #666; margin-bottom: 2mm; }
.cover .alt { font-size: 12pt; color: #555; margin-bottom: 8mm; }
.cover .deposit { font-size: 14pt; font-weight: 600; margin-bottom: 7mm; }
.cover table { width: auto; margin: 0 auto 7mm; font-size: 11pt; }
.cover td { border: 0; padding: 1.2mm 4mm; }
.cover td:first-child { color: #666; text-align: right; white-space: nowrap; }
.cover td:last-child { max-width: 110mm; }
.cover .composition { max-width: 130mm; margin: 0 auto; text-align: left; }
.cover ol { margin: 2mm 0 0; padding-left: 6mm; }
/* содержание */
.toc { list-style: none; margin: 0; padding: 0; font-size: 12pt; }
.toc li { display: flex; align-items: baseline; margin: 0 0 3.2mm; }
.toc .n { width: 9mm; color: #666; flex: none; }
.toc .t { flex: none; }
.toc .dots { flex: 1; border-bottom: .5pt dotted #999; margin: 0 2mm; transform: translateY(-1mm); }
.toc .p { flex: none; font-variant-numeric: tabular-nums; }
.toc .run { display: block; padding-left: 9mm; font-size: 9.5pt; color: #555; margin: -2mm 0 3.2mm; line-height: 1.5; }
.toc .run b { font-weight: 400; color: #999; margin: 0 .5mm; }
/* реестр */
.reg { font-size: 8.5pt; table-layout: fixed; }
.reg td.id, .reg td.qty, .reg th.id, .reg th.qty { text-align: right; }
.reg td.name { font-weight: 600; }
/* рубашки, фигурки */
.gallery { display: flex; flex-wrap: wrap; gap: 6mm 5mm; align-items: flex-end; justify-content: center; }
.gallery figure { margin: 0; text-align: center; page-break-inside: avoid; break-inside: avoid; }
.gallery figcaption { font-size: 9pt; margin-top: 1.5mm; }
.gallery img { display: block; margin: 0 auto; }
.backs figure { width: 54mm; }
.backs img { width: 54mm; box-shadow: 0 0 0 .3pt #bbb; }
.blk { page-break-inside: avoid; break-inside: avoid; }
.fig3d figure { width: 50mm; }
.fig3d img { width: 38mm; }
.figr figure { width: 25mm; }
.figr img { height: 28mm; width: auto; }
.figink figure { width: 44mm; }
.figink img { height: 46mm; width: auto; }
"""


def html_doc(body, title):
    return ('<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>' + html.escape(title) +
            '</title><style>' + CSS + '</style></head><body>' + body + '</body></html>')


def page_cover(meta, rev, rev_date, total_pages, card_count):
    today = datetime.date.today().strftime('%d.%m.%Y')
    repo = meta['repo']
    rows = [('Автор', html.escape(meta['author'])),
            ('Вид произведения', html.escape(meta['kind'])),
            ('Год создания', html.escape(meta['year'])),
            ('Публичный репозиторий', f'<a href="{html.escape(repo)}">{html.escape(repo)}</a>' if repo else ''),
            ('Версия материалов', html.escape(f'git {rev} от {rev_date}')),
            ('Дата сборки файла', today),
            ('Объём', f'{total_pages} страниц A4')]
    tr = ''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in rows if v)
    return f'''
<div class="cover">
  <img src="{file_url('rules/media/cover.webp')}" alt="">
  <p class="kicker">Настольная карточная игра</p>
  <h1>{html.escape(meta['title'])}</h1>
  <p class="alt">рабочее название «{html.escape(meta['alt'])}»</p>
  <p class="deposit">Материалы для депонирования авторских прав</p>
  <table>{tr}</table>
  <div class="composition">
    <p>В файле — всё произведение целиком, а не ссылки на него:</p>
    <ol>
      <li>правила игры и памятка игрока — русский оригинал и английский перевод;</li>
      <li>реестр и изображения {card_count} карт колоды: название, тип, текст эффекта, иллюстрация;</li>
      <li>рубашки трёх групп карт;</li>
      <li>фигурки и жетоны: 3D-модели для печати, рендеры, тушевые иллюстрации.</li>
    </ol>
  </div>
</div>'''


def page_toc(entries):
    """entries: [(номер, название, страница, [(подпункт, страница)…])]; подпункты — одной строкой под разделом."""
    li = ''
    for n, title, page, subs in entries:
        li += (f'<li><span class="n">{n}</span><span class="t">{html.escape(title)}</span>'
               f'<span class="dots"></span><span class="p">{page}</span></li>')
        if subs:
            li += '<span class="run">' + '<b>·</b>'.join(f'{html.escape(t)}&nbsp;{p}' for t, p in subs) + '</span>'
    return f'<div class="pb"><h2>Содержание</h2><ul class="toc">{li}</ul></div>'


def desc_html(text):
    t = html.escape(text or '')
    t = re.sub(r'\s*-\s*(ИЛИ|OR)\s*-\s*', r' <b>— \1 —</b> ', t)
    return t.replace('[NL]', '<br>')


def page_registry(cards, lang):
    L = TYPE_LABEL[lang]
    if lang == 'ru':
        head, cols = 'Реестр карт', ('№', 'ID', 'Название', 'Тип', 'Кол-во', 'Текст эффекта')
    else:
        head, cols = 'Card registry', ('#', 'ID', 'Title', 'Type', 'Qty', 'Effect text')
    total = sum(c.get('qty') or 0 for c in cards)
    intro = (f'{len(cards)} карт, {total} экземпляров в колоде. Порядок — как в картотеке и на страницах '
             f'с изображениями ниже: по группам, внутри группы — в порядке базы карт. '
             f'Корзина исключена, черновики включены.' if lang == 'ru' else
             f'{len(cards)} cards, {total} copies in the deck. Same order as in the card browser and on the '
             f'image pages below: by group, within a group — as in the card database.')
    rows = ''
    for i, c in enumerate(cards, 1):
        title = c.get('enTitle') if lang == 'en' and c.get('enTitle') else c.get('title', '')
        desc = c.get('enDesc') if lang == 'en' and c.get('enDesc') else c.get('desc', '')
        types = ', '.join(L.get(t, t) for t in (c.get('types') or []))
        rows += (f'<tr><td class="id">{i}</td><td class="id">{c.get("id", "")}</td>'
                 f'<td class="name">{html.escape(title)}</td><td>{html.escape(types)}</td>'
                 f'<td class="qty">{c.get("qty", "")}</td><td>{desc_html(desc)}</td></tr>')
    th = ''.join(f'<th class="{"id" if i in (0, 1) else "qty" if i == 4 else ""}">{h}</th>' for i, h in enumerate(cols))
    colgroup = ''.join(f'<col style="width:{w}">' for w in ('7mm', '9mm', '34mm', '24mm', '12mm', 'auto'))
    return (f'<h2>{head}</h2><p class="muted small">{intro}</p><table class="reg"><colgroup>{colgroup}</colgroup>'
            f'<thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table>')


def gallery(items, cls):
    figs = ''.join(f'<figure><img src="{file_url(src)}" alt=""><figcaption>{cap}</figcaption></figure>' for src, cap in items)
    return f'<div class="gallery {cls}">{figs}</div>'


def page_backs():
    items = [(f'media/backs/{key}.png', f'{ru}<br><span class="muted">{en}</span>') for key, ru, en in BACKS]
    return (f'<h2>Рубашки карт · Card backs</h2>'
            f'<p class="muted small">Печатные файлы рубашек как есть: лист с белыми полями, сама рубашка — '
            f'по центру в пропорции 5:8. Одни на обе языковые версии.</p>' + gallery(items, 'backs'))


def page_figures(work):
    items = []
    for src, cap in MODELS_3MF:
        png = os.path.join(work, os.path.basename(src) + '.png')
        with zipfile.ZipFile(src) as z:
            open(png, 'wb').write(z.read('Metadata/plate_1.png'))
        items.append((os.path.relpath(png, ROOT), cap))
    return (f'<h2>Фигурки и жетоны · Figures and tokens</h2>'
            f'<p class="muted small">Физические компоненты игры, печатаются на 3D-принтере. '
            f'Превью — с плиты проектов печати; ниже — те же фигурки в правилах и памятке.</p>'
            f'<div class="blk"><h3>3D-модели для печати</h3>{gallery(items, "fig3d")}</div>'
            f'<div class="blk"><h3>Рендеры фигурок (правила и памятка)</h3>{gallery(FIG_RENDERS, "figr")}</div>'
            f'<div class="blk"><h3>Тушевые иллюстрации фигурок (правила)</h3>{gallery(FIG_INK, "figink")}</div>')


# ── Разделы: рендер по одному в кэш ─────────────────────────────────

def recompress_images(doc, quality):
    """Flate-картинки (Chrome кладёт PNG как есть — 200 МБ на прогон картотеки)
    → JPEG того же размера, правкой объекта по xref: ссылки из вложенных
    XObject остаются целы. Document.rewrite_images так нельзя — он теряет
    Pattern-ресурсы вложенных форм (градиенты плашек), и MuPDF сыплет
    «cannot find Pattern resource». Маски прозрачности (SMask) не трогаем."""
    done, n = set(), 0
    for pno in range(doc.page_count):
        for xref, _smask, _w, _h, bpc, _cs, _alt, _name, filt, *_ in doc.get_page_images(pno, full=True):
            if xref in done:
                continue
            done.add(xref)
            if bpc != 8 or filt in ('DCTDecode', 'JPXDecode') or doc.xref_get_key(xref, 'ImageMask')[1] == 'true':
                continue
            pix = fitz.Pixmap(doc, xref)
            if pix.alpha:
                pix = fitz.Pixmap(pix, 0)
            if pix.n not in (1, 3):
                pix = fitz.Pixmap(fitz.csRGB, pix)
            doc.update_stream(xref, pix.tobytes('jpeg', jpg_quality=quality), compress=False)
            doc.xref_set_key(xref, 'Filter', '/DCTDecode')
            doc.xref_set_key(xref, 'DecodeParms', 'null')
            doc.xref_set_key(xref, 'ColorSpace', '/DeviceRGB' if pix.n == 3 else '/DeviceGray')
            doc.xref_set_key(xref, 'BitsPerComponent', '8')
            n += 1
    return n


def render_html(name, body, title, budget=6000):
    path = os.path.abspath(os.path.join(PARTS_DIR, name + '.html'))
    open(path, 'w', encoding='utf-8').write(html_doc(body, title))
    return chrome_pdf('file:///' + path.replace(os.sep, '/'), os.path.join(PARTS_DIR, name + '.raw.pdf'), budget=budget)


def render_url(name, rel, query='', budget=10000):
    return chrome_pdf(file_url(rel, query), os.path.join(PARTS_DIR, name + '.raw.pdf'), budget=budget)


def parts_spec(cards):
    """Ключ → заголовок для содержания и закладок, рендер сырого PDF, язык подпунктов по группам карт."""
    return [
        ('rules-ru',    'Правила игры (рус.)',          lambda: render_url('rules-ru', 'rules/rules.html'), None),
        ('cheat-ru',    'Памятка игрока (рус.)',         lambda: render_url('cheat-ru', 'rules/cheatsheet.html'), None),
        ('registry-ru', 'Реестр карт (рус.)',            lambda: render_html('registry-ru', page_registry(cards, 'ru'), 'Реестр карт'), None),
        ('cards-ru',    'Карты (рус.)',                  lambda: render_url('cards-ru', 'app.html', budget=30000), 'ru'),
        ('backs',       'Рубашки карт',                  lambda: render_html('backs', page_backs(), 'Рубашки'), None),
        ('figures',     'Фигурки и жетоны — 3D-модели',  lambda: render_html('figures', page_figures(PARTS_DIR), 'Фигурки'), None),
        ('rules-en',    'Game rules (English)',          lambda: render_url('rules-en', 'rules/rules-en.html'), None),
        ('cheat-en',    'Player cheat sheet (English)',  lambda: render_url('cheat-en', 'rules/cheatsheet-en.html'), None),
        ('registry-en', 'Card registry (English)',       lambda: render_html('registry-en', page_registry(cards, 'en'), 'Card registry'), None),
        ('cards-en',    'Cards (English)',               lambda: render_url('cards-en', 'app.html', '?lang=en', budget=30000), 'en'),
    ]


def build_part(key, render, quality):
    """Сырой PDF от Chrome → пережатые картинки → print/copyright_deposit_parts/<key>.pdf."""
    raw = render()
    doc = fitz.open(raw)
    recompress_images(doc, quality)
    dst = os.path.join(PARTS_DIR, key + '.pdf')
    doc.save(dst, garbage=4, deflate=True)
    doc.close()
    os.remove(raw)
    return dst


def group_subs(cards, lang):
    """Страницы карт идут по 9 в порядке cards — первая карта группы даёт смещение её страницы."""
    subs, seen = [], set()
    for i, c in enumerate(cards):
        g = c.get('group') or 'action'
        if g not in seen:
            seen.add(g); subs.append((GROUP_LABEL[lang].get(g, g), i // 9))
    return subs


# ── Сборка ───────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', help='куда писать PDF (по умолчанию print/copyright_deposit_<дата>.pdf)')
    ap.add_argument('--redo', default='', help='какие разделы перерисовать: ключи через запятую или all')
    ap.add_argument('--list', action='store_true', help='показать разделы и состояние кэша, без сборки')
    ap.add_argument('--quality', type=int, default=85, help='JPEG-качество картинок (85); действует на перерисовываемые разделы')
    args = ap.parse_args()

    if not os.path.exists(CHROME):
        sys.exit(f'Нет Chrome: {CHROME}')
    os.makedirs(PARTS_DIR, exist_ok=True)
    meta = read_meta()
    rev, rev_date = git_rev()
    cards = load_cards()
    spec = parts_spec(cards)
    keys = [k for k, *_ in spec]

    redo = set(keys) if args.redo == 'all' else {k.strip() for k in args.redo.split(',') if k.strip()}
    if redo - set(keys):
        sys.exit(f'неизвестные разделы: {", ".join(sorted(redo - set(keys)))}; есть: {", ".join(keys)}')
    if args.list:
        for k, title, *_ in spec:
            p = os.path.join(PARTS_DIR, k + '.pdf')
            state = (f'{fitz.open(p).page_count} стр., {datetime.datetime.fromtimestamp(os.path.getmtime(p)):%d.%m %H:%M}'
                     if os.path.exists(p) else 'нет')
            print(f'  {k:12} {title:34} {state}')
        return

    # 1. Разделы: из кэша, недостающие и запрошенные — заново.
    docs = []
    for key, title, render, lang in spec:
        dst = os.path.join(PARTS_DIR, key + '.pdf')
        if key in redo or not os.path.exists(dst):
            print(f'  … {key}' + (' (картотека, ~1 мин)' if key.startswith('cards') else ''), flush=True)
            dst = build_part(key, render, args.quality)
        docs.append((title, fitz.open(dst), group_subs(cards, lang) if lang else []))
    content_pages = sum(d.page_count for _, d, _ in docs)

    # 2. Титул + содержание: номера страниц зависят от длины самого содержания,
    #    поэтому печатаем, считаем страницы и при расхождении печатаем ещё раз.
    front_pages, front = 2, None
    for _ in range(3):
        total = front_pages + content_pages
        entries, page = [], front_pages + 1
        for i, (title, d, subs) in enumerate(docs, 1):
            entries.append((i, title, page, [(t, page + off) for t, off in subs]))
            page += d.page_count
        body = page_cover(meta, rev, rev_date, total, len(cards)) + page_toc(entries)
        print('  … титул и содержание', flush=True)
        if front:
            front.close()   # иначе Windows не даст перезаписать front.pdf
        front = fitz.open(build_part('front', lambda: render_html('front', body, meta['title']), args.quality))
        if front.page_count == front_pages:
            break
        front_pages = front.page_count
    else:
        sys.exit('титул и содержание не сходятся по числу страниц')

    # 3. Склейка: каждая страница вписывается в A4 (альбомные — в альбомный A4),
    #    сквозной номер снизу справа, закладки по разделам; одинаковые картинки
    #    (арт RU и EN карт — один JPEG) схлопывает garbage=4.
    pdf = fitz.open()
    toc, footer_label = [], f'{meta["title"]} · депонирование'
    segoe = fitz.Font(fontfile=SEGOE)
    def add(src, title=None, subs=()):
        if title:
            toc.append([1, title, pdf.page_count + 1])
        toc.extend([2, t, pdf.page_count + 1 + off] for t, off in subs)
        for i in range(src.page_count):
            r = src[i].rect
            W, H = (A4[1], A4[0]) if r.width > r.height else A4
            page = pdf.new_page(width=W, height=H)
            k = min(W / r.width, H / r.height)
            w, h = r.width * k, r.height * k
            x0, y0 = (W - w) / 2, (H - h) / 2
            page.show_pdf_page(fitz.Rect(x0, y0, x0 + w, y0 + h), src, i)
            n = pdf.page_count
            if n > 1:   # титул без номера
                text = f'{footer_label} · {n} / {total}'
                tw = segoe.text_length(text, fontsize=7)
                page.insert_text((W - 8 * MM - tw, H - 5 * MM), text, fontsize=7, fontname='segoe',
                                 fontfile=SEGOE, color=(0.45, 0.45, 0.45))
    add(front, 'Титул и содержание')
    for title, d, subs in docs:
        add(d, title, subs)
    assert pdf.page_count == total, (pdf.page_count, total)
    pdf.set_toc(toc)
    pdf.set_metadata(dict(title=f'{meta["title"]} — материалы для депонирования', author=meta['author'],
                          subject='Настольная карточная игра: правила, карты, рубашки, фигурки',
                          keywords='депонирование, авторское право, настольная игра',
                          creator='tools/build-copyright-deposit.py', producer='PyMuPDF',
                          creationDate=fitz.get_pdf_now(), modDate=fitz.get_pdf_now()))
    pdf.subset_fonts()
    out = args.out or os.path.join('print', f'copyright_deposit_{datetime.date.today():%Y-%m-%d}.pdf')
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    pdf.save(out, garbage=4, deflate=True)
    for _, d, _ in docs: d.close()
    front.close(); pdf.close()

    sha = hashlib.sha256(open(out, 'rb').read()).hexdigest()
    size = os.path.getsize(out) / 1e6
    print(f'\n{out}\n{total} страниц · {size:.1f} МБ · {len(cards)} карт · git {rev}\nSHA-256 {sha}')
    print(f'\nСтрока для журнала в copyright.md:\n| {datetime.date.today():%d.%m.%Y} | nris.ru | — | {os.path.basename(out)} | {total} | {sha[:16]}… | {rev.split()[0]} |')


if __name__ == '__main__':
    main()
