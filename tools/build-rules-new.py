# -*- coding: utf-8 -*-
"""Запуск: py -3 tools/build-rules-new.py

Собирает rules/rules.html (RU, оригинал) и rules/rules-en.html (EN,
перевод) — предпечатную вёрстку правил. Текст глав берётся как есть из
rules/content-ru.html и rules/content-en.html (там и правится текст; сами
rules*.html — результат сборки, руками не трогать).

Модель — не веб-поток, а страницы: каждая страница — фиксированный
контейнер A5 портрет (section.sheet), на экране они стоят разворотами по
две (div.spread), на печати — по одной на лист. Главы раскладываются по
страницам ВРУЧНУЮ в PAGES; автоматического переноса нет: что не влезло —
выезжает за низ страницы и остаётся видно, переносить руками.

Титул — один по центру, без номера. Дальше нумерация с 1: нечётные страницы —
левые (широкое поле слева под значки и карты, корешок справа), чётные —
правые (корешок слева, поле справа). Последняя — «Конец» — как титул, одна
по центру. Брошюра печатается на сложенных пополам листах A4, по четыре
страницы на лист, поэтому общее число страниц (титул + текст + «Конец»)
добивается пустыми страницами перед «Концом» до кратного четырём.

Добавляет: значки типов и карты-примеры на поле, бледный фон главы,
иероглиф-водяной знак, раздел «Стол во время партии» (table_fig.py),
цепочки порядка расчёта."""
import os, re, sys, glob
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import table_fig
from PIL import Image

os.chdir(os.path.dirname(HERE))   # корень репозитория

# ---------- фоны глав: rules/media/bg/<key>.webp ----------
# Нет файла — берём последний PNG, сгенерированный /img (локальный путь
# автора); в репозитории лежат готовые webp, так что обычно ветка не нужна.
os.makedirs('rules/media/bg', exist_ok=True)
BG_KEY = {'weapons': 'attack', 'turn': 'cards'}          # глава → имя файла, если отличается
def bg_path(cid):
    key = BG_KEY.get(cid, cid)
    dst = f'rules/media/bg/{key}.webp'
    if not os.path.exists(dst):
        cands = sorted(glob.glob(os.path.expanduser(rf'~\.claude\imagegen\out\*_bg_{key}.png')))
        if not cands:
            return None
        im = Image.open(cands[-1]).convert('RGBA')
        im.thumbnail((1100, 1100), Image.LANCZOS)
        im.save(dst, 'WEBP', quality=82, method=6)
        print('bg', key, im.size, os.path.getsize(dst) // 1024, 'KB')
    return dst.replace('rules/', '')

# ---------- конфиг глав (общий для языков) ----------
# icons — значки главы в строке заголовка: ('ic', ключ группы/бейджа) или ('mk', файл в media/)
# cards — ID карт-примеров (превью в rules/media/cards/, см. render-card-previews.py)
#         или рубашки 'back' / 'back-role' / 'back-character' (оттуда же, `render-card-previews.py backs`);
#         список — все на первом срезе, словарь {начало_среза: [id]} — по срезам
# layout — 'fan' (веером, для коротких глав) или 'stack' (лесенкой вниз); тоже
#         может быть словарём по срезам
CH = {
 'about':         dict(icons=[],                                        cards=[]),
 'setup':         dict(layout={0: 'fan', 6: 'fan'}, icons=[],   # сердце и очко стоят у своих подзаголовков (INLINE)
                       cards={0: [202, 200, 'back-role'], 6: [137, 135, 'back-character']}),   # роли и их рубашка — у «Распределения ролей», персонажи и их рубашка — у «Выбора персонажей»; рубашка последней — сверху, видна целиком
 'table':         dict(icons=[],                                        cards=[]),   # стол во время партии (глава собирается из table_fig)
 'flow':          dict(icons=[],                                        cards=[]),
 'turn':          dict(layout={0: 'fan', 2: 'fan'}, icons=[],
                       cards={0: [109, 84], 2: ['back', 'back']}),   # у хода — действие «Саке» и групповое «Чайная церемония» сверху; у «Набора карт» — две рубашки
 'death':         dict(icons=[],                                        cards=[]),
 'players':       dict(icons=[],                                        cards=[]),
 'weapons':       dict(layout={0: 'stack', 10: 'fan'}, icons=[[('ic','weapon'),('ic','modifier')]],
                       cards={0: [1, 32, 31], 10: [70, 64]}),   # меч, сюрикен, отравленное яри (два режима); у подраздела «Модификатор» (срез с блока 10) — два модификатора
 'defense':       dict(icons=[[('ic','defense')]],                      cards=[50, 48]),   # защита с эффектом и простая «Защита» — сверху, она основная
 'thrust':        dict(icons=[[('ic','thrust')]],                       cards=[90, 124]),   # «Боевой крик» и «Удар дракона» — карты с выпадом
 'traps':         dict(icons=[[('ic','trap')]],                         cards=[43, 41], fig=('trap-fig', 17, 1, 4)),   # фигурка макибиси тушью — в углу главы, чуть левее края
 'stances':       dict(icons=[[('ic','stance')]],                       cards=[60, 1166]),   # «Лучник» справа, сверху — виден целиком
 'group':         dict(icons=[[('ic','aoe')]],                          cards=[83, 82]),   # «Потасовка» и «Миротворцы» сверху
 'effects':       dict(icons=[[('ic','effect')]],                       cards=[92, 91]),   # «Противоядие» внутри, «Метка убийцы» сверху
 'poison':        dict(icons=[[('ic','poison')]],                       cards=[116, 64], fig=('poison-fig', 22, 1, 3, 6)),   # фигурка яда тушью — крупно, под картами, чуть ниже и правее списка
 'interventions': dict(layout='stack', icons=[[('ic','intervention')]], cards=[121, 124]),
 'auras':         dict(icons=[[('ic','aura')]],                        cards=[1209, 1206], fig=('banner-fig', 13, 2)),   # «Часовой» внутри, «Дымовая завеса» сверху; фигурка знамени тушью — в углу
 'conditional':   dict(layout='stack', icons=[[('ic','rolectx'),('ic','hpctx'),('ic','charges'),('ic','charctx')]], cards=[125, 3094, 112]),   # внизу «Сапёр» — пример условия по имени персонажа (Иё)
 'order':         dict(icons=[],                                        cards=[]),
}

# ---------- раскладка по страницам (руками) ----------
# Элемент страницы: '__title__' — титульный лист (один на странице), '__end__' —
# завершающий лист «Конец» (тоже один по центру; перед ним сборщик добавляет
# пустые страницы, пока общее число страниц не станет кратным четырём — так
# печатается брошюра из сложенных пополам A4);
# '__cover__' — шапка первой страницы текста (тот же рисунок, что на титуле); 'id' — глава целиком;
# ('id', a, b) — срез главы: блоки тела с a по b (не включая), нумерация
# блоков тела с нуля, без h2. Первый срез несёт заголовок и колонку на
# поле, последний — иероглиф. Что не влезает — выезжает вниз, видно.
# Высоты блоков смотреть в браузере: getBoundingClientRect по .chapter-body > *.
PAGES = [
    ['__title__'],                      # титул: рисунок, название, подзаголовок — без номера, в счёт не идёт
    ['__cover__', 'about', ('setup', 0, 4)],   # шапка с рисунком, об игре, подготовка: роли
    [('setup', 4, 6), ('setup', 6, None), 'flow'],   # рассадка; персонажи и жетоны; партия и её окончание
    [('turn', 0, 2), ('turn', 2, None), 'death'],   # ход; набор карт и восстановление — со своими рубашками; смерть
    ['table'],                       # стол во время партии — один на странице
    [('weapons', 0, 10)],            # атака: оружие, два режима, сложность
    [('weapons', 10, None), 'defense', 'thrust'],   # модификатор и любимое оружие со своими картами; защита; выпад
    ['traps', 'stances', 'group'],   # ловушки, стойки, групповые действия
    ['effects', 'poison'],
    ['interventions', 'auras'],
    ['conditional'],
    ['order', 'players'],           # неравные команды — редкость, в самый конец
    ['__end__'],                    # «Конец» — задняя обложка, одна по центру
]

def top_level_blocks(html):
    """Режет HTML тела главы на блоки верхнего уровня (p, h4, aside, table,
    ul, div, figure, ol…). Считает глубину по открывающим/закрывающим тегам,
    поэтому вложенные списки и таблицы остаются целыми."""
    blocks, depth, start = [], 0, None
    tag_re = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)[^>]*?(/?)>')
    for m in tag_re.finditer(html):
        closing, name, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        void = name in ('img', 'br', 'hr', 'input', 'meta', 'link') or selfclose
        if not closing and depth == 0 and not void:
            start = m.start()
        if closing:
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(html[start:m.end()]); start = None
        elif not void:
            depth += 1
    return blocks

def part_cards(cfg, a):
    """Карты и раскладка для среза, начинающегося с блока a."""
    cards, layout = cfg['cards'], cfg.get('layout', 'fan')
    if isinstance(cards, dict):
        cards = cards.get(a, [])
    elif a != 0:
        cards = []
    if isinstance(layout, dict):
        layout = layout.get(a, 'fan')
    return cards, layout

# высота колонки на поле — чтобы срез главы был не ниже своих карт
def side_height_mm(icon_rows, n, layout):
    h = icon_rows * 9 + max(icon_rows - 1, 0) * 1.5     # значки на поле 9 мм, зазор 1.5
    if n:
        step = 21.6 if n >= 5 else 26.1                    # пять карт лесенкой — плотнее (.n5 в CSS)
        cards = (32.6 + (n - 1) * step) if layout == 'stack' else {1: 32.6, 2: 35, 3: 36}.get(n, 36)
        h += (2 if icon_rows else 0) + 1 + cards
    return round(h + 1, 1)

BANNER = '<img class="mk fig-inline" src="media/fig/banner.webp" alt="">'   # фигурка знамени в строке текста
POISON = '<img class="mk fig-inline poison" src="media/fig/poison.webp" alt="">'   # зелёная фигурка яда в строке текста
TRAP = '<img class="mk fig-inline trap" src="media/fig/trap.webp" alt="">'         # фигурка макибиси в строке текста

def ic(kind, key):
    if kind == 'ic':
        return f'<i class="ic" data-b="{key}"></i>'
    return f'<img class="mk" src="../media/{key}" alt="">'

def heading_icons(rows):
    """Значки главы — одним рядом в строке заголовка, после штриха."""
    flat = [i for r in rows for i in r]
    if not flat:
        return ''
    return '<span class="h-icons">' + ''.join(ic(*i) for i in flat) + '</span>'

def card_fan(ids, lang, layout='fan'):
    """Карты-примеры на поле: WebP из rules/media/cards/ (tools/render-card-previews.py).
    fan — веером с поворотом (короткие главы), stack — лесенкой вниз (длинные)."""
    if not ids:
        return ''
    n = len(ids)
    items = []
    for i, cid in enumerate(ids):
        k = i - (n - 1) / 2           # -1, 0, 1 для трёх карт
        # рубашки ('back', 'back-role', 'back-character') — одни на оба языка
        suffix = '-en' if lang == 'en' and not str(cid).startswith('back') else ''
        src = f'media/cards/{cid}{suffix}.webp'
        items.append(f'<div class="card-embed" style="--k:{k:g};--i:{i}"><img src="{src}" alt=""></div>')
    return f'<div class="side-cards {layout} n{n}">' + ''.join(items) + '</div>'

# значки в тексте — точечные вставки по фразам (глава, было, стало)
# Значки в строке текста — только чужие для главы (защита и яд в «Оружии», сердце в
# «Подготовке»…): свой значок главы уже стоит в её заголовке, в тексте не дублируется.
INLINE = {
 'ru': [
  ('weapons', 'наибольшая <b>сложность</b>, которую оно берёт, и сила атаки.', 'наибольшая <b>сложность</b>, которую оно берёт ' + ic('mk','icons/complexity1.svg') + ', и сила атаки ' + ic('mk','icons/dmg2.svg') + '.'),
  ('weapons', 'Метательное оружие берёт любую сложность.', 'Метательное оружие ' + ic('mk','ranged.png') + ' берёт любую сложность.'),
  ('weapons', 'либо отбивает атаку картой защиты', 'либо отбивает атаку картой защиты ' + ic('ic','defense')),
  ('weapons', 'Оружие также может быть усилено ядом.', 'Оружие также может быть усилено ядом ' + ic('ic','poison') + '.'),
  ('weapons', 'картой-модификатором с красной плашкой;', 'картой-модификатором ' + ic('ic','modifier') + ' с красной плашкой;'),
  ('auras', 'сверху ставится фигурка знамени', 'сверху ставится фигурка знамени ' + BANNER),
  ('poison', 'помечается фигуркой яда поверх', 'помечается фигуркой яда ' + POISON + ' поверх'),
  ('traps', 'и поставив на неё фигурку ловушки.', 'и поставив на неё фигурку ловушки ' + TRAP + '.'),
  ('setup', 'Цифра внутри сердца — максимум', 'Цифра внутри сердца ' + ic('ic','hp') + ' — максимум'),
  ('setup', '<h4>Выставление жетонов</h4>', '<h4>Выставление жетонов<span class="h-icons">' + ic('mk','hp.png') + ic('mk','winpoint.png') + '</span></h4>'),   # сначала жизни, потом очки
  ('conditional', '<h4>Бонусы по фракции</h4>', '<h4>Бонусы по фракции<span class="h-icons">' + ic('ic','rolectx') + '</span></h4>'),
  ('conditional', '<h4>Контекст здоровья</h4>', '<h4>Контекст здоровья<span class="h-icons">' + ic('ic','hpctx') + '</span></h4>'),
  ('conditional', '<h4>Счёт по столу</h4>', '<h4>Счёт по столу<span class="h-icons">' + ic('ic','charges') + '</span></h4>'),
  ('conditional', '<h4>Условие по имени</h4>', '<h4>Условие по имени<span class="h-icons">' + ic('ic','charctx') + '</span></h4>'),
 ],
 'en': [
  ('weapons', 'the highest <b>complexity</b> it can handle and its attack power.', 'the highest <b>complexity</b> it can handle ' + ic('mk','icons/complexity1.svg') + ' and its attack power ' + ic('mk','icons/dmg2.svg') + '.'),
  ('weapons', 'Thrown weapons handle any complexity.', 'Thrown weapons ' + ic('mk','ranged.png') + ' handle any complexity.'),
  ('weapons', 'or blocks the attack with a Defense card', 'or blocks the attack with a Defense card ' + ic('ic','defense')),
  ('weapons', 'Weapons can also be strengthened with poison.', 'Weapons can also be strengthened with poison ' + ic('ic','poison') + '.'),
  ('weapons', 'Modifier card with a red banner;', 'Modifier card ' + ic('ic','modifier') + ' with a red banner;'),
  ('auras', 'with the banner figurine on top', 'with the banner figurine ' + BANNER + ' on top'),
  ('poison', 'marked with the poison figurine placed', 'marked with the poison figurine ' + POISON + ' placed'),
  ('traps', 'the trap figurine on top of it.', 'the trap figurine ' + TRAP + ' on top of it.'),
  ('setup', 'The number inside the heart is', 'The number inside the heart ' + ic('ic','hp') + ' is'),
  ('setup', '<h4>Setting out tokens</h4>', '<h4>Setting out tokens<span class="h-icons">' + ic('mk','hp.png') + ic('mk','winpoint.png') + '</span></h4>'),
  ('conditional', '<h4>Faction bonuses</h4>', '<h4>Faction bonuses<span class="h-icons">' + ic('ic','rolectx') + '</span></h4>'),
  ('conditional', '<h4>Health context</h4>', '<h4>Health context<span class="h-icons">' + ic('ic','hpctx') + '</span></h4>'),
  ('conditional', '<h4>Counting the table</h4>', '<h4>Counting the table<span class="h-icons">' + ic('ic','charges') + '</span></h4>'),
  ('conditional', '<h4>Named condition</h4>', '<h4>Named condition<span class="h-icons">' + ic('ic','charctx') + '</span></h4>'),
 ],
}

CHAINS = {
 'ru': {
  'attacker': ('Атакующий', [('character','персонаж'),('stance','стойка'),('aura','аура'),('poison','яд'),('effect','эффект'),('weapon','оружие'),('modifier','модификатор')]),
  'defender': ('Защищающийся', [('character','персонаж'),('stance','стойка'),('aura','аура'),('poison','яд'),('effect','эффект'),('trap','ловушка'),('defense','защита')]),
 },
 'en': {
  'attacker': ('Attacker', [('character','character'),('stance','stance'),('aura','aura'),('poison','poison'),('effect','effect'),('weapon','weapon'),('modifier','modifier')]),
  'defender': ('Defender', [('character','character'),('stance','stance'),('aura','aura'),('poison','poison'),('effect','effect'),('trap','trap'),('defense','defense')]),
 },
}
def chain(lang, who):
    title, steps = CHAINS[lang][who]
    parts = [f'<span class="st"><i class="ic" data-b="{k}"></i>{w}</span>' for k, w in steps]
    return f'<h4>{title}</h4><div class="chain">' + '<span class="arr">→</span>'.join(parts) + '</div>'


L = {
 'ru': dict(src='rules/content-ru.html', out='rules/rules.html', html_lang='ru',
            title='Последний самурай — правила игры',
            sub='— Последний самурай —',
            cover_title=('Последний', 'самурай'), cover_sub='Правила игры', end='Конец',
            draft='<a href="../app.html">Картотека</a> · <a href="cheatsheet.html">Памятка A5</a> · Ctrl+P — печать A5, страница на лист',
            switch='<span class="lang-switch-current">RU</span><a href="rules-en.html">EN</a>',
            comment='Правила игры, русский оригинал. ФАЙЛ СОБИРАЕТСЯ СКРИПТОМ\n     tools/build-rules-new.py из rules/content-ru.html — текст править там,\n     здесь — не править. Английская версия — rules-en.html, перевод.'),
 'en': dict(src='rules/content-en.html', out='rules/rules-en.html', html_lang='en',
            title='The Last Samurai — Game Rules',
            sub='— The Last Samurai —',
            cover_title=('The Last', 'Samurai'), cover_sub='Game Rules', end='The End',
            draft='<a href="../app.html?lang=en">Card catalogue</a> · <a href="cheatsheet-en.html">Cheat sheet A5</a> · Ctrl+P — print A5, one page per sheet',
            switch='<a href="rules.html">RU</a><span class="lang-switch-current">EN</span>',
            comment='Game rules, English translation — not the original: the Russian\n     rules.html is the source of truth. GENERATED by tools/build-rules-new.py\n     from rules/content-en.html; edit the text there, never here.'),
}

SCRIPT = '''<script>
  // Плоские значки с карт: круг цвета группы + белый силуэт, как в памятке.
  (function () {
    var M = '../media/';
    var GROUP = {
      defense: '#dca300', trap: '#43525A', weapon: '#2E2A28', stance: '#A78B6B',
      modifier: '#ED1C24', aoe: '#2E2A28', aura: '#93a32e', effect: '#2E2A28',
      intervention: '#3B8476', action: '#2E2A28', character: '#6C8CC7', role: '#5d3c75'
    };
    var SPECIAL = {
      poison:  { color: '#4F7A21', glyph: M + 'icons/poison.svg' },
      thrust:  { color: '#8B1E2D', glyph: M + 'icons/thrust.svg' },
      rolectx: { glyph: M + 'icons/rolectx.svg', raw: true },
      hpctx:   { glyph: M + 'icons/hpctx.svg',   raw: true },
      charctx: { glyph: M + 'icons/charctx.svg', raw: true },
      charges: { glyph: M + 'icons/charges.svg', raw: true },
      hp:      { png: M + 'hp.png' }
    };
    document.querySelectorAll('.ic[data-b]').forEach(function (el) {
      var key = el.getAttribute('data-b');
      var b = SPECIAL[key] || (GROUP[key] && { color: GROUP[key], glyph: M + 'types/' + key + '.svg' });
      if (!b) return;
      el.classList.add('b-' + key);
      if (b.raw || b.png) el.classList.add('raw');
      if (b.color) el.style.background = b.color;
      var e = document.createElement('img');
      e.src = b.glyph || b.png; e.alt = ''; e.draggable = false;
      el.appendChild(e);
    });
  })();
</script>'''

sec_re = re.compile(r'<section class="chapter" id="(\w+)">\s*<h2 class="chapter-title" data-mark="([^"]+)">([^<]+)</h2>(.*?)</section>', re.S)


def chapter_html(lang, cid, mark, title, body, a=0, b=None):
    """Глава или её срез body[a:b] (блоки верхнего уровня, без h2).
    Первый срез (a == 0) несёт заголовок и колонку на поле, последний
    (b is None) — иероглиф-водяной знак."""
    cfg = CH[cid]
    body = body.strip('\n')
    for c, old, new in INLINE[lang]:
        if c == cid:
            if old not in body:
                print('  ! not found', lang, cid, old[:50]); continue
            body = body.replace(old, new, 1)
    if cid == 'order':
        # вместо двух нумерованных списков — две цепочки значков
        body = re.sub(r'<div class="order-list">.*?</div>\s*<div class="order-list">.*?</div>',
                      chain(lang, 'attacker') + chain(lang, 'defender'), body, count=1, flags=re.S)
        assert 'order-list' not in body, lang
    blocks = top_level_blocks(body)
    part = blocks[a:b]
    assert part, (cid, a, b, len(blocks))
    first, last = a == 0, b is None
    fig = cfg.get('fig')
    if fig and last:
        # тушевая иллюстрация главы — ровно в правом нижнем углу: последние k блоков
        # получают отступ справа под картинку, сама она стоит абсолютно в углу этой
        # обёртки (.fig-row). Обычный блок, не flex: строки по-прежнему обтекают
        # колонку карт, и перед подзаголовком не появляется зазора
        name, w, k, *rest = fig
        right = rest[0] if rest else 0      # сдвиг влево от края колонки, мм — например, под центр колонки карт
        down = rest[1] if len(rest) > 1 else 0   # свес ниже последнего блока, мм — если под главой есть место
        part = list(part)
        i = max(len(part) - k, 0)
        row = (f'<div class="fig-row"><div class="fig-text" style="padding-right:{w + 3 + right}mm">\n' + '\n'.join(part[i:]) + '\n</div>'
               f'<img class="chapter-fig" src="media/fig/ink/{name}.webp" style="width:{w}mm;right:{right}mm;bottom:{-down}mm" alt=""></div>')
        part = part[:i] + [row]
    body = '\n'.join(part)
    bg = bg_path(cid) if a == 0 else None   # фон — только на первом срезе, чтобы не повторялся на странице
    cards, layout = part_cards(cfg, a)
    icons = cfg['icons'] if first else []
    style = f' style="--bg:url({bg})"' if bg else ''
    cls = 'chapter' + ('' if first else ' continued')
    title_html = f'\n          <h2 class="chapter-title">{title}<span class="kanji" aria-hidden="true">{mark}</span>{heading_icons(icons)}</h2>' if first else ''
    kanji_html = ''   # иероглиф теперь в строке заголовка
    side_html = ''
    if cards:
        side_html = f'''
        <aside class="chapter-side">
          {card_fan(cards, lang, layout)}
        </aside>'''
    return f'''
      <section class="{cls}" id="{cid}{"" if first else f"-{a}"}"{style}>
        <div class="chapter-body">{title_html}{side_html}
{body}{kanji_html}
        </div>
      </section>'''


def cover_html(t):
    # Шапка первой страницы текста: тот же тушевой рисунок, что на титуле, в 40 мм
    return '''
      <header class="cover">
        <img class="cover-art" src="media/cover.webp" alt="">
      </header>'''

def title_html(t):
    # Титульный лист: тушевой рисунок дуэли (rules/media/cover.webp, /img) во всю ширину,
    # название построчно (cover_title — строки), подзаголовок ниже, между точками
    return f'''
      <div class="title-page">
        <img class="title-art" src="media/cover.webp" alt="">
        <h1 class="title-name">{''.join(f'<span>{w}</span>' for w in t['cover_title'])}</h1>
        <p class="title-sub"><span>{t['cover_sub']}</span></p>
      </div>'''

def end_html(t):
    # Завершающий лист: иероглиф и слово «Конец» между штрихами
    return f'''
      <div class="end-page">
        <p class="end-kanji" aria-hidden="true">終</p>
        <p class="title-sub"><span>{t['end']}</span></p>
      </div>'''


def build(lang):
    t = L[lang]
    src = open(t['src'], encoding='utf-8').read()
    chapters = {cid: (mark, title, body) for cid, mark, title, body in sec_re.findall(src)}
    assert len(chapters) == 18, (lang, len(chapters))
    # глава «Стол во время партии» собирается из table_fig: h4 там становится заголовком главы
    tsec = table_fig.section(lang)
    ttitle = re.search(r'<h4>([^<]*)</h4>', tsec).group(1)
    chapters['table'] = ('卓', ttitle, re.sub(r'<h4>[^<]*</h4>', '', tsec, count=1))
    used = [(c[0] if isinstance(c, tuple) else c) for pg in PAGES for c in pg if isinstance(c, tuple) or not c.startswith('__')]
    missing = [c for c in chapters if c not in used]
    assert not missing, ('главы без страницы', missing)

    # Титул не считается: нумерация с первой страницы текста, она левая.
    # «Конец» стоит один, как титул. Брошюра — сложенные пополам A4, четыре
    # страницы на лист: общее число страниц добивается пустыми (без фолио)
    # перед «Концом» до кратного четырём.
    pages = list(PAGES)
    assert pages[0] == ['__title__'] and pages[-1] == ['__end__']
    for _ in range(-len(pages) % 4):
        pages.insert(len(pages) - 1, ['__blank__'])
    assert len(pages) % 4 == 0
    sheets = []
    for n, page in enumerate(pages, start=0):
        # n=0 — титул, один; дальше нечётные — левые, чётные — правые;
        # последний — «Конец», один, как титул
        side = 'right' if n == 0 or n == len(pages) - 1 else ('left' if n % 2 else 'right')
        blocks, kind = [], 'page'
        for item in page:
            if item == '__title__':
                blocks.append(title_html(t)); kind = 'title'
            elif item == '__cover__':
                blocks.append(cover_html(t))
            elif item == '__end__':
                blocks.append(end_html(t)); kind = 'end'
            elif item == '__blank__':
                kind = 'blank'
            elif isinstance(item, tuple):
                cid, a, b = item
                blocks.append(chapter_html(lang, cid, *chapters[cid], a=a, b=b))
            else:
                blocks.append(chapter_html(lang, item, *chapters[item]))
        folio = f'\n      <span class="folio">{n}</span>' if kind == 'page' else ''
        sheets.append(f'''
    <section class="sheet {side} {kind}" id="p{n}" data-page="{n}">
      <div class="content">{''.join(blocks)}
      </div>{folio}
    </section>''')
    # развороты: титул один, затем пары (1–2, 3–4…), «Конец» один
    groups = [[0]] + [[i, i + 1] for i in range(1, len(sheets) - 1, 2)] + [[len(sheets) - 1]]
    assert sum(len(g) for g in groups) == len(sheets)
    spreads = []
    for g in groups:
        cls = 'spread single' if len(g) == 1 else 'spread'
        spreads.append(f'\n  <div class="{cls}">' + ''.join(sheets[i] for i in g) + '\n  </div>')

    html = f'''<!DOCTYPE html>
<html lang="{t['html_lang']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t['title']}</title>
<link rel="icon" type="image/svg+xml" href="../media/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Sans+Narrow:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="rules.css">
<link rel="stylesheet" href="rules-print.css" media="print">
<script src="typograph.js" defer></script>
</head>
<body>
<!-- {t['comment']} -->
<div class="toolbar screen-only">
  <span class="toolbar-title">{t['title']}</span>
  <span class="draft-note">{t['draft']}</span>
  <span class="lang-switch">{t['switch']}</span>
</div>

<div class="book">{''.join(spreads)}
</div>

{SCRIPT}
</body>
</html>
'''
    open(t['out'], 'w', encoding='utf-8', newline='\n').write(html)
    print(lang, 'written', t['out'], len(sheets), 'pages')


for lang in ('ru', 'en'):
    build(lang)
