# -*- coding: utf-8 -*-
"""Запуск: py -3 tools/build-aspect-matrix.py [--list]

Собирает матрицу аспектов: mechanics/aspect_matrix_card_ideas.md (текст для
обсуждения и git-diff) и mechanics/aspect_matrix_card_ideas.html (тепловая
карта покрытия и превью родни через ../app.html?embed=<ID>). Обе страницы —
из одних данных, руками их не править.

Источники:
- mechanics/aspects.md — словарь: разделы, ключи, описания. Строка словаря —
  ``- `ключ` — описание``; разделы «вне матрицы» и «Убрано» пропускаются.
- js/cards.js — колода (через node, как build-copyright-deposit.py). Роли и
  корзина не в счёт; черновики в счёт не идут, но называются в подсказке.
- mechanics/aspect_matrix_card_ideas.toml — идеи новых карт на пустых парах
  и тексты вступления/заключения.

Как аспект узнаётся на карте — словарь DETECT ниже. Детектор грубый
намеренно: задача матрицы — показать пустые пересечения, а не посчитать
покрытие до карты. Карта, которую регулярка не ловит, дописывается в ids.

--list печатает, какие карты нашёл каждый детектор, — для настройки."""
import os, sys, re, json, html, subprocess, tomllib, itertools
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ASPECTS_MD = 'mechanics/aspects.md'
IDEAS_TOML = 'mechanics/aspect_matrix_card_ideas.toml'
OUT_MD = 'mechanics/aspect_matrix_card_ideas.md'
OUT_HTML = 'mechanics/aspect_matrix_card_ideas.html'

# Карта несёт аспект, если сработало хоть одно: re — регулярка по русскому desc
# (регистр не важен), group — группа карты, type — один из types, icon — значок
# в icons/iconsOr, alt — у карты есть вторая ветка значков (iconsOr), ids — явный
# список; not_re — если совпало, аспекта нет. Хвост «TODO: …» в desc не читается.
DETECT = {
    # Состояние игрока
    'full hp':      dict(re=r'полном здоровье'),
    'death door':   dict(re=r'на пороге|порог смерти'),
    'missing hp':   dict(re=r'недостающ'),
    'heal':         dict(re=r'восстан\w*[^.]{0,40}(жизн|жетон|здоров|ХП)|\+\d ХП|лечени|исцел|лечит|вылечить'
                           r'|получает жетон жизни|верн\w* \d жетон'),
    'hp swap':      dict(re=r'количеством жетонов|количество жетонов жизни выбранного|перераспредел\w* жетон'
                           r'|забираете у игрока жетон|жизни меняются местами|разделить в любой пропорции'),
    'poisoned':     dict(icon=['poison'], re=r'отрав|яд\b|яда|ядом'),
    'dead':         dict(re=r'умерш|умира|мёртв(?!ым)|при смерти'),
    'restore':      dict(re=r'восстановлени\w* после смерти|до семи'),
    'kill':         dict(re=r'убив|убийств|убивш|добива|добьёт'),
    'deathrattle':  dict(re=r'после (вашей )?смерти'),
    'feign death':  dict(re=r'считаетесь убитым|притворяется мёртвым'),
    'complexity':   dict(re=r'сложност'),
    'defenseless':  dict(re=r'нельзя защититься|невозможно защититься|не может защищаться|беззащит'
                           r'|лишается возможности играть карты защиты|игнорирует[^.]{0,20}защиту'),
    'self-harm':    dict(re=r'вы теряете (один )?жетон|вы умираете|за каждый сброшенный жетон|\{носитель\}[^.]{0,20}отравлени'
                           r'|получает на 1 рану больше|может отравить и себя|ценой одной раны'
                           r'|вы и согласный[^.]{0,30}сбрасываете все'),
    # Карты на столе
    'stance':       dict(group=['stance'], re=r'стойк'),
    'trap':         dict(group=['trap'], type=['trap'], icon=['trap'], re=r'ловушк'),
    'enlightened':  dict(re=r'просве[тщ]|ловушки на столе открываются'),
    'effect':       dict(group=['effect'], type=['effect'], icon=['effect8'], re=r'эффект'),
    'aura':         dict(group=['aura'], re=r'\bаур'),
    'aura stack':   dict(re=r'под ауру'),
    'play as':      dict(re=r'можно (использовать|сыграть) как|как карту защиты|как защиту|переходит (эффектом|на него эффектом)'
                           r'|получает эту карту как эффект|сыграть карту оружия как вмешательство|может защитить от атаки в виде'
                           r'|защищаться от прямых атак оружием|в любой момент, даже в чужой ход|играть эти карты как свои'
                           r'|можно выложить перед собой в любой момент|как вмешательство',
                         ids=[56, 1032]),
    'strip':        dict(re=r'теря\w* (свою )?стойк|сбрасывают свою ловушку|обезвред|уничтожа|скидывает указанный'
                           r'|сним\w*[^.]{0,25}эффект|снять[^.]{0,25}эффект|стойку отнять|возвращают свои стойки'),
    # Рука и движение карт
    'hand':         dict(re=r'с руки|из руки|в руке|своей руки|руку|рука '),
    'revealed':     dict(re=r'в открытую|показыва|лежит перед ним в открытую', not_re=r'под аур'),
    'draw':         dict(re=r'из колоды|берут? по \d|возьмите[^.]{0,20}карт|берите[^.]{0,20}карт|берёт(е)?[^.]{0,20}карт|взять \d'),
    'draw phase':   dict(re=r'фаз\w* набора|в наборе'),
    'discard cost': dict(re=r'сбросив|сбросьте|скиньте|за каждую (дополнительно )?сброшенную|скинуть лишь|сбросить (одну |1 |2 |две )?карт'
                           r'|штрафуются сбросом|должен сбросить|должны сбросить|сбросить 2 карты|сбрасываете все свои карты'
                           r'|скидывая|сбросить любое число оружия|подложить под ауру|сбросить любое'),
    'forced discard': dict(re=r'скидывает случайную|сбрасывает случайную|скидывают (карту|свою)|скидывают карту защиты'
                             r'|сбрасывая каждый раз'),
    'steal':        dict(re=r'забира|заберите|забрать|украд|взять любую из них', not_re=r'^$'),
    'give':         dict(re=r'переда|отда[ёе]т|отдают|отдать|для себя или союзника|отдаёте|отдайте', ids=[108]),
    'swap':         dict(re=r'меняетесь|поменять|обмен|сдвигаются|меняются местами|обменяться', not_re=r'Обмен, выравнивание'),
    'return':       dict(re=r'возвращается (вам )?в руку|возвращают свои стойки в руку|свою возвращает в руку|обратно в руку|в руку по шнуру'),
    # Атака
    'weapon':       dict(group=['weapon'], type=['weapon'], re=r'оружи'),
    'ranged':       dict(icon=['ranged'], re=r'метательн'),
    'polearm':      dict(re=r'древков'),
    'favorite':     dict(re=r'любимое оружие'),
    'unarmed':      dict(re=r'рукопашн'),
    'attempt':      dict(re=r'попытк|тратит атаку|не тратит|на одну прямую атаку меньше|первой попыткой|второй попыткой'),
    'modifier':     dict(group=['modifier'], type=['modifier'], icon=['modifier'], re=r'модификатор'),
    'bonus dmg':    dict(re=r'на (одну|1|2|две) ран\w* больше|\+\d к силе|\+\d ран|сила атаки увеличивается|наносят дополнительно'
                           r'|дополнительно \d ран|ещё на одну рану|сила атаки становится равна|сила атаки равна'
                           r'|добавляется к силе|\+2 к силе|бьёт на 2|наносит им две раны|тогда ран две'),
    'thrust':       dict(icon=['thrust'], re=r'выпад'),
    'on hit':       dict(re=r'в случае успешной атаки|успешн\w* (прямую )?атак|совершив успешную|после нанесения ран'
                           r'|столько жетонов жизни, сколько нанесли'),
    'on wounded':   dict(re=r'за каждую полученную рану|в момент получения ран|ранивший вас|получая любой вид урона'
                           r'|остались в живых после атаки|за каждую атаку по вам'),
    # Защита и вмешательства
    'defense':      dict(group=['defense'], type=['defense'], icon=['defense'],
                         re=r'карт\w* защиты|как защиту|как карту защиты|защищаться|защитой|защиту'),
    'ally defense': dict(re=r'за любого игрока|в защиту другого|может защитить от атаки в виде вмешательства'
                           r'|принять прямую атаку[^.]{0,30}на себя|перенаправить прямую атаку оружия на себя'),
    'intervention': dict(group=['intervention'], type=['intervention'], icon=['intervention'],
                         re=r'вмешательств|в любой момент|в чужой ход'),
    'redirect':     dict(re=r'перенаправ|на себя \(|переложить|переместить|передвин|переходит на убивш'
                           r'|вместо неё свою ловушку|обращается обратно|передаёте игроку отравление|ауру можете выложить перед любым'),
    # Разовые действия
    'aoe':          dict(group=['aoe'], icon=['aoe']),
    'action':       dict(group=['action']),
    # Мишени
    'ally':         dict(re=r'союзник|соратник|вашей команды|своей команды|\{союзник'),
    'enemy':        dict(re=r'враг'),
    'all':          dict(re=r'все (остальные )?(активные|живые)|остальные (активные|живые)|каждый (активный|живой)|все враги'
                           r'|все игроки|каждый союзник|каждый враг|все \{?союзник|все ловушки|вашей команде|по вашей команде'),
    'consent':      dict(re=r'соглас'),
    'neighbor':     dict(re=r'сосед|по часовой'),
    # Условия и масштаб
    'faction':      dict(icon=['rolectx'], re=r'\{(самура|ниндз)'),
    'char-name':    dict(icon=['charctx']),
    'charges':      dict(icon=['charges'], re=r'за каждого|за каждое|за каждую|за каждый|за каждые'),
    'two-mode':     dict(re=r'-ИЛИ-|\{ИЛИ\}|Либо сыграйте|Либо скиньте', alt=True),
    'once-per-turn': dict(re=r'раз в (свой )?ход'),
    'one step':     dict(re=r'до следующего|до конца (текущего |того )?хода|весь раунд|в начале своего хода|следующ'),
    'vp':           dict(re=r'победн|очко|жетонов победы'),
}

GROUP_RU = {
    'weapon': 'оружие', 'trap': 'ловушка', 'defense': 'защита', 'stance': 'стойка',
    'modifier': 'модификатор', 'aoe': 'групповое', 'effect': 'эффект', 'action': 'действие',
    'intervention': 'вмешательство', 'aura': 'аура', 'character': 'персонаж', 'role': 'роль',
}
GROUP_COLOR = {  # те же, что GROUP_TITLE_COLOR в js/app.js
    'weapon': '#231F20', 'trap': '#43525A', 'defense': '#dca300', 'stance': '#A78B6B',
    'modifier': '#ED1C24', 'aoe': '#2E2A28', 'effect': '#5B4A7E', 'action': '#231F20',
    'intervention': '#3B8476', 'aura': '#8a5a2b', 'character': '#6C8CC7', 'role': '#5d3c75',
}


# ── данные ───────────────────────────────────────────────────────────────────

def load_cards():
    js = ("const fs=require('fs');const src=fs.readFileSync('js/cards.js','utf8');"
          "process.stdout.write(JSON.stringify(new Function(src+';return CARDS;')()));")
    out = subprocess.run(['node', '-e', js], capture_output=True, text=True, encoding='utf-8', check=True).stdout
    return json.loads(out)


def load_aspects():
    """aspects.md → [(раздел, ключ, описание)] в порядке файла."""
    rows, section, skip = [], None, False
    for line in open(ASPECTS_MD, encoding='utf-8'):
        if line.startswith('## '):
            section = line[3:].strip()
            skip = 'вне матрицы' in section or section.startswith('Убрано')
            continue
        m = re.match(r'- `([^`]+)` — (.+)', line.rstrip())
        if m and section and not skip:
            rows.append((section, m.group(1), m.group(2)))
    return rows


def card_has(card, rule):
    desc = (card.get('desc') or '').split('TODO')[0]
    if rule.get('not_re') and re.search(rule['not_re'], desc, re.I):
        return False
    if card.get('group') in rule.get('group', ()):
        return True
    if set(card.get('types') or ()) & set(rule.get('type', ())):
        return True
    if set((card.get('icons') or []) + (card.get('iconsOr') or [])) & set(rule.get('icon', ())):
        return True
    if card['id'] in rule.get('ids', ()) or (rule.get('alt') and card.get('iconsOr')):
        return True
    return bool(rule.get('re') and re.search(rule['re'], desc, re.I))


def status(card):
    tags = card.get('tags') or []
    return 'trash' if 'trash' in tags else 'draft' if 'draft' in tags else 'active'


def build_model():
    aspects = load_aspects()
    keys = [k for _, k, _ in aspects]
    missing = [k for k in keys if k not in DETECT]
    extra = [k for k in DETECT if k not in keys]
    if missing or extra:
        sys.exit(f'Словарь и детекторы разошлись. Нет детектора: {missing}. Нет в aspects.md: {extra}')
    cards = [c for c in load_cards() if c.get('group') != 'role' and status(c) != 'trash']
    has = {k: [c for c in cards if card_has(c, DETECT[k])] for k in keys}
    pairs = {}
    for a, b in itertools.combinations(keys, 2):
        ids_b = {c['id'] for c in has[b]}
        both = [c for c in has[a] if c['id'] in ids_b]
        pairs[(a, b)] = both
    ideas_doc = tomllib.load(open(IDEAS_TOML, 'rb')) if os.path.exists(IDEAS_TOML) else {}
    ideas = ideas_doc.get('idea', [])
    by_id = {c['id']: c for c in load_cards()}
    for i in ideas:
        for k in i['pair']:
            if k not in keys:
                sys.exit(f'{i["id"]}: аспекта «{k}» нет в словаре')
        for cid in i.get('kin', []):
            if cid not in by_id:
                sys.exit(f'{i["id"]}: карты #{cid} нет в js/cards.js')
        i['pair'] = sorted(i['pair'], key=keys.index)
    return dict(aspects=aspects, keys=keys, cards=cards, has=has, pairs=pairs,
                doc=ideas_doc.get('doc', {}), ideas=ideas, by_id=by_id)


def active(cs):
    return [c for c in cs if status(c) == 'active']


# ── разметка ─────────────────────────────────────────────────────────────────

def esc(s):
    return html.escape(str(s), quote=True)


def inline_html(s):
    """Микроформаты карты и markdown-строки → html: {условие}, [NL], -ИЛИ-, **жирный**, `код`."""
    s = esc(s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'\{([^}]+)\}', r'<em class="cond">\1</em>', s)
    s = s.replace('[NL]', '<br>')
    s = re.sub(r'\s*-ИЛИ-\s*', ' <span class="or">или</span> ', s)
    return s


def md_to_html(text):
    """Абзацы, списки «- » и заголовки «## » / «### » — ровно то, что пишется в [doc]."""
    out = []
    for block in re.split(r'\n\s*\n', (text or '').strip()):
        lines = block.strip().split('\n')
        m = re.match(r'(#{2,3}) (.+)', lines[0])
        if m:
            h = len(m.group(1))
            out.append(f'<h{h}>{inline_html(m.group(2))}</h{h}>')
            lines = lines[1:]
            if not lines:
                continue
        if all(l.startswith('- ') or l.startswith('  ') for l in lines):
            items, cur = [], None
            for l in lines:
                if l.startswith('- '):
                    cur = [l[2:]]
                    items.append(cur)
                else:
                    cur.append(l.strip())
            out.append('<ul>' + ''.join(f'<li>{inline_html(" ".join(it))}</li>' for it in items) + '</ul>')
        else:
            out.append(f'<p>{inline_html(" ".join(l.strip() for l in lines))}</p>')
    return '\n'.join(out)


def card_ref(c):
    return f'#{c["id"]} {c["title"]}'


# ── markdown ─────────────────────────────────────────────────────────────────

def build_md(m):
    keys, pairs, has = m['keys'], m['pairs'], m['has']
    n_pairs = len(pairs)
    covered = sum(1 for v in pairs.values() if active(v))
    doc = m['doc']
    L = [f'# {doc.get("title", "Матрица аспектов")}', '']
    L += [doc.get('subtitle', ''), ''] if doc.get('subtitle') else []
    L += ['> Собрано `py -3 tools/build-aspect-matrix.py` из `aspects.md`, `js/cards.js` и',
          '> `aspect_matrix_card_ideas.toml`. Руками не править — правится `.toml`, потом пересборка.',
          '> Визуальная версия с тепловой картой покрытия и превью родни — `aspect_matrix_card_ideas.html`.', '']
    if doc.get('intro'):
        L += [doc['intro'].strip(), '']
    L += ['## Покрытие', '',
          f'Аспектов в матрице — {len(keys)}, пар — {n_pairs}. Активных карт в колоде без ролей — '
          f'{len(active(m["cards"]))}. Пар, которые несёт хотя бы одна активная карта, — {covered}; '
          f'пустых — {n_pairs - covered}.', '',
          '| Раздел | Аспект | Карт | Пустых пар | Примеры |', '|---|---|---|---|---|']
    for section, k, _ in m['aspects']:
        cs = active(has[k])
        empty = sum(1 for (a, b), v in pairs.items() if k in (a, b) and not active(v))
        ex = ', '.join(card_ref(c) for c in cs[:3]) + (' …' if len(cs) > 3 else '')
        L.append(f'| {section} | `{k}` | {len(cs) or "**0**"} | {empty} | {ex or "—"} |')
    L += ['']
    ideas = m['ideas']
    L += [f'## Идеи — {len(ideas)} новых карт', '',
          '| № | Пересечение | Карта | Эффект | Флавор | Родня в колоде |', '|---|---|---|---|---|---|']
    for i in ideas:
        a, b = i['pair']
        cov = active(pairs[(a, b)])
        pair = f'`{a}` × `{b}`' + (f' · сейчас {len(cov)}' if cov else ' · пусто')
        name = f'**{i["name"]}**' + (f' {i["jp"]}' if i.get('jp') else '')
        card = f'{name}<br>{GROUP_RU.get(i["group"], i["group"])} · ×{i["qty"]} · {i["tilt"]}'
        kin = ', '.join(card_ref(m['by_id'][cid]) for cid in i.get('kin', []))
        note = (kin + ' — ' if kin else '') + i.get('kin_note', '')
        cells = [i['id'], pair, card, i['text'], i['flavor'], note]
        L.append('| ' + ' | '.join(str(x).replace('|', '\\|').replace('\n', ' ') for x in cells) + ' |')
    L += ['']
    checks = [i for i in ideas if i.get('check')]
    if checks:
        L += ['## Проверка по мета-правилам', '']
        for i in checks:
            L.append(f'- **{i["id"]} {i["name"]}.** {i["check"].strip()}')
        L += ['']
    if doc.get('outro'):
        L += [doc['outro'].strip(), '']
    return '\n'.join(L)


# ── html ─────────────────────────────────────────────────────────────────────

CSS = """
    :root { --line: #d8d3c8; --paper: #fffdf9; --soft: #f5f3ee; --ink: #1a1a1a; --gold: #9b8755; }
    body { font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
           max-width: 1560px; margin: 24px auto; padding: 0 20px 60px; color: var(--ink);
           line-height: 1.5; background: var(--paper); }
    h1 { font-size: 27px; margin-bottom: 4px; }
    h1 .jp { font-weight: 400; color: #8a7a55; margin-left: 10px; font-size: 20px; }
    h2 { font-size: 20px; margin-top: 34px; border-bottom: 2px solid var(--line); padding-bottom: 6px; }
    h3 { font-size: 16px; margin-top: 24px; }
    p, li { font-size: 14px; }
    .sub { color: #666; font-size: 14px; margin-top: 0; }
    .legend { background: var(--soft); border-left: 3px solid var(--gold); padding: 12px 16px; margin: 16px 0; font-size: 13px; }
    .legend p { font-size: 13px; } .legend p:first-child { margin-top: 0; } .legend p:last-child { margin-bottom: 0; }
    code { background: #ece8de; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
    .cond { font-style: normal; background: #ece8de; border-radius: 3px; padding: 0 4px; }
    .or { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: #8a7a55; }

    /* тепловая карта */
    .hm-wrap { overflow-x: auto; margin: 16px 0; }
    table.hm { border-collapse: collapse; font-size: 11px; }
    table.hm th.col { height: 118px; width: 15px; padding: 0 0 4px; vertical-align: bottom; font-weight: 400; }
    table.hm th.col span { writing-mode: vertical-rl; transform: rotate(180deg); white-space: nowrap; color: #4a4330; }
    table.hm th.row { text-align: right; padding: 0 6px 0 0; font-weight: 400; white-space: nowrap; color: #4a4330; }
    table.hm th .n { color: #a39777; }
    table.hm th.zero, table.hm th.zero span { color: #b5442e; font-weight: 600; }
    table.hm td { width: 15px; height: 15px; padding: 0; border: 1px solid #ece8de; text-align: center;
                  font-size: 9px; line-height: 13px; color: #fff; }
    table.hm td.diag { background: #43525a; border-color: #43525a; }
    table.hm td.none { border: 0; }
    table.hm td.c0 { background: #fff; }
    table.hm td.cd { background: repeating-linear-gradient(45deg, #fff, #fff 2px, #e9e2cf 2px, #e9e2cf 4px); }
    table.hm td.c1 { background: #efe3c2; } table.hm td.c2 { background: #dcc48a; }
    table.hm td.c3 { background: #b9974c; } table.hm td.c4 { background: #7f6427; }
    table.hm td.idea { background: #b5442e !important; cursor: pointer; font-weight: 700; }
    table.hm td.idea a { color: #fff; text-decoration: none; display: block; }
    table.hm tr.sec-start th.row, table.hm tr.sec-start td { border-top: 2px solid #9b8755; }
    table.hm td.sec-start, table.hm th.col.sec-start { border-left: 2px solid #9b8755; }
    table.hm td:hover { outline: 2px solid #1a1a1a; }
    .scale { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: #555; margin: 6px 0 0; }
    .scale i { display: inline-block; width: 13px; height: 13px; vertical-align: -2px; margin-right: 4px; border: 1px solid #ddd6c6; }

    /* покрытие аспектов */
    table.cov { border-collapse: collapse; width: 100%; font-size: 13px; }
    table.cov th, table.cov td { border: 1px solid var(--line); padding: 5px 9px; vertical-align: top; text-align: left; }
    table.cov th { background: var(--soft); font-weight: 600; }
    table.cov td.num { text-align: right; width: 56px; font-variant-numeric: tabular-nums; }
    table.cov td.zero { color: #b5442e; font-weight: 700; }
    table.cov td.sec { color: #8a7a55; width: 150px; }
    table.cov td.ex { color: #555; }

    /* идеи */
    table.ideas { border-collapse: collapse; width: 100%; margin: 20px 0 8px; table-layout: fixed; }
    col.col-num { width: 50px; } col.col-card { width: 296px; } col.col-flavor { width: 250px; } col.col-kin { width: 300px; }
    table.ideas th, table.ideas td { border: 1px solid var(--line); padding: 10px 14px; vertical-align: top; font-size: 14px; }
    table.ideas th { background: var(--soft); text-align: left; font-weight: 600; }
    td.num { text-align: center; color: #8a7a55; font-weight: 600; font-size: 13px; padding: 10px 4px; }
    td.card-cell { padding: 6px; background: #fafafa; text-align: center; }
    iframe.card-frame { width: 272px; height: 434px; border: 0; display: block; margin: 0 auto; }
    .card-name { display: block; margin-top: 2px; font-size: 11px; color: #555; }
    .card-name em { color: #8a7a55; font-style: normal; }
    .more-kin { font-size: 11px; color: #8a7a55; margin-top: 4px; }
    td.idea { background: #fcfbf7; }
    .idea-name { font-size: 17px; font-weight: 700; }
    .idea-name .jp { font-weight: 400; color: #8a7a55; margin-left: 6px; }
    .idea-meta { margin: 4px 0 10px; display: flex; gap: 6px; flex-wrap: wrap; }
    .tag { display: inline-block; color: #fff; border-radius: 10px; padding: 1px 9px; font-size: 11px; }
    .tag.q { background: #fff; color: #4a4330; border: 1px solid #ddd6c6; }
    .tag.t-samurai { background: #b5442e; } .tag.t-ninja { background: #2F3566; } .tag.t-neutral { background: #8a8374; }
    .pairtag { display: inline-block; font-size: 12px; background: #f0ece2; border: 1px solid #ddd6c6; border-radius: 12px; padding: 1px 9px; color: #4a4330; }
    .pairtag.covered { background: #fbf1ee; border-color: #e4c2b8; }
    .idea-text { background: #fef3c9; border: 1px solid #efd98e; border-radius: 6px; padding: 8px 11px; }
    .idea-check { margin-top: 10px; font-size: 13px; color: #555; }
    td.flavor { color: #5a5344; font-style: italic; background: #f9f8f4; }
    td.kin { font-size: 13px; color: #444; }
"""

HM_JS = """
    document.querySelectorAll('table.hm td.idea').forEach(function (td) {
      td.addEventListener('click', function () {
        var id = td.getAttribute('data-idea');
        var row = document.getElementById(id);
        if (row) { row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                   row.style.outline = '3px solid #b5442e';
                   setTimeout(function () { row.style.outline = ''; }, 1600); }
      });
    });
"""


def level(n):
    return 'c0' if n == 0 else 'c1' if n == 1 else 'c2' if n <= 3 else 'c3' if n <= 6 else 'c4'


def build_html(m):
    keys, pairs, has, doc = m['keys'], m['pairs'], m['has'], m['doc']
    sec_of = {k: s for s, k, _ in m['aspects']}
    sec_start = {k for i, k in enumerate(keys) if i == 0 or sec_of[keys[i - 1]] != sec_of[k]}
    idea_at = {}
    for i in m['ideas']:
        idea_at.setdefault(tuple(i['pair']), []).append(i['id'])
    n_pairs = len(pairs)
    covered = sum(1 for v in pairs.values() if active(v))

    H = ['<!DOCTYPE html>', '<html lang="ru">', '<head>', '  <meta charset="UTF-8">',
         f'  <title>{esc(doc.get("title", "Матрица аспектов"))}</title>', f'  <style>{CSS}  </style>', '</head>', '<body>', '']
    jp = f'<span class="jp">{esc(doc["jp"])}</span>' if doc.get('jp') else ''
    H.append(f'  <h1>{esc(doc.get("title", "Матрица аспектов"))}{jp}</h1>')
    if doc.get('subtitle'):
        H.append(f'  <p class="sub">{inline_html(doc["subtitle"])} Текстовая версия — <code>aspect_matrix_card_ideas.md</code>.</p>')
    H.append('  <div class="legend"><p>Собрано <code>py -3 tools/build-aspect-matrix.py</code> из <code>aspects.md</code>, '
             '<code>js/cards.js</code> и <code>aspect_matrix_card_ideas.toml</code>. Руками не править.</p></div>')
    if doc.get('intro'):
        H.append(md_to_html(doc['intro']))

    # тепловая карта: нижний треугольник, строки и столбцы — аспекты в порядке словаря
    H += ['  <h2>Покрытие пар</h2>',
          f'  <p>Аспектов — {len(keys)}, пар — {n_pairs}; хотя бы одной активной картой покрыто {covered}, '
          f'пустых {n_pairs - covered}. Клетка — сколько активных карт несут оба аспекта; наведите, чтобы увидеть карты. '
          'Красная клетка — идея из этого файла, щелчок ведёт к ней (цифра в клетке — если идей на паре несколько). Число у названия — сколько карт несут аспект; '
          'красным — аспекты, которых в колоде нет совсем.</p>',
          '  <div class="scale"><span><i style="background:#fff"></i>0</span>'
          '<span><i style="background:repeating-linear-gradient(45deg,#fff,#fff 2px,#e9e2cf 2px,#e9e2cf 4px)"></i>0, но есть черновик</span>'
          '<span><i style="background:#efe3c2"></i>1</span><span><i style="background:#dcc48a"></i>2–3</span>'
          '<span><i style="background:#b9974c"></i>4–6</span><span><i style="background:#7f6427"></i>7+</span>'
          '<span><i style="background:#b5442e"></i>идея</span></div>',
          '  <div class="hm-wrap"><table class="hm">', '    <tr><th></th>']
    for k in keys:
        n = len(active(has[k]))
        cls = 'col' + (' sec-start' if k in sec_start else '') + (' zero' if n == 0 else '')
        H.append(f'      <th class="{cls}" title="{esc(sec_of[k])}"><span>{esc(k)} <span class="n">{n}</span></span></th>')
    H.append('    </tr>')
    for r, a in enumerate(keys):
        n = len(active(has[a]))
        rcls = ' class="sec-start"' if a in sec_start else ''
        zcls = ' zero' if n == 0 else ''
        row = [f'    <tr{rcls}><th class="row{zcls}" title="{esc(sec_of[a])}">{esc(a)} <span class="n">{n}</span></th>']
        for c, b in enumerate(keys):
            sc = ' sec-start' if b in sec_start else ''
            if c > r:
                row.append(f'<td class="none{sc}"></td>')
                continue
            if c == r:
                row.append(f'<td class="diag{sc}"></td>')
                continue
            key = (b, a)  # b раньше a в словаре
            cs = pairs[key]
            act, drafts = active(cs), [x for x in cs if status(x) == 'draft']
            tip = f'{b} × {a}: {len(act)}'
            if act:
                tip += ' — ' + ', '.join(card_ref(x) for x in act[:12]) + (' …' if len(act) > 12 else '')
            if drafts:
                tip += ' · черновики: ' + ', '.join(card_ref(x) for x in drafts)
            ids = idea_at.get(key)
            if ids:
                tip += ' · идея ' + ', '.join(ids)
                row.append(f'<td class="idea{sc}" data-idea="{ids[0]}" title="{esc(tip)}">'
                           f'<a href="#{ids[0]}">{len(ids) if len(ids) > 1 else ""}</a></td>')
            else:
                cls = 'cd' if not act and drafts else level(len(act))
                row.append(f'<td class="{cls}{sc}" title="{esc(tip)}"></td>')
        row.append('</tr>')
        H.append(''.join(row))
    H += ['  </table></div>']

    # идеи
    ideas = m['ideas']
    H += [f'  <h2>Идеи — {len(ideas)} новых карт</h2>',
          '  <table class="ideas">',
          '    <colgroup><col class="col-num"><col class="col-card"><col class="col-idea"><col class="col-flavor"><col class="col-kin"></colgroup>',
          '    <thead><tr><th>№</th><th>Ближайшая родня</th><th>Новая карта</th><th>Флавор</th><th>Отличие от родни</th></tr></thead>',
          '    <tbody>']
    tilt_cls = {'самураи': 't-samurai', 'ниндзя': 't-ninja'}
    for i in ideas:
        a, b = i['pair']
        cov = active(pairs[(a, b)])
        kin = [m['by_id'][cid] for cid in i.get('kin', [])]
        if kin:
            k0 = kin[0]
            cell = (f'<iframe class="card-frame" loading="lazy" src="../app.html?embed={k0["id"]}" title="{esc(k0["title"])}"></iframe>'
                    f'<span class="card-name">{esc(card_ref(k0))} <em>{esc(GROUP_RU.get(k0["group"], ""))}</em></span>')
            if len(kin) > 1:
                cell += '<div class="more-kin">и ' + ', '.join(esc(card_ref(x)) for x in kin[1:]) + '</div>'
        else:
            cell = '<span class="card-name">родни в колоде нет</span>'
        pair_cls = 'pairtag covered' if cov else 'pairtag'
        pair_txt = f'{a} × {b} · ' + (f'сейчас {len(cov)}' if cov else 'пусто')
        jp = f'<span class="jp">{esc(i["jp"])}</span>' if i.get('jp') else ''
        gcol = GROUP_COLOR.get(i['group'], '#555')
        check = f'<div class="idea-check">{inline_html(i["check"].strip())}</div>' if i.get('check') else ''
        H += ['      <tr id="' + esc(i['id']) + '">',
              f'        <td class="num">{esc(i["id"])}</td>',
              f'        <td class="card-cell">{cell}</td>',
              f'        <td class="idea"><div class="idea-name">{esc(i["name"])}{jp}</div>'
              f'<div class="idea-meta"><span class="tag" style="background:{gcol}">{esc(GROUP_RU.get(i["group"], i["group"]))}</span>'
              f'<span class="tag q">×{esc(i["qty"])}</span><span class="tag {tilt_cls.get(i["tilt"], "t-neutral")}">{esc(i["tilt"])}</span>'
              f'<span class="{pair_cls}">{esc(pair_txt)}</span></div>'
              f'<div class="idea-text">{inline_html(i["text"])}</div>{check}</td>',
              f'        <td class="flavor">{inline_html(i["flavor"])}</td>',
              f'        <td class="kin">{inline_html(i.get("kin_note", ""))}</td>',
              '      </tr>']
    H += ['    </tbody>', '  </table>']

    # покрытие аспектов
    H += ['  <h2>Аспекты в колоде</h2>',
          '  <table class="cov"><thead><tr><th>Раздел</th><th>Аспект</th><th>Описание</th><th>Карт</th><th>Пустых пар</th><th>Примеры</th></tr></thead><tbody>']
    for section, k, descr in m['aspects']:
        cs = active(has[k])
        empty = sum(1 for (x, y), v in pairs.items() if k in (x, y) and not active(v))
        ex = ', '.join(card_ref(c) for c in cs[:5]) + (' …' if len(cs) > 5 else '')
        H.append(f'    <tr><td class="sec">{esc(section)}</td><td><code>{esc(k)}</code></td><td>{inline_html(descr)}</td>'
                 f'<td class="num{" zero" if not cs else ""}">{len(cs)}</td><td class="num">{empty}</td><td class="ex">{esc(ex) or "—"}</td></tr>')
    H += ['  </tbody></table>']
    if doc.get('outro'):
        H.append(md_to_html(doc['outro']))
    H += [f'  <script>{HM_JS}  </script>', '</body>', '</html>', '']
    return '\n'.join(H)


def main():
    m = build_model()
    if '--list' in sys.argv:
        for section, k, _ in m['aspects']:
            cs = active(m['has'][k])
            print(f'{k} ({len(cs)}): ' + ', '.join(card_ref(c) for c in cs))
        return
    open(OUT_MD, 'w', encoding='utf-8', newline='\n').write(build_md(m))
    open(OUT_HTML, 'w', encoding='utf-8', newline='\n').write(build_html(m))
    n = len(m['pairs'])
    empty = sum(1 for v in m['pairs'].values() if not active(v))
    print(f'аспектов {len(m["keys"])}, пар {n}, пустых {empty}, идей {len(m["ideas"])}')
    zero = [k for k in m['keys'] if not active(m['has'][k])]
    if zero:
        print('аспекты без единой активной карты:', ', '.join(zero))
    for i in m['ideas']:
        cov = active(m['pairs'][tuple(i['pair'])])
        if cov:
            print(f'  {i["id"]} {i["name"]}: пара {" × ".join(i["pair"])} уже покрыта — '
                  + ', '.join(card_ref(c) for c in cov))
    print(f'→ {OUT_MD}\n→ {OUT_HTML}')


if __name__ == '__main__':
    main()
