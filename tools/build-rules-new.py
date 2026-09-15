# -*- coding: utf-8 -*-
"""Собирает rules/rules-new.html (RU, оригинал) и rules/rules-new-en.html (EN,
перевод) — черновик новой вёрстки правил. Текст глав берётся как есть из
rules/rules.html и rules/rules-en.html. Добавляет: боковую колонку с
иероглифом и плоскими значками, ряд карт-примеров через ../app.html?embed=ID,
бледные фоны глав из rules/media/bg/, раздел «Стол во время партии»
(table_fig.py), переключатель RU|EN."""
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
BG_KEY = {'weapons': 'attack'}          # глава → имя файла, если отличается
def bg_path(cid):
    key = BG_KEY.get(cid, cid)
    dst = f'rules/media/bg/{key}.webp'
    if not os.path.exists(dst):
        cands = sorted(glob.glob(rf'C:\Users\aveic\.claude\imagegen\out\*_bg_{key}.png'))
        if not cands:
            return None
        im = Image.open(cands[-1]).convert('RGBA')
        im.thumbnail((1100, 1100), Image.LANCZOS)
        im.save(dst, 'WEBP', quality=82, method=6)
        print('bg', key, im.size, os.path.getsize(dst) // 1024, 'KB')
    return dst.replace('rules/', '')

# ---------- конфиг глав (общий для языков) ----------
CH = {
 'about':         dict(icons=[[('ic','role')]],                         cards=[201, 200]),
 'setup':         dict(layout='stack', icons=[[('mk','hp.png'), ('mk','winpoint.png')]], cards=[202, 137]),
 'flow':          dict(icons=[],                                        cards=[]),
 'ending':        dict(icons=[],                                        cards=[]),
 'players':       dict(icons=[],                                        cards=[]),
 'cards':         dict(icons=[],                                        cards=[]),
 'weapons':       dict(layout='stack', icons=[[('ic','weapon'),('ic','modifier')],[('ic','defense')]], cards=[1, 32, 33, 31, 70, 48]),
 'traps':         dict(icons=[[('ic','trap')]],                         cards=[43, 41]),
 'stances':       dict(icons=[[('ic','stance')]],                       cards=[1166, 60]),
 'characters':    dict(icons=[[('ic','character'),('ic','hp')]],        cards=[135, 138]),
 'effects':       dict(icons=[[('ic','effect')]],                       cards=[91]),
 'poison':        dict(icons=[[('ic','poison')]],                       cards=[116, 64]),
 'interventions': dict(layout='stack', icons=[[('ic','intervention')]],                 cards=[121, 124]),
 'auras':         dict(layout='stack', icons=[[('ic','aura')]],                         cards=[1200, 1204]),
 'conditional':   dict(layout='stack', icons=[[('ic','rolectx'),('ic','hpctx')],[('ic','poison'),('ic','stance')],[('ic','charges')]], cards=[125, 1165]),
 'order':         dict(icons=[],                                        cards=[]),
}

def ic(kind, key):
    if kind == 'ic':
        return f'<i class="ic" data-b="{key}"></i>'
    return f'<img class="mk" src="../media/{key}" alt="">'

def side_icons(rows):
    if not rows:
        return ''
    return '<div class="side-icons">' + ''.join('<div class="row">' + ''.join(ic(*i) for i in r) + '</div>' for r in rows) + '</div>'

def card_fan(ids, lang, layout='fan'):
    """Карты-примеры на полях: WebP из rules/media/cards/ (tools/render-card-previews.py).
    fan — веером с поворотом (короткие главы), stack — лесенкой вниз (длинные)."""
    if not ids:
        return ''
    n = len(ids)
    items = []
    for i, cid in enumerate(ids):
        k = i - (n - 1) / 2           # -1, 0, 1 для трёх карт
        src = f'media/cards/{cid}{"-en" if lang == "en" else ""}.webp'
        items.append(f'<div class="card-embed" style="--k:{k:g};--i:{i}"><img src="{src}" alt="" loading="lazy"></div>')
    return f'<div class="side-cards {layout} n{n}">' + ''.join(items) + '</div>'

# значки в тексте — точечные вставки по фразам (глава, было, стало)
INLINE = {
 'ru': [
  ('weapons', 'наибольшая <b>сложность</b>, которую оно берёт, и сила атаки.', 'наибольшая <b>сложность</b>, которую оно берёт ' + ic('mk','icons/complexity1.svg') + ', и сила атаки ' + ic('mk','icons/dmg2.svg') + '.'),
  ('weapons', 'Метательное оружие берёт любую сложность.', 'Метательное оружие ' + ic('mk','ranged.png') + ' берёт любую сложность.'),
  ('weapons', 'либо использовать карту защиты для блокирования атаки.', 'либо использовать карту защиты ' + ic('ic','defense') + ' для блокирования атаки.'),
  ('weapons', 'Оружие также может быть усилено ядом.', 'Оружие также может быть усилено ядом ' + ic('ic','poison') + '.'),
  ('weapons', 'картой-модификатором с красной плашкой.', 'картой-модификатором ' + ic('ic','modifier') + ' с красной плашкой.'),
  ('weapons', '<h4 class="section-title">Выпад</h4>', '<h4 class="section-title">' + ic('ic','thrust') + ' Выпад</h4>'),
  ('poison', '<h4>Три недуга отравленного</h4>', '<h4>' + ic('ic','poison') + ' Три недуга отравленного</h4>'),
  ('traps', 'поставив на неё фигурку ловушки.', 'поставив на неё фигурку ловушки ' + ic('ic','trap') + '.'),
  ('interventions', 'Вмешательство — особый тип карт,', 'Вмешательство ' + ic('ic','intervention') + ' — особый тип карт,'),
  ('auras', 'Командные ауры — мощные карты,', 'Командные ауры ' + ic('ic','aura') + ' — мощные карты,'),
  ('characters', 'Цифра внутри сердца означает', 'Цифра внутри сердца ' + ic('ic','hp') + ' означает'),
  ('conditional', '<strong>Бонусы по фракции.</strong>', ic('ic','rolectx') + ' <strong>Бонусы по фракции.</strong>'),
  ('conditional', '<strong>Контекст здоровья.</strong>', ic('ic','hpctx') + ' <strong>Контекст здоровья.</strong>'),
  ('conditional', '<strong>Условия по яду.</strong>', ic('ic','poison') + ' <strong>Условия по яду.</strong>'),
  ('conditional', '<strong>Условия по стойке.</strong>', ic('ic','stance') + ' <strong>Условия по стойке.</strong>'),
 ],
 'en': [
  ('weapons', 'the highest <b>complexity</b> it can handle and its attack power.', 'the highest <b>complexity</b> it can handle ' + ic('mk','icons/complexity1.svg') + ' and its attack power ' + ic('mk','icons/dmg2.svg') + '.'),
  ('weapons', 'Thrown weapons handle any complexity.', 'Thrown weapons ' + ic('mk','ranged.png') + ' handle any complexity.'),
  ('weapons', 'or play a Defense card to block the attack.', 'or play a Defense card ' + ic('ic','defense') + ' to block the attack.'),
  ('weapons', 'Weapons can also be strengthened with poison.', 'Weapons can also be strengthened with poison ' + ic('ic','poison') + '.'),
  ('weapons', 'Modifier card with a red banner.', 'Modifier card ' + ic('ic','modifier') + ' with a red banner.'),
  ('weapons', '<h4 class="section-title">Thrust</h4>', '<h4 class="section-title">' + ic('ic','thrust') + ' Thrust</h4>'),
  ('poison', '<h4>The three afflictions of the poisoned</h4>', '<h4>' + ic('ic','poison') + ' The three afflictions of the poisoned</h4>'),
  ('interventions', '<p>Intervention is a special card type', '<p>Intervention ' + ic('ic','intervention') + ' is a special card type'),
  ('auras', '<p>Team Auras are powerful cards', '<p>Team Auras ' + ic('ic','aura') + ' are powerful cards'),
  ('characters', 'The number inside the heart is', 'The number inside the heart ' + ic('ic','hp') + ' is'),
  ('conditional', '<strong>Faction bonuses.</strong>', ic('ic','rolectx') + ' <strong>Faction bonuses.</strong>'),
  ('conditional', '<strong>Health context.</strong>', ic('ic','hpctx') + ' <strong>Health context.</strong>'),
  ('conditional', '<strong>Poison conditions.</strong>', ic('ic','poison') + ' <strong>Poison conditions.</strong>'),
  ('conditional', '<strong>Stance conditions.</strong>', ic('ic','stance') + ' <strong>Stance conditions.</strong>'),
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
 'ru': dict(src='rules/rules.html', out='rules/rules-new.html', html_lang='ru',
            title='Самураи против Ниндзя — правила (новая вёрстка)',
            sub='— Самураи против Ниндзя —',
            draft='Черновик новой вёрстки · <a href="rules.html">действующие правила</a>',
            switch='<span class="lang-switch-current">RU</span><a href="rules-new-en.html">EN</a>',
            footer='侍 対 忍者 · правила игры',
            appendix='Стол во время партии',
            comment='Черновик новой вёрстки правил. Текст глав — копия rules.html (русский\n     оригинал); при расхождении прав rules.html. Оформление: rules-new.css.\n     Английская версия — rules-new-en.html, перевод, не оригинал.'),
 'en': dict(src='rules/rules-en.html', out='rules/rules-new-en.html', html_lang='en',
            title='Samurai vs Ninja — Rules (new layout)',
            sub='— Samurai vs Ninja —',
            draft='New layout draft · <a href="rules-en.html">current rules</a>',
            switch='<a href="rules-new.html">RU</a><span class="lang-switch-current">EN</span>',
            footer='侍 対 忍者 · game rules',
            appendix='The table during play',
            comment='New-layout draft of the rules, English version. A translation, not the\n     original: the Russian rules-new.html is the source of truth and this file\n     follows it. Chapter text is copied from rules-en.html. Styles: rules-new.css.'),
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

def build(lang):
    t = L[lang]
    src = open(t['src'], encoding='utf-8').read()
    chapters = sec_re.findall(src)
    assert len(chapters) == 16, (lang, len(chapters))
    out = []
    for cid, mark, title, body in chapters:
        cfg = CH[cid]
        body = body.strip('\n')
        for c, a, b in INLINE[lang]:
            if c == cid:
                if a not in body:
                    print('  ! not found', lang, cid, a[:50]); continue
                body = body.replace(a, b, 1)
        if cid == 'setup':
            body += '<div class="table-inflow">' + table_fig.section(lang) + '</div>'
        if cid == 'order':
            # вместо двух нумерованных списков — две цепочки значков
            body = re.sub(r'<div class="order-list">.*?</div>\s*<div class="order-list">.*?</div>',
                          chain(lang, 'attacker') + chain(lang, 'defender'), body, count=1, flags=re.S)
            assert 'order-list' not in body, lang
        bg = bg_path(cid)
        style = f' style="--bg:url({bg})"' if bg else ''
        out.append(f'''
    <section class="chapter" id="{cid}"{style}>
      <div class="chapter-body">
        <h2 class="chapter-title">{title}</h2>
{body}
        <span class="kanji" aria-hidden="true">{mark}</span>
      </div>
      <aside class="chapter-side">
        {side_icons(cfg['icons'])}
        {card_fan(cfg['cards'], lang, cfg.get('layout', 'fan'))}
      </aside>
    </section>
    <div class="brush-line"></div>''')

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
<link rel="stylesheet" href="rules-new.css">
<link rel="stylesheet" href="rules-new-print.css" media="print">
<script src="typograph.js" defer></script>
</head>
<body>
<!-- {t['comment']} -->
<div class="page">
  <header class="header">
    <div class="hanko">侍<br>忍</div>
    <h1 class="kanji-banner">侍 対 忍者</h1>
    <p class="kanji-sub">{t['sub']}</p>
    <p class="draft-note">{t['draft']}</p>
    <p class="lang-switch">{t['switch']}</p>
  </header>

  <div class="brush-line"></div>
{''.join(out)}

  <!-- Печатное приложение: тот же стол, но в конце брошюры разворотом на
       обе колонки, чтобы не рвать поток глав. На экране скрыт. -->
  <section class="chapter print-only appendix" id="table-appendix">
    <div class="chapter-body">
      <h2 class="chapter-title">{t['appendix']}</h2>
{re.sub(r'<h4>[^<]*</h4>', '', table_fig.section(lang), count=1)}
      <footer class="footer">{t['footer']}</footer>
    </div>
  </section>

  <footer class="footer screen-only">{t['footer']}</footer>
</div>

{SCRIPT}
</body>
</html>
'''
    open(t['out'], 'w', encoding='utf-8', newline='\n').write(html)
    print(lang, 'written', t['out'], len(html))

for lang in ('ru', 'en'):
    build(lang)
