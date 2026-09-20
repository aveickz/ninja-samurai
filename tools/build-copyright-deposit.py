# -*- coding: utf-8 -*-
"""Собирает единый PDF для депонирования авторских прав на игру (nris.ru):
титул и содержание, правила, памятка и изображения всех карт — сначала
русская версия, потом общее (рубашки, фигурки и жетоны 3D), потом
английская, в конце — двуязычный реестр карт. Реквизиты (название, автор,
репозиторий) — из copyright.md, там же состав и журнал депонирований.

Два этапа. Сначала куски: каждый раздел — отдельный PDF в
print/copyright_deposit_parts/<ключ>.pdf, рендерится headless Chrome по
file:// (правила и картотека — теми же print-css, что и обычная печать),
картинки сразу пережаты в JPEG. Куски независимы и рисуются параллельно,
каждый в своём процессе. Потом сборка: титул и содержание по фактическим
страницам, каждая страница вписана в A4, сквозной номер снизу справа,
закладки по разделам.

    py -3 tools/build-copyright-deposit.py                 # недостающие куски + сборка → print/copyright_deposit_<дата>.pdf
    py -3 tools/build-copyright-deposit.py list            # куски и состояние кэша
    py -3 tools/build-copyright-deposit.py part cards-ru rules-ru   # перерисовать эти куски
    py -3 tools/build-copyright-deposit.py part --all -j 6 # все куски заново, по шесть разом
    py -3 tools/build-copyright-deposit.py assemble        # только склейка из кэша
    py -3 tools/build-copyright-deposit.py --out X.pdf --quality 75
"""
import os, sys, re, json, html, zipfile, hashlib, argparse, datetime, subprocess, tempfile, shutil, time
import concurrent.futures
import importlib.util
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
    profile = tempfile.mkdtemp(prefix='deposit_chrome_')   # свой профиль: параллельные Chrome не делят lock
    try:
        subprocess.run([CHROME, '--headless', '--disable-gpu', '--hide-scrollbars', '--no-pdf-header-footer',
                        f'--user-data-dir={profile}', f'--virtual-time-budget={budget}', f'--print-to-pdf={out}', url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not os.path.exists(out) or os.path.getsize(out) < 1000:
        raise RuntimeError(f'Chrome не напечатал {url}')
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
/* реестр */
.reg { font-size: 8.5pt; table-layout: fixed; }
.reg td, .reg th { padding: .8mm 1.6mm; }
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
/* 3D-модели */
.models td { vertical-align: middle; text-align: center; padding: 3mm 2mm; }
.models td.cap { text-align: left; width: 38mm; font-weight: 600; }
.models td.cap span { display: block; font-weight: 400; font-family: Consolas, monospace; }
.models img { max-width: 62mm; max-height: 52mm; display: block; margin: 0 auto; }
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
      <li>изображения {card_count} карт колоды и их реестр (название и тип на двух языках);</li>
      <li>рубашки трёх групп карт;</li>
      <li>фигурки и жетоны: 3D-модели для печати, рендеры, тушевые иллюстрации.</li>
    </ol>
  </div>
</div>'''


def page_toc(entries):
    """entries: [(номер, название, страница)]. Группы карт в печатное содержание не идут — только в закладки PDF."""
    li = ''.join(f'<li><span class="n">{n}</span><span class="t">{html.escape(title)}</span>'
                 f'<span class="dots"></span><span class="p">{page}</span></li>' for n, title, page in entries)
    return f'<div class="pb"><h2>Содержание</h2><ul class="toc">{li}</ul></div>'


def desc_html(text):
    t = html.escape(text or '')
    t = re.sub(r'\s*-\s*(ИЛИ|OR)\s*-\s*', r' <b>— \1 —</b> ', t)
    return t.replace('[NL]', '<br>')


def page_registry(cards):
    """Краткий двуязычный реестр: номер, ID, название RU/EN, тип RU/EN, количество — без текстов эффектов,
    они на самих картах."""
    total = sum(c.get('qty') or 0 for c in cards)
    intro = (f'{len(cards)} карт, {total} экземпляров в колоде; порядок — как на страницах с изображениями: '
             f'по группам, внутри группы — в порядке базы карт. Корзина исключена, черновики включены. · '
             f'{len(cards)} cards, {total} copies in the deck; same order as on the image pages.')
    rows = ''
    for i, c in enumerate(cards, 1):
        types = c.get('types') or []
        rows += (f'<tr><td class="id">{i}</td><td class="id">{c.get("id", "")}</td>'
                 f'<td class="name">{html.escape(c.get("title") or "")}</td><td>{html.escape(c.get("enTitle") or "")}</td>'
                 f'<td>{html.escape(", ".join(TYPE_LABEL["ru"].get(t, t) for t in types))}</td>'
                 f'<td>{html.escape(", ".join(TYPE_LABEL["en"].get(t, t) for t in types))}</td>'
                 f'<td class="qty">{c.get("qty", "")}</td></tr>')
    cols = (('№', 'id'), ('ID', 'id'), ('Название', ''), ('Title', ''), ('Тип', ''), ('Type', ''), ('Кол-во', 'qty'))
    th = ''.join(f'<th class="{cls}">{h}</th>' for h, cls in cols)
    colgroup = ''.join(f'<col style="width:{w}">' for w in ('8mm', '10mm', 'auto', 'auto', '30mm', '30mm', '15mm'))
    return (f'<h2>Реестр карт · Card registry</h2><p class="muted small">{intro}</p>'
            f'<table class="reg"><colgroup>{colgroup}</colgroup><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table>')


def gallery(items, cls):
    figs = ''.join(f'<figure><img src="{file_url(src)}" alt=""><figcaption>{cap}</figcaption></figure>' for src, cap in items)
    return f'<div class="gallery {cls}">{figs}</div>'


def page_backs():
    items = [(f'media/backs/{key}.png', f'{ru}<br><span class="muted">{en}</span>') for key, ru, en in BACKS]
    return (f'<h2>Рубашки карт · Card backs</h2>'
            f'<p class="muted small">Печатные файлы рубашек как есть: лист с белыми полями, сама рубашка — '
            f'по центру в пропорции 5:8. Одни на обе языковые версии.</p>' + gallery(items, 'backs'))


def page_figures():
    items = []
    os.makedirs(PARTS_DIR, exist_ok=True)
    for src, cap in MODELS_3MF:
        png = os.path.join(PARTS_DIR, os.path.basename(src) + '.png')
        with zipfile.ZipFile(src) as z:
            open(png, 'wb').write(z.read('Metadata/plate_1.png'))
        items.append((os.path.relpath(png, ROOT), cap))
    return (f'<h2>Фигурки и жетоны · Figures and tokens</h2>'
            f'<p class="muted small">Физические компоненты игры, печатаются на 3D-принтере. '
            f'Превью — с плиты проектов печати; ниже — те же фигурки в правилах и памятке.</p>'
            f'<div class="blk"><h3>3D-модели для печати</h3>{gallery(items, "fig3d")}</div>'
            f'<div class="blk"><h3>Рендеры фигурок (правила и памятка)</h3>{gallery(FIG_RENDERS, "figr")}</div>'
            f'<div class="blk"><h3>Тушевые иллюстрации фигурок (правила)</h3>{gallery(FIG_INK, "figink")}</div>')


def page_models():
    """Рендеры .glb заливкой и сеткой из 3d/preview/ (tools/render-glb.py); недостающие дорисовывает."""
    spec = importlib.util.spec_from_file_location('render_glb', os.path.join(ROOT, 'tools', 'render-glb.py'))
    rg = importlib.util.module_from_spec(spec); spec.loader.exec_module(rg)
    subprocess.run([sys.executable, 'tools/render-glb.py'], check=True, stdout=subprocess.DEVNULL)
    rows = ''
    for key, src, cap, _color, _cam in rg.MODELS:
        rows += (f'<tr><td class="cap">{html.escape(cap)}<span class="muted small">{html.escape(os.path.basename(src))}</span></td>'
                 f'<td><img src="{file_url(f"{rg.OUT}/{key}.png")}" alt=""></td>'
                 f'<td><img src="{file_url(f"{rg.OUT}/{key}-mesh.png")}" alt=""></td></tr>')
    return (f'<h2>3D-модели фигурок · 3D models</h2>'
            f'<p class="muted small">Каждая модель в двух видах: заливка с материалами из файла и сетка — '
            f'светлая заливка с рёбрами треугольников. Рендер three.js в headless Chrome, один ракурс на все модели. · '
            f'Each model shaded with its own materials and as a wireframe over a light fill.</p>'
            f'<table class="models"><thead><tr><th>Фигурка · Figure</th><th>Заливка · Shaded</th><th>Сетка · Mesh</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


# ── Разделы: каждый — отдельный PDF в кэше ──────────────────────────

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


# Раздел: ключ → заголовок (содержание, закладки), как рендерить, язык подпунктов по группам карт,
# входит ли в книгу. Порядок списка = порядок в книге. Рендер описан данными, а не замыканиями:
# куски рисуются в отдельных процессах, и спецификация должна переживать pickle.
#   ('url', <файл относительно корня>, <query>, <virtual-time-budget>)  — страницы проекта как есть
#   ('html', <имя функции page_*>)                                       — служебная страница
PARTS = [
    dict(key='rules-ru', title='Правила игры (рус.)',         how=('url', 'rules/rules.html', '', 10000)),
    dict(key='cheat-ru', title='Памятка игрока (рус.)',        how=('url', 'rules/cheatsheet.html', '', 10000)),
    dict(key='cards-ru', title='Карты (рус.)',                 how=('url', 'app.html', '', 30000), subs='ru'),
    dict(key='backs',    title='Рубашки карт',                 how=('html', 'page_backs')),
    dict(key='figures',  title='Фигурки и жетоны — 3D-модели', how=('html', 'page_figures')),
    dict(key='rules-en', title='Game rules (English)',         how=('url', 'rules/rules-en.html', '', 10000)),
    dict(key='cheat-en', title='Player cheat sheet (English)', how=('url', 'rules/cheatsheet-en.html', '', 10000)),
    dict(key='cards-en', title='Cards (English)',              how=('url', 'app.html', '?lang=en', 30000), subs='en'),
    dict(key='registry', title='Реестр карт · Card registry',  how=('html', 'page_registry')),
    # Пока отдельным PDF, в книгу не входит: рендеры .glb заливкой и сеткой (tools/render-glb.py).
    dict(key='models',   title='3D-модели фигурок · 3D models', how=('html', 'page_models'), book=False),
]
PART_BY_KEY = {p['key']: p for p in PARTS}
CARDS_PER_PAGE = 9      # печать картотеки: сетка 3×3


def part_path(key):
    return os.path.join(PARTS_DIR, key + '.pdf')


def render_part(key, quality):
    """Один раздел: сырой PDF от Chrome → пережатые картинки → print/copyright_deposit_parts/<key>.pdf.
    Запускается в отдельном процессе — всё нужное берёт сам (карты через node, реквизиты из copyright.md)."""
    os.makedirs(PARTS_DIR, exist_ok=True)
    spec = PART_BY_KEY[key]
    how = spec['how']
    t0 = time.time()
    if how[0] == 'url':
        raw = render_url(key, how[1], how[2], how[3])
    else:
        builder = globals()[how[1]]
        body = builder(load_cards()) if how[1] == 'page_registry' else builder()
        raw = render_html(key, body, spec['title'])
    doc = fitz.open(raw)
    n = recompress_images(doc, quality)
    doc.save(part_path(key), garbage=4, deflate=True)
    pages = doc.page_count
    doc.close()
    os.remove(raw)
    return key, pages, n, time.time() - t0


def render_parts(keys, quality, jobs):
    """Куски независимы — каждый в своём процессе с собственным Chrome."""
    print(f'  рисую {len(keys)} разд.: {", ".join(keys)} (параллельно {min(jobs, len(keys))})', flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, min(jobs, len(keys)))) as pool:
        for key, pages, n, sec in pool.map(render_part, keys, [quality] * len(keys)):
            print(f'  ✓ {key:9} {pages:3} стр., {n} картинок в JPEG, {sec:.0f} с', flush=True)


def group_subs(cards, lang):
    """Страницы карт идут по 9 в порядке cards — первая карта группы даёт смещение её страницы."""
    subs, seen = [], set()
    for i, c in enumerate(cards):
        g = c.get('group') or 'action'
        if g not in seen:
            seen.add(g); subs.append((GROUP_LABEL[lang].get(g, g), i // CARDS_PER_PAGE))
    return subs


# ── Сборка книги из кусков ───────────────────────────────────────────

def assemble(out, quality):
    meta = read_meta()
    rev, rev_date = git_rev()
    cards = load_cards()
    book = [p for p in PARTS if p.get('book', True)]
    missing = [p['key'] for p in book if not os.path.exists(part_path(p['key']))]
    if missing:
        sys.exit(f'нет кусков: {", ".join(missing)} — сначала  py -3 tools/build-copyright-deposit.py part {" ".join(missing)}')
    docs = [(p['title'], fitz.open(part_path(p['key'])), group_subs(cards, p['subs']) if p.get('subs') else []) for p in book]
    content_pages = sum(d.page_count for _, d, _ in docs)

    # Титул + содержание: номера страниц зависят от длины самого содержания,
    # поэтому печатаем, считаем страницы и при расхождении печатаем ещё раз.
    front_pages, front = 2, None
    for _ in range(3):
        total = front_pages + content_pages
        entries, page = [], front_pages + 1
        for i, (title, d, _subs) in enumerate(docs, 1):
            entries.append((i, title, page))
            page += d.page_count
        body = page_cover(meta, rev, rev_date, total, len(cards)) + page_toc(entries)
        raw = render_html('front', body, meta['title'])
        if front:
            front.close()   # иначе Windows не даст перезаписать front.pdf
        front = fitz.open(raw); recompress_images(front, quality)
        front.save(part_path('front'), garbage=4, deflate=True); front.close(); os.remove(raw)
        front = fitz.open(part_path('front'))
        if front.page_count == front_pages:
            break
        front_pages = front.page_count
    else:
        sys.exit('титул и содержание не сходятся по числу страниц')

    # Каждая страница вписывается в A4 (альбомные — в альбомный A4), сквозной номер
    # снизу справа, закладки по разделам и группам карт; одинаковые картинки
    # (арт RU и EN карт — один JPEG) схлопывает garbage=4.
    pdf = fitz.open()
    toc, footer_label = [], f'{meta["title"]} · депонирование'
    segoe = fitz.Font(fontfile=SEGOE)
    def add(src, title, subs=()):
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
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    pdf.save(out, garbage=4, deflate=True)
    for _, d, _ in docs: d.close()
    front.close(); pdf.close()

    sha = hashlib.sha256(open(out, 'rb').read()).hexdigest()
    size = os.path.getsize(out) / 1e6
    print(f'\n{out}\n{total} страниц · {size:.1f} МБ · {len(cards)} карт · git {rev}\nSHA-256 {sha}')
    print(f'\nСтрока для журнала в copyright.md:\n| {datetime.date.today():%d.%m.%Y} | nris.ru | — | {os.path.basename(out)} | {total} | {sha[:16]}… | {rev.split()[0]} |')
    extra = [p for p in PARTS if not p.get('book', True) and os.path.exists(part_path(p['key']))]
    for p in extra:
        print(f'отдельно, в книгу не входит: {part_path(p["key"])} — {p["title"]}')


def list_parts():
    for p in PARTS:
        path = part_path(p['key'])
        state = (f'{fitz.open(path).page_count} стр., {datetime.datetime.fromtimestamp(os.path.getmtime(path)):%d.%m %H:%M}'
                 if os.path.exists(path) else 'нет')
        print(f'  {p["key"]:9} {p["title"]:34} {state}{"" if p.get("book", True) else "   (отдельно, в книгу не входит)"}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', nargs='?', choices=['part', 'assemble', 'list'], help='без подкоманды: недостающие куски + сборка')
    ap.add_argument('keys', nargs='*', help='part: какие куски рисовать (пусто — недостающие)')
    ap.add_argument('--all', action='store_true', help='part: все куски заново')
    ap.add_argument('-j', '--jobs', type=int, default=4, help='сколько кусков рисовать одновременно (4)')
    ap.add_argument('--out', help='assemble: куда писать PDF (по умолчанию print/copyright_deposit_<дата>.pdf)')
    ap.add_argument('--quality', type=int, default=85, help='JPEG-качество картинок (85); действует на рисуемые куски')
    args = ap.parse_args()
    if not os.path.exists(CHROME):
        sys.exit(f'Нет Chrome: {CHROME}')
    os.makedirs(PARTS_DIR, exist_ok=True)
    unknown = set(args.keys) - set(PART_BY_KEY)
    if unknown:
        sys.exit(f'неизвестные куски: {", ".join(sorted(unknown))}; есть: {", ".join(PART_BY_KEY)}')

    if args.cmd == 'list':
        list_parts(); return
    if args.cmd in (None, 'part'):
        if args.all:
            keys = list(PART_BY_KEY)
        elif args.keys:
            keys = args.keys
        else:
            keys = [k for k in PART_BY_KEY if not os.path.exists(part_path(k))]
        if keys:
            render_parts(keys, args.quality, args.jobs)
        else:
            print('  все куски на месте — нечего рисовать (part --all или part <ключи>, чтобы заново)')
    if args.cmd in (None, 'assemble'):
        assemble(args.out or os.path.join('print', f'copyright_deposit_{datetime.date.today():%Y-%m-%d}.pdf'), args.quality)


if __name__ == '__main__':
    main()
