# -*- coding: utf-8 -*-
"""Запуск: py -3 tools/build-cheatsheet.py

Собирает rules/cheatsheet-v2.html — памятку-схему на A5 landscape (RU).
Внизу по центру — зона одного игрока, как она лежит на столе перед ним:
карты-превью из rules/media/cards/, фигурки из rules/media/fig/, жетоны из
media/. Слева вверху — рука, справа вверху — атака и защита, по центру
вверху — порядок расчёта и мелочи. К предметам ведут выноски: кистевая
скобка у кромки предмета, сужающийся штрих и короткая подпись со значком.

Все координаты — в миллиметрах листа (210 × 148), общие для HTML-слоя
(карты, подписи) и SVG-слоя (скобки, штрихи). Правится здесь, HTML
руками не трогать."""
import os, sys, math, re
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

W, H = 210, 148
CW, CH = 15, 24            # карта 5:8

# ---------- предметы: key -> dict(x, y, w, h, rot, src, cls) ----------
OBJ = {}
def card(key, x, y, cid, rot=0, w=CW, h=CH, cls='card'):
    OBJ[key] = dict(x=x, y=y, w=w, h=h, rot=rot, src=f'media/cards/{cid}.webp', cls=cls)
def lcard(key, x, y, cid):
    """Карта, лежащая боком: видимый прямоугольник (x, y, CH, CW)."""
    cx, cy = x + CH / 2, y + CW / 2
    card(key, cx - CW / 2, cy - CH / 2, cid, rot=90)
def fig(key, x, y, w, h, src, rot=0, cls='fig'):
    OBJ[key] = dict(x=x, y=y, w=w, h=h, rot=rot, src=src, cls=cls)

# --- рука: левый верхний угол ---
for i, r in enumerate((-22, -11, 0, 11, 22)):
    fig(f'hand{i}', 12 + i * 5.4, 10 + abs(i - 2) * 1.2, 12, 19.2, 'media/cards/back.webp', rot=r, cls='card hand')

# --- атака и защита: правый верхний угол ---
card('weapon',   150, 8, 1, rot=-6)                # Катана
card('modifier', 158, 11, 70, rot=6)               # Гнев сёгуна
card('defense',  184, 9, 48, rot=-10)              # Защита

# --- зона игрока: низ по центру ---
lcard('trapcard', 62, 93, 'back')                  # ловушка — рубашкой вверх, боком
fig('trap', 69.5, 96, 9, 9, 'media/fig/trap.webp')
lcard('char', 62, 113, 137)                        # Сайго — боком
fig('poison', 71.4, 116.5, 5.2, 8, 'media/fig/poison.webp')
lcard('role', 88, 113, 201)                        # Самурай — боком, рядом
for i in range(4):
    fig(f'hp{i}', 63 + i * 5.2, 131, 4.6, 4.6, '../media/hp.png', cls='tok')
for i in range(4):
    fig(f'vp{i}', 63 + i * 5.2, 138.3, 4.6, 4.6, '../media/winpoint.png', cls='tok')
card('effect0', 118, 110, 91)                      # эффекты — стопкой, на треть выше
card('effect1', 121, 107, 91)
card('effect2', 124, 104, 91)
card('stance',  139, 118, 1166)                    # Лучник
card('aura',    139, 92, 1204)                     # Спина к спине — над стойкой

def bbox(keys, pad=1.0):
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

# ---------- выноски ----------
# (цели, плашка (x, y, w), сторона скобки относительно предмета:
#  'top' — скобка над предметом, текст выше; 'bottom' — под; 'left' — слева,
#  текст левее; 'right' — справа; 'dot' — без скобки, штрих в точку; заголовок, значок, текст)
CALL = [
 (['hand0','hand1','hand2','hand3','hand4'], (6, 40, 54), 'bottom', 'Рука', 'card',
  'Старт — <b>7</b>. В начале хода не больше <b>9</b>, лишнее в сброс. В конце хода набор <b>3</b> <i>(меньшая команда +1)</i>, затем каждый противник берёт <b>1</b>. Между ходами не ограничена.'),
 (['weapon','modifier'], (144, 40, 36), 'bottom', 'Атака', 'weapon',
  'До <b>2</b> за ход. Оружие берёт цель, если его сложность ≥ сложности цели (обычно 1); метательное — любую. Один модификатор. Кулаки — 1/1 за обе атаки.'),
 (['defense'], (160, 66, 44), 'bottom', 'Защита', 'defense',
  'Своя — атака отбита, бонусы атакующего не срабатывают. Союзная, как вмешательство: одна — раны до <b>1</b>, две от команды — до <b>0</b>. Беззащитного не спасти.'),
 (['trapcard','trap'], (46, 58, 40), 'top', 'Ловушка', 'trap',
  'Одна, рубашкой вверх, фигурка сверху. Срабатывает, если атакуют и вы не защищаетесь; метательное её не будит. Подложили не ловушку — умираете.'),
 (['role'], (88, 78, 26), 'top', 'Роль', 'rolectx',
  'Самурай, Ниндзя или Сёгун. Сёгун — самурай, начинает раунд.'),
 (['effect0','effect1','effect2'], (114, 58, 34), 'top', 'Эффекты', 'effect',
  'Справа, в открытую, сколько угодно. Постоянные — до смерти, разовые — до срабатывания. Одноимённые не повторяются. Только на живых.'),
 (['aura'], (160, 92, 44), 'right', 'Аура', 'aura',
  'Над стойкой, одна на игрока. Действует на всех за столом; у команды складываются. Новая — прежняя в руку.'),
 (['stance'], (160, 118, 44), 'right', 'Стойка', 'stance',
  'Раз за ход, одна. Работает сразу. Новая — прежняя в руку.'),
 (['char'], (5, 96, 53), 'left', 'Персонаж', 'hp',
  'Жизни — цифра в сердце; это же максимум для <i>полного здоровья</i>. Открыт всем всю партию.'),
 (['poison'], (5, 109, 53), 'dot', 'Яд', 'poison',
  'Бутылка на персонаже. В конце хода <b>−2</b> жизни; отравленная атака по вам <b>+1</b> рана. Смерть от яда — без восстановления, очко в сброс.'),
 (['hp0','hp1','hp2','hp3'], (5, 124, 53), 'left', 'Жизни', 'hpctx',
  '<b>0</b> — мертвы до конца хода: очко убийце, открытые карты в сброс, вас никто не трогает. Со следующего хода живы; в свой ход — восстановление.'),
 (['vp0','vp1','vp2','vp3'], (5, 137.5, 53), 'left', 'Победные очки', 'winpoint',
  'Старт — <b>4</b>. Убили — забрали очко у жертвы. Чьи-то <b>0</b> — конец партии.'),
]

# ---------- центр вверху: порядок расчёта и мелочи ----------
CHAIN = [('character','персонаж'),('stance','стойка'),('aura','аура'),('poison','яд'),('effect','эффект'),('weapon','оружие'),('modifier','модификатор')]
STRIP = [
 ('intervention', 'Вмешательство', 'не в свой ход, посреди чужого действия или в тишине; всё сыгранное — одновременно, порядок выбирает тот, чья жизнь на кону.'),
 ('thrust', 'Выпад', 'раны напрямую: не атака, без защиты и ловушки, не тратит атаку.'),
 ('action', 'Восстановление', 'в начале хода после смерти: сброс любых карт, добор до <b>7</b>.'),
 ('aoe', 'Конец партии', 'кончилась колода · у кого-то 0 очков · по договорённости, доиграв раунд до игрока перед Сёгуном.'),
]

def ic(key):
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
    for keys, (x, y, w), side, title, icon, text in CALL:
        out.append(f'<div class="co co-{side}" style="left:{x}mm;top:{y}mm;width:{w}mm"><h4>{ic(icon)}{title}</h4><p>{text}</p></div>')
    return '\n'.join(out)

def est_h(text, w):
    """Оценка высоты плашки: ~0.85 знака на мм при 6.9pt узкого шрифта."""
    plain = re.sub(r'<[^>]+>', '', text)
    lines = -(-len(plain) // max(1, int(w * 0.85)))
    return 3.6 + lines * 2.55

# ---------- кистевая графика ----------
L = 2.4   # длина «усов» скобки

def bracket(side, b):
    """Квадратная скобка у одной кромки рамки предмета: ⎴ ⎵ [ ]."""
    x0, y0, x1, y1 = b
    if side == 'top':    return f'M{x0:.1f},{y0+L:.1f} V{y0:.1f} H{x1:.1f} V{y0+L:.1f}'
    if side == 'bottom': return f'M{x0:.1f},{y1-L:.1f} V{y1:.1f} H{x1:.1f} V{y1-L:.1f}'
    if side == 'left':   return f'M{x0+L:.1f},{y0:.1f} H{x0:.1f} V{y1:.1f} H{x0+L:.1f}'
    if side == 'right':  return f'M{x1-L:.1f},{y0:.1f} H{x1:.1f} V{y1:.1f} H{x1-L:.1f}'
    return ''

def stroke(p0, p1, w0=1.0, w1=0.25, bend=0.12, n=14):
    """Сужающийся штрих от p0 (у предмета, толстый) к p1 (у текста, тонкий):
    слегка изогнутая квадратичная кривая, обведённая полигоном."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy) or 1
    nx, ny = -dy / d, dx / d                   # нормаль
    cx, cy = (x0 + x1) / 2 + nx * d * bend, (y0 + y1) / 2 + ny * d * bend
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        px = (1-t)**2 * x0 + 2*(1-t)*t * cx + t**2 * x1
        py = (1-t)**2 * y0 + 2*(1-t)*t * cy + t**2 * y1
        tx = 2*(1-t)*(cx - x0) + 2*t*(x1 - cx)
        ty = 2*(1-t)*(cy - y0) + 2*t*(y1 - cy)
        tl = math.hypot(tx, ty) or 1
        wx, wy = -ty / tl, tx / tl
        hw = (w0 + (w1 - w0) * t) / 2
        left.append((px + wx*hw, py + wy*hw)); right.append((px - wx*hw, py - wy*hw))
    pts = left + right[::-1]
    return 'M' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in pts) + ' Z'

def leader(keys, box, side, text):
    x, y, w = box
    b = bbox(keys)
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    h = est_h(text, w)
    if side == 'top':
        p0 = (min(max(cx, x + 4), x + w - 4), y0 - .3); p1 = (p0[0], y + h + .8)
    elif side == 'bottom':
        p0 = (min(max(cx, x + 4), x + w - 4), y1 + .3); p1 = (p0[0], y - .8)
    elif side == 'left':
        p0 = (x0 - .3, cy); p1 = (x + w + .6, y + 1.6)
    elif side == 'right':
        p0 = (x1 + .3, cy); p1 = (x - .6, y + 1.6)
    else:   # dot — в точку на предмете, без скобки
        p0 = (cx, cy); p1 = (x + w + .6, y + 1.6)
    br = bracket(side, b) if side != 'dot' else ''
    dot = f'<circle class="pin" cx="{cx:.1f}" cy="{cy:.1f}" r="1.1"/>' if side == 'dot' else ''
    return br, stroke(p0, p1), dot

def svg_html():
    brs, sts, dots = [], [], []
    for keys, box, side, _t, _i, text in CALL:
        br, st, dot = leader(keys, box, side, text)
        if br: brs.append(f'<path d="{br}"/>')
        sts.append(f'<path d="{st}"/>'); dots.append(dot)
    return (f'<svg class="ov" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
            '<defs><filter id="ink" x="-5%" y="-5%" width="110%" height="110%">'
            '<feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="2" seed="7" result="n"/>'
            '<feDisplacementMap in="SourceGraphic" in2="n" scale=".45" xChannelSelector="R" yChannelSelector="G"/></filter></defs>'
            '<g class="br" filter="url(#ink)">' + ''.join(brs) + '</g>'
            '<g class="st" filter="url(#ink)">' + ''.join(sts) + '</g>'
            '<g>' + ''.join(dots) + '</g></svg>')

def center_html():
    chain = ''.join(f'<span class="s"><i class="ic" data-b="{k}"></i>{t}</span><span class="arr">→</span>' for k, t in CHAIN)
    chain = chain[:-len('<span class="arr">→</span>')]
    items = ''.join(f'<p><i class="ic" data-b="{k}"></i><b>{t}</b> — {d}</p>' for k, t, d in STRIP)
    return (f'<div class="center"><div class="chain"><b>Порядок расчёта</b>{chain}'
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
  /* бледная тушь — на свободном месте слева посередине */
  .sheet::before { content:""; position:absolute; left:4mm; top:56mm; width:56mm; height:40mm;
    background:url('media/bg/flow.webp') center / contain no-repeat; opacity:.11; mix-blend-mode:multiply; pointer-events:none; }

  /* заголовок — как заголовок главы правил, по центру сверху */
  .ttl { position:absolute; left:0; right:0; top:4mm; display:flex; justify-content:center; align-items:center; gap:2.5mm;
    font-family:'Han Zi Web','Shippori Mincho',serif; font-size:10.5pt; text-transform:uppercase; letter-spacing:.04em; color:var(--ink); line-height:1; }
  .ttl .kanji { font-family:'Shippori Mincho','Noto Serif JP','Yu Mincho',serif; font-size:11pt; color:rgba(122,20,16,.45); text-transform:none; letter-spacing:.06em; }
  .ttl .kanji::before { content:"·"; font-family:'PT Sans Narrow',sans-serif; font-size:9pt; color:rgba(70,58,50,.28); margin-right:2.5mm; }

  /* предметы */
  .card { position:absolute; display:block; border-radius:.9mm; box-shadow:0 .5mm 1.2mm rgba(40,20,5,.35); outline:.32mm solid #fff; }
  .card.hand { outline-width:.28mm; box-shadow:0 .4mm 1mm rgba(40,20,5,.35); }
  .fig { position:absolute; display:block; filter: drop-shadow(0 .5mm .6mm rgba(0,0,0,.45)); }
  .tok { position:absolute; display:block; filter: drop-shadow(0 .3mm .4mm rgba(0,0,0,.35)); }

  /* SVG-слой: скобки и штрихи тушью */
  .ov { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
  .ov .br path { fill:none; stroke:var(--ink-soft); stroke-width:.42; stroke-linecap:round; stroke-linejoin:round; opacity:.85; }
  .ov .st path { fill:var(--ink-soft); opacity:.8; }
  .ov .pin { fill:var(--vermilion); opacity:.9; }

  /* выноски */
  .co { position:absolute; }
  .co h4 { margin:0 0 .4mm; font-size:7.4pt; font-weight:700; color:var(--ink-soft); display:flex; align-items:center; gap:1.4mm; line-height:1.1; }
  .co p { margin:0; color:var(--ink); }
  .co p b { color:var(--vermilion); }
  .co p i { font-style:italic; color:var(--ink-faded); font-weight:700; }
  .co-right h4, .co-right p { text-align:left; }

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

  /* центр вверху */
  .center { position:absolute; left:64mm; top:13mm; width:80mm; }
  .chain { display:flex; flex-wrap:wrap; align-items:center; gap:.3mm; font-size:6.2pt; color:var(--ink-soft); line-height:1.1; }
  .chain > b { width:100%; font-size:7.4pt; margin-bottom:.8mm; }
  .chain .s { display:inline-flex; flex-direction:column; align-items:center; width:9.4mm; text-align:center; }
  .chain .s .ic { --ic:3.8mm; margin-bottom:.3mm; }
  .chain .arr { color:rgba(70,58,50,.35); font-size:6pt; margin:0 -.5mm 2.6mm; }
  .chain .tail { width:100%; margin-top:.6mm; font-size:6.3pt; color:var(--ink-faded); }
  .chain .tail .ic { --ic:2.8mm; vertical-align:-.7mm; }
  .misc { margin-top:1.8mm; padding-top:1.4mm; border-top:.2mm solid rgba(122,20,16,.25); }
  .misc p { margin:0 0 .6mm; color:var(--ink); }
  .misc p .ic { --ic:3mm; margin-right:1mm; vertical-align:-.7mm; }
  .misc p b { color:var(--ink-soft); }

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
    <div class="ttl">Самураи против Ниндзя <span class="kanji">覚</span></div>
{objects_html()}
{svg_html()}
{callouts_html()}
{center_html()}
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
