# -*- coding: utf-8 -*-
"""Запуск: py -3 tools/build-cheatsheet.py

Собирает rules/cheatsheet-v2.html — памятку-схему на A5 landscape (RU).
Посередине — зона одного игрока, как на столе: карты-превью из
rules/media/cards/, фигурки из rules/media/fig/, жетоны из media/.
Вокруг — выноски: тонкий контур вокруг предмета, короткая линия и
короткая подпись со значком. Внизу — полоса: порядок расчёта и мелочи.

Все координаты — в миллиметрах листа (210 × 148), общие для HTML-слоя
(карты, подписи) и SVG-слоя (контуры, линии). Правится здесь, HTML
руками не трогать."""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

W, H = 210, 148
CW, CH = 17, 27.2          # карта 5:8

# ---------- предметы на столе: key -> dict(x, y, w, h, rot, src, cls) ----------
OBJ = {}
def card(key, x, y, cid, rot=0):
    OBJ[key] = dict(x=x, y=y, w=CW, h=CH, rot=rot, src=f'media/cards/{cid}.webp', cls='card')
def fig(key, x, y, w, h, src, rot=0, cls='fig'):
    OBJ[key] = dict(x=x, y=y, w=w, h=h, rot=rot, src=src, cls=cls)

# ряд 1 — карты перед игроком
card('char',   64, 21, 137)                       # Сайго
card('role',   83, 21, 201)                       # Самурай
card('stance', 102, 21, 1166)                     # Лучник
card('effect', 121, 21, 91)                       # Метка убийцы
fig('poison', 73.4, 31.5, 6.2, 9.6, 'media/fig/poison.webp')   # бутылка яда на персонаже
# ряд 2 — жетоны, ловушка, аура
for i in range(4):
    fig(f'hp{i}', 64 + i * 5.4, 52.5, 4.8, 4.8, '../media/hp.png', cls='tok')
for i in range(4):
    fig(f'vp{i}', 64 + i * 5.4, 60, 4.8, 4.8, '../media/winpoint.png', cls='tok')
card('trapcard', 94, 50.5, 'back', rot=-6)
fig('trap', 97, 59, 11, 11, 'media/fig/trap.webp')
card('aura', 121, 50.5, 1204)                     # Спина к спине
# ряд 3 — рука, атака, защита
for i, r in enumerate((-22, -11, 0, 11, 22)):
    fig(f'hand{i}', 61 + i * 5.2, 80.5 + abs(i - 2) * 1.4, 13, 20.8, 'media/cards/back.webp', rot=r, cls='card hand')
card('weapon',   110, 78, 1, rot=-4)               # Катана
card('modifier', 117, 81, 70, rot=7)               # Гнев сёгуна
card('defense',  139, 80, 48, rot=-10)             # Защита

import math
def bbox(keys, pad=1.2):
    """Рамка вокруг предметов с учётом поворота (углы каждого предмета
    поворачиваются вокруг его центра, как transform: rotate в CSS)."""
    xs, ys, xe, ye = 1e9, 1e9, -1e9, -1e9
    for k in keys:
        o = OBJ[k]
        cx, cy = o['x'] + o['w'] / 2, o['y'] + o['h'] / 2
        a = math.radians(o['rot'])
        for dx, dy in ((-o['w']/2, -o['h']/2), (o['w']/2, -o['h']/2), (o['w']/2, o['h']/2), (-o['w']/2, o['h']/2)):
            px = cx + dx * math.cos(a) - dy * math.sin(a)
            py = cy + dx * math.sin(a) + dy * math.cos(a)
            xs, ys, xe, ye = min(xs, px), min(ys, py), max(xe, px), max(ye, py)
    return xs - pad, ys - pad, xe + pad, ye + pad

# ---------- выноски: (цель, плашка (x, y, w), заголовок, значок, текст) ----------
# side — с какой стороны плашки выходит линия: 'r' (правая кромка), 'l', 't', 'b'
CALL = [
 (['char'],        (5, 9, 53, 'r'),  'Персонаж', 'hp',
  'Жизни — цифра в сердце; это же максимум для <i>полного здоровья</i>. Открыт всем всю партию.'),
 (['poison'],      (5, 25, 53, 'r'), 'Яд', 'poison',
  'Бутылка на персонаже. В конце хода <b>−2</b> жизни; отравленная атака по вам <b>+1</b> рана. Смерть от яда — без восстановления, очко в сброс.'),
 (['role'],        (76, 4, 24, 'b'), 'Роль', 'rolectx',
  'Самурай, Ниндзя или Сёгун. Сёгун — самурай, начинает раунд.'),
 (['stance'],      (103, 4, 34, 'b'), 'Стойка', 'stance',
  'Раз за ход, одна. Работает сразу. Новая — прежняя в руку.'),
 (['effect'],      (156, 10, 49, 'l'), 'Эффекты', 'effect',
  'Справа от персонажа, в открытую. Постоянные — до смерти, разовые — до срабатывания. Одноимённые не повторяются. Только на живых.'),
 (['hp0','hp1','hp2','hp3'], (5, 47, 53, 'r'), 'Жизни', 'hpctx',
  '<b>0</b> — мертвы до конца хода: очко убийце, открытые карты в сброс, вас никто не трогает. Со следующего хода живы; в свой ход — восстановление.'),
 (['vp0','vp1','vp2','vp3'], (5, 65, 53, 'r'), 'Победные очки', 'winpoint',
  'Старт — <b>4</b>. Убили — забрали очко у жертвы. Чьи-то <b>0</b> — конец партии.'),
 (['aura'],        (156, 44, 49, 'l'), 'Аура', 'aura',
  'Перед персонажем, одна на игрока. Действует на всех за столом; у команды складываются. Новая — прежняя в руку.'),
 (['hand0','hand1','hand2','hand3','hand4'], (5, 80, 53, 'r'), 'Рука', 'card',
  'Старт — <b>7</b>. В начале хода не больше <b>9</b>, лишнее в сброс. В конце хода набор <b>3</b> <i>(меньшая команда +1)</i>, затем каждый противник берёт <b>1</b>. Между ходами не ограничена.'),
 (['trapcard','trap'], (64, 108, 44, 't', .97), 'Ловушка', 'trap',
  'Одна, рубашкой вверх, фигурка сверху. Срабатывает, если атакуют и вы не защищаетесь; метательное её не будит. Подложили не ловушку — умираете.'),
 (['weapon','modifier'], (111, 110, 48, 't', .3), 'Атака', 'weapon',
  'До <b>2</b> за ход. Оружие берёт цель, если его сложность ≥ сложности цели (обычно 1); метательное — любую. Один модификатор. Кулаки — 1/1 за обе атаки.'),
 (['defense'],     (156, 78, 49, 'l'), 'Защита', 'defense',
  'Своя — атака отбита, бонусы атакующего не срабатывают. Союзная, как вмешательство: одна — раны до <b>1</b>, две от команды — до <b>0</b>. Беззащитного не спасти.'),
]

# ---------- нижняя полоса ----------
CHAIN = [('character','персонаж'),('stance','стойка'),('aura','аура'),('poison','яд'),('effect','эффект'),('weapon','оружие'),('modifier','модификатор')]
STRIP = [
 ('intervention', 'Вмешательство', 'не в свой ход, посреди чужого действия или в тишине; всё сыгранное — одновременно, порядок выбирает тот, чья жизнь на кону.'),
 ('thrust', 'Выпад', 'раны напрямую: не атака, без защиты и ловушки, не тратит атаку.'),
 ('action', 'Восстановление', 'в начале хода после смерти: сброс любых карт, добор до <b>7</b>.'),
 ('aoe', 'Конец партии', 'кончилась колода · у кого-то 0 очков · по договорённости, доиграв раунд до игрока перед Сёгуном.'),
]

def esc(s): return s

def ic(key, size=None):
    if key in ('winpoint', 'card'):
        src = '../media/winpoint.png' if key == 'winpoint' else 'media/cards/back.webp'
        return f'<img class="mk" src="{src}" alt="">'
    return f'<i class="ic" data-b="{key}"></i>'

def objects_html():
    out = []
    for k, o in OBJ.items():
        st = f"left:{o['x']}mm;top:{o['y']}mm;width:{o['w']}mm;height:{o['h']}mm;"
        if o['rot']:
            st += f"transform:rotate({o['rot']}deg);"
        out.append(f'<img class="{o["cls"]}" data-k="{k}" src="{o["src"]}" alt="" style="{st}">')
    return '\n'.join(out)

def callouts_html():
    out = []
    for keys, (x, y, w, side, *_), title, icon, text in CALL:
        out.append(f'<div class="co" style="left:{x}mm;top:{y}mm;width:{w}mm"><h4>{ic(icon)}{title}</h4><p>{text}</p></div>')
    return '\n'.join(out)

# Высоты плашек в SVG не известны заранее — линию ведём от точки на кромке
# плашки (для 'r'/'l' — на уровне заголовка, для 't'/'b' — по центру ширины).
import re as _re
def est_h(text, w):
    plain = _re.sub(r'<[^>]+>', '', text)
    lines = -(-len(plain) // max(1, int(w * 0.85)))
    return 3.6 + lines * 2.6

def leader_and_outline(keys, box, side, text=''):
    x, y, w = box[:3]
    f = box[4] if len(box) > 4 else .5        # где на кромке 't'/'b' выходит линия (доля ширины)
    bx0, by0, bx1, by1 = bbox(keys)
    if side == 'r':   sx, sy = x + w, y + 1.6;  tx, ty = bx0, min(max(sy, by0), by1)
    elif side == 'l': sx, sy = x, y + 1.6;      tx, ty = bx1, min(max(sy, by0), by1)
    elif side == 'b': sx, sy = x + w * f, y + est_h(text, w); tx, ty = min(max(sx, bx0), bx1), by0
    else:             sx, sy = x + w * f, y - .6;  tx, ty = min(max(sx, bx0), bx1), by1
    return (f'<rect x="{bx0:.1f}" y="{by0:.1f}" width="{bx1-bx0:.1f}" height="{by1-by0:.1f}" rx="1.6"/>',
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}"/>')

def svg_html():
    rects, lines = [], []
    for keys, box, _t, _i, text in CALL:
        r, l = leader_and_outline(keys, box, box[3], text); rects.append(r); lines.append(l)
    return (f'<svg class="ov" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
            '<defs><marker id="dot" viewBox="0 0 4 4" refX="2" refY="2" markerWidth="3" markerHeight="3"><circle cx="2" cy="2" r="1.6"/></marker></defs>'
            '<g class="lines">' + ''.join(lines) + '</g><g class="outl">' + ''.join(rects) + '</g></svg>')

def strip_html():
    chain = ''.join(f'<span class="st"><i class="ic" data-b="{k}"></i>{t}</span><span class="arr">→</span>' for k, t in CHAIN)
    chain = chain[:-len('<span class="arr">→</span>')]
    items = ''.join(f'<p><i class="ic" data-b="{k}"></i><b>{t}</b> — {d}</p>' for k, t, d in STRIP)
    return (f'<div class="strip"><div class="chain"><b>Порядок расчёта</b>{chain}'
            '<span class="tail">у защищающегося то же, последней — <i class="ic" data-b="trap"></i> ловушка · «не менее 1» держится с места, где встретился</span></div>'
            f'<div class="misc">{items}</div></div>')

CSS = r"""
  @font-face { font-family: 'Han Zi Web'; src: url('fonts/Han-Zi_Regular.woff') format('woff'); font-display: swap; }
  :root {
    --paper-light:#f4ead2; --paper-deep:#c4a86a; --ink:#1c1410; --ink-soft:#3a2a1d; --ink-faded:#6a4a30;
    --vermilion:#b1281d; --vermilion-dk:#7a1410; --gold:#8b6a2a;
    --fs: 6.9pt; --ic: 3.4mm;
  }
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; background: radial-gradient(ellipse at top, #2a1a10 0%, #150a05 70%), #0a0503;
    color: var(--ink); font-family: 'PT Sans Narrow', 'PT Sans', Arial, sans-serif; min-height:100vh; }
  .desk { min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:24px 16px 40px; gap:14px; }
  .desk-note { color:#b39a6f; font-size:14px; letter-spacing:.04em; opacity:.8; }
  .desk-note a { color:#d8c39a; }

  .sheet { position:relative; width:210mm; height:148mm; overflow:hidden; font-size:var(--fs); line-height:1.25;
    background: radial-gradient(ellipse 60mm 40mm at 85% 12%, rgba(120,70,20,.10), transparent 70%),
                radial-gradient(ellipse 50mm 30mm at 20% 70%, rgba(120,70,20,.10), transparent 70%),
                url('media/paper.png') center / 100% 100% no-repeat var(--paper-light);
    box-shadow: 0 0 0 1px rgba(60,30,10,.4), 0 20px 50px rgba(0,0,0,.65); }
  .sheet::before { content:""; position:absolute; inset:8mm 40mm 26mm; background:url('media/bg/flow.webp') center / contain no-repeat;
    opacity:.09; mix-blend-mode:multiply; pointer-events:none; }

  /* заголовок листа — как заголовок главы правил */
  .ttl { position:absolute; left:6mm; top:4mm; font-family:'Han Zi Web','Shippori Mincho',serif; font-size:10.5pt; text-transform:uppercase;
    letter-spacing:.04em; color:var(--ink); display:flex; align-items:center; gap:2.5mm; line-height:1; }
  .ttl .kanji { font-family:'Shippori Mincho','Noto Serif JP','Yu Mincho',serif; font-size:11pt; color:rgba(122,20,16,.45); text-transform:none; letter-spacing:.06em; }
  .ttl .kanji::before { content:"·"; font-family:'PT Sans Narrow',sans-serif; font-size:9pt; color:rgba(70,58,50,.28); margin-right:2.5mm; }
  .ttl2 { position:absolute; right:6mm; top:5mm; font-size:7pt; color:var(--ink-faded); letter-spacing:.08em; text-transform:uppercase; }

  /* предметы на столе */
  .card { position:absolute; display:block; border-radius:1mm; box-shadow:0 .5mm 1.2mm rgba(40,20,5,.35); outline:.35mm solid #fff; }
  .card.hand { outline-width:.3mm; box-shadow:0 .4mm 1mm rgba(40,20,5,.35); }
  .fig { position:absolute; display:block; filter: drop-shadow(0 .5mm .6mm rgba(0,0,0,.45)); }
  .tok { position:absolute; display:block; filter: drop-shadow(0 .3mm .4mm rgba(0,0,0,.35)); }

  /* SVG-слой: контуры и линии */
  .ov { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
  .ov .outl rect { fill:none; stroke:var(--vermilion); stroke-width:.3; opacity:.75; }
  .ov .lines line { stroke:var(--vermilion); stroke-width:.3; opacity:.8; marker-end:url(#dot); }
  .ov #dot circle { fill:var(--vermilion); }

  /* выноски */
  .co { position:absolute; }
  .co h4 { margin:0 0 .4mm; font-size:7.4pt; font-weight:700; color:var(--ink-soft); display:flex; align-items:center; gap:1.4mm; line-height:1.1; }
  .co p { margin:0; color:var(--ink); }
  .co p b { color:var(--vermilion); }
  .co p i { font-style:italic; color:var(--ink-faded); font-weight:700; }

  /* значки */
  .ic { display:inline-block; position:relative; width:var(--ic); height:var(--ic); border-radius:50%; vertical-align:-.9mm; flex:none; }
  .ic > img { position:absolute; inset:0; width:100%; height:100%; display:block; padding:20%; filter:brightness(0) invert(1); }
  .ic.raw { background:#fff; box-shadow:0 0 0 .22mm var(--paper-deep) inset; }
  .ic.raw > img { padding:14%; filter:none; }
  .ic.b-rolectx > img { padding:10%; }
  .ic.b-hp { background:none; box-shadow:none; }
  .ic.b-hp > img { padding:0; filter:none; }
  .mk { display:inline-block; width:var(--ic); height:var(--ic); object-fit:contain; vertical-align:-.9mm; flex:none; }
  h4 .mk { border-radius:.5mm; }

  /* нижняя полоса */
  .strip { position:absolute; left:6mm; right:6mm; bottom:3.5mm; height:18mm; padding-top:1.4mm;
    border-top:.2mm solid rgba(122,20,16,.25); display:grid; grid-template-columns: 78mm 1fr; column-gap:5mm; }
  .chain { display:flex; flex-wrap:wrap; align-items:center; gap:.3mm; font-size:6.2pt; color:var(--ink-soft); line-height:1.1; }
  .chain > b { width:100%; font-size:7.4pt; color:var(--ink-soft); margin-bottom:.8mm; }
  .chain .st { display:inline-flex; flex-direction:column; align-items:center; width:9.6mm; text-align:center; }
  .chain .st .ic { --ic:4mm; margin-bottom:.3mm; }
  .chain .arr { color:rgba(70,58,50,.35); font-size:6pt; margin:0 -.5mm 2.6mm; }
  .chain .tail { width:100%; margin-top:.8mm; font-size:6.4pt; color:var(--ink-faded); }
  .chain .tail .ic { --ic:2.8mm; vertical-align:-.7mm; }
  .misc p { margin:0 0 .7mm; color:var(--ink); }
  .misc p .ic { --ic:3mm; margin-right:1mm; vertical-align:-.7mm; }
  .misc p b { color:var(--ink-soft); }
  .misc p b + span, .misc p b { font-weight:700; }

  /* печать */
  @page { size: A5 landscape; margin:0; }
  @media print {
    html, body { background:#fff; }
    .desk { min-height:auto; padding:0; gap:0; display:block; }
    .desk-note { display:none; }
    .sheet { box-shadow:none; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  }
"""

SCRIPT = r"""
  (function () {
    var M = '../media/';
    var GROUP = { defense:'#dca300', trap:'#43525A', weapon:'#2E2A28', stance:'#A78B6B', modifier:'#ED1C24', aoe:'#2E2A28',
      aura:'#93a32e', effect:'#2E2A28', intervention:'#3B8476', action:'#2E2A28', character:'#6C8CC7', role:'#5d3c75' };
    var SPECIAL = { poison:{color:'#4F7A21', glyph:M+'icons/poison.svg'}, thrust:{color:'#8B1E2D', glyph:M+'icons/thrust.svg'},
      rolectx:{glyph:M+'icons/rolectx.svg', raw:true}, hpctx:{glyph:M+'icons/hpctx.svg', raw:true},
      charges:{glyph:M+'icons/charges.svg', raw:true}, hp:{png:M+'hp.png'} };
    document.querySelectorAll('.ic[data-b]').forEach(function (el) {
      var key = el.getAttribute('data-b');
      var b = SPECIAL[key] || (GROUP[key] && { color: GROUP[key], glyph: M + 'types/' + key + '.svg' });
      if (!b) return;
      el.classList.add('b-' + key);
      if (b.raw || b.png) el.classList.add('raw');
      if (b.color) el.style.background = b.color;
      var e = document.createElement('img'); e.src = b.glyph || b.png; e.alt = ''; e.draggable = false; el.appendChild(e);
    });
  })();
"""

def build():
    html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Самураи против Ниндзя — памятка-схема A5</title>
<link rel="icon" type="image/svg+xml" href="../media/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Sans+Narrow:wght@400;700&family=Shippori+Mincho:wght@400&display=swap" rel="stylesheet">
<!-- СОБИРАЕТСЯ tools/build-cheatsheet.py — руками не править. -->
<style>{CSS}</style>
</head>
<body>
<div class="desk">
  <div class="desk-note">Памятка-схема · A5 горизонтально · <a href="rules.html">правила</a> · <a href="cheatsheet.html">памятка в три колонки</a></div>
  <div class="sheet">
    <div class="ttl">Зона игрока <span class="kanji">陣</span></div>
    <div class="ttl2">Самураи против Ниндзя · памятка</div>
{objects_html()}
{svg_html()}
{callouts_html()}
{strip_html()}
  </div>
</div>
<script>{SCRIPT}</script>
</body>
</html>
'''
    open('rules/cheatsheet-v2.html', 'w', encoding='utf-8', newline='\n').write(html)
    print('written rules/cheatsheet-v2.html')

if __name__ == '__main__':
    build()
