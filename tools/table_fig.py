# -*- coding: utf-8 -*-
"""Глава «Стол» для rules*.html (импорт из build-rules-new.py):
картинка стола + SVG-слой с подписями внутри стола и короткими стрелками.
Координаты — в пикселях исходной картинки 1192×1165, общие для обоих языков."""
import os, re, math, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

W0, H = 1192, 1165        # фото стола; координаты подписей — в его пикселях
PAD = 110                 # слева холст расширен под дугу ауры за спиной левого ниндзя (compose-table-effects.py)
W = W0 + PAD              # ширина итоговой картинки rules/media/table.webp
# Картинка стола — rules/media/table.webp (скриншот стола, белый фон вырезан
# в прозрачность); координаты ниже — в её пикселях.

# (ключ, центр подписи (x,y), цель стрелки (x,y))
# Подписи стоят внутри стола, в свободных местах рядом со своим предметом —
# стрелки короткие. Ориентиры (пиксели картинки): круг стола — центр (600,585),
# радиус ~375; верхний игрок: стойка (540,300), роль (593,300), сердца (555,350),
# очки (665,345), рука (720,290); левый: персонаж (355,555), роль (355,605);
# правый: столбик эффектов (878,515…605), бутылка яда на карте роли (879,556) — повёрнута
# на 90° влево, как его карты (tools/compose-table-poison.py),
# карта защиты (806,704); нижний: сердца (585,800), очки (655,810), персонаж
# (587,855); центр: колода (578,565), сброс (650,565); атака (705,715)+(740,740);
# ловушка левого игрока — рубашка вверх портретом с фигуркой макибиси (452,580), перед его
# персонажем и ролью, ближе к центру стола (tools/compose-table-trap.py; прежний капкан боком — obsolete/table-v3-beartrap.webp).
# Стрелка атаки: нижний самурай атакует правого ниндзя (FLOW).
# Бутылка, капкан и карта защиты дорисованы поверх фото (rules/media/obsolete/
# table-v1.webp — исходник без них) скриптом-монтажом: фигурки — /img, карта —
# превью 48.webp, рубашка ловушки — старая media/backs/obsolete/default_real.png; слои
# строились в 4× и поворачивались до уменьшения.
LABELS = [
    ('stance',    (428, 300), (515, 300)),    # слева от стойки, у кромки
    ('role',      (600, 425), (593, 335)),    # под картами верхнего игрока
    ('hand',      (850, 380), (760, 315)),    # справа-снизу от веера
    ('trap',      (500, 645), (458, 612)),    # под ловушкой левого игрока, между жетонами и колодой
    ('character', (470, 445), (365, 532)),    # верхняя левая четверть
    ('auracard',  (300, 432), (330, 480)),    # над картой ауры левого ниндзя, у кромки стола
    ('deck',      (500, 500), (560, 565)),    # слева-сверху от колоды
    ('discard',   (712, 614), (668, 588)),    # справа-снизу от сброса
    ('effect',    (790, 430), (856, 462)),    # над столбиком эффектов — к верхней карте («Пыль в глаза»)
    ('intervention', (716, 390), (708, 412)),  # над «Щитоломом» верхнего самурая, между «Картой роли» и «Рукой»
    ('poison',    (800, 540), (862, 552)),    # бутылка яда на карте роли
    ('defense',   (815, 762), (812, 732)),    # под картой защиты
    ('attack',    (540, 722), (688, 714)),    # слева от выложенной атаки
    ('life',      (430, 790), (565, 800)),    # слева от сердец нижнего игрока
    ('vp',        (800, 812), (683, 812)),    # справа от очков нижнего игрока
]
# фракционные метки у фигур: (текст-ключ, центр)
TAGS = [('samurai', (335, 150)), ('ninja', (1080, 395)), ('samurai', (760, 1060)), ('ninja', (140, 400))]   # верхний самурай — метка слева, справа идёт дуга вмешательства
# стрелки хода — дуги снаружи стола, концентрично его кромке (центр CX,CY, радиус кромки ≈410):
# (ключ подписи, класс, угол начала, угол конца, значки типов посередине дуги, радиус подписи).
# Углы — от оси x по часовой (y вниз): 0° — правый ниндзя, 90° — нижний самурай, −90° — верхний.
# Атака: нижний самурай → правый ниндзя; защита: короткая дуга от ниндзя навстречу атаке;
# вмешательство: верхний самурай → ниндзя. Значки стоят на дуге, подписи — снаружи от неё.
CX, CY, R_ARC = 597, 582, 470
R_AURA = 605              # дуга ауры — снаружи фигуры ниндзя
FLOWS = [
    ('attacks',    'attack',  68,  37, ['weapon', 'modifier'], 560),   # две трети пути от самурая к ниндзя; значки — от острия: оружие, за ним модификатор
    ('defends',    'def',     16,  34, ['defense'],            0, -4), # навстречу, одна треть; значок ближе к ниндзя, чтобы не упирался в остриё; подпись — DEF_LABEL
    ('intervenes', 'int',    -66, -22, ['intervention'],       560),   # до самого ниндзя, к его метке
    ('aura',       'aura',   205, 155, ['aura'],               0),     # за спиной левого ниндзя (радиус R_AURA, на поле PAD): аура — на весь стол; подпись — AURA_LABEL
]
AURA_LABEL = (130, 930)   # сильно ниже нижнего конца дуги, у левой кромки
DEF_LABEL = (1095, 870)   # «Защищается» — ниже дуги, не наезжая на значок   # плашка «Аура — на весь стол» под концом дуги, слева-снизу от ниндзя
import math
def polar(a, r=R_ARC):
    return (CX + r * math.cos(math.radians(a)), CY + r * math.sin(math.radians(a)))
def arc_path(a0, a1, r=R_ARC):
    (x0, y0), (x1, y1) = polar(a0, r), polar(a1, r)
    return f'M {x0:.0f} {y0:.0f} A {r} {r} 0 0 {1 if a1 > a0 else 0} {x1:.0f} {y1:.0f}'
def flow_r(key):
    return R_AURA if key == 'aura' else R_ARC
def flow_icons():
    """Значки типов на середине каждой дуги: (ключ, центр); два значка — по 5° в стороны от середины."""
    out = []
    for key, cls, a0, a1, icons, _, *rest in FLOWS:
        mid = (a0 + a1) / 2 + (rest[0] if rest else 0)
        step = -7 if a1 > a0 else 7        # первый значок — ближе к острию, следующие — за ним
        for i, ic in enumerate(icons):
            out.append((ic, polar(mid + (i - (len(icons) - 1) / 2) * step, flow_r(key))))
    return out

TXT = {
 'ru': {
  'stance': 'Стойка', 'role': 'Карта роли', 'deck': 'Колода', 'character': 'Персонаж',
  'hand': 'Рука', 'discard': 'Сброс', 'effect': 'Эффекты', 'life': 'Жизни',
  'vp': 'Победные очки', 'attack': 'Атака: оружие|+ модификатор',
  'poison': 'Яд', 'defense': 'Защита', 'trap': 'Ловушка', 'attacks': 'Атакует',
  'defends': 'Защищается', 'intervenes': 'Вмешивается', 'aura': 'Аура — на весь стол', 'auracard': 'Аура',
  'intervention': 'Вмешательство',
  'samurai': 'Самурай', 'ninja': 'Ниндзя',
  'h4': 'Стол',
  'intro': 'Так выглядит стол в середине партии на четверых: у каждого игрока перед собой своя зона, посреди стола — общие стопки. Игроки сидят через одного, поэтому напротив — союзник, а по бокам — противники.',
  'legend': [
   ('character', 'карта персонажа лежит перед игроком в открытую всю партию; цифра в сердце — стартовые жизни.'),
   ('role',      'Самурай или Ниндзя — рядом с персонажем, тоже в открытую.'),
   ('stance',    'перед собой в открытую, не больше одной; новая заменяет старую.'),
   ('effect',    'справа от персонажа, в открытую. Сюда же ложатся эффекты, наложенные на вас другими игроками.'),
   ('life',      'жетоны-сердца по цифре на карте персонажа. Опустились до нуля — вы обескровлены.'),
   ('vp',        'жетоны победных очков, по умолчанию четыре. Убили — забрали очко у жертвы.'),
   ('hand',      'карты рубашкой вверх, в конце хода на руке не больше восьми.'),
   ('deck',      'общая колода посреди стола, рубашкой вверх. Кончилась — партия заканчивается.'),
   ('discard',   'рядом с колодой, картинкой вверх. Из сброса карты не возвращаются.'),
   ('attack',    'оружие и модификатор выкладываются на стол в сторону цели, после расчёта уходят в сброс.'),
  ],
  'outro': 'Ловушка кладётся перед собой рубашкой вверх, сверху — фигурка капкана; яд отмечают фигуркой-бутылкой на карте роли. Аура кладётся перед собой в открытую, сверху — фигурка знамени; на этой картинке её нет. Верхний самурай подкрепляет атаку союзника вмешательством — «Щитоломом».',
  'caption': 'Стол на четверых: самурай — ниндзя — самурай — ниндзя.',
  'note': 'За большим столом — на восьмерых — колоду и сброс удобно разделить на две стопки и поставить с разных сторон, чтобы каждому было легко дотянуться: колода перетасована, а порядок карт в сбросе не важен.',
 },
 'en': {
  'stance': 'Stance', 'role': 'Role card', 'deck': 'Deck', 'character': 'Character',
  'hand': 'Hand', 'discard': 'Discard', 'effect': 'Effects', 'life': 'Life',
  'vp': 'Victory points', 'attack': 'Attack: weapon|+ modifier',
  'poison': 'Poison', 'defense': 'Defense', 'trap': 'Trap', 'attacks': 'Attacks',
  'defends': 'Defends', 'intervenes': 'Intervenes', 'aura': 'Aura — whole table', 'auracard': 'Aura',
  'intervention': 'Intervention',
  'samurai': 'Samurai', 'ninja': 'Ninja',
  'h4': 'The Table',
  'intro': 'This is what a four-player table looks like mid-game: every player has their own area in front of them, and the shared piles sit in the middle. Seats alternate, so the player opposite is your ally and the players on either side are enemies.',
  'legend': [
   ('character', 'the character card lies face up in front of the player for the whole game; the number in the heart is the starting life.'),
   ('role',      'Samurai or Ninja — next to the character, also face up.'),
   ('stance',    'face up in front of you, one at most; a new one replaces the old.'),
   ('effect',    'to the right of the character, face up. Effects other players put on you go here too.'),
   ('life',      'heart tokens matching the number on the character card. Down to zero — you have bled out.'),
   ('vp',        'victory point tokens, four by default. Make a kill — take a point from the victim.'),
   ('hand',      'cards face down; at the end of your turn, eight at most.'),
   ('deck',      'the shared deck in the middle of the table, face down. When it runs out, the game ends.'),
   ('discard',   'next to the deck, face up. Cards never come back from the discard.'),
   ('attack',    'weapon and modifier are laid on the table towards the target; once resolved they go to the discard.'),
  ],
  'outro': 'A trap is placed face down in front of you with the trap figure on top; poison is marked by a bottle figure on the role card. An aura goes face up in front of you with the banner figure on top; it is not shown in this picture. The top samurai backs his ally’s attack with an intervention — «Shieldbreaker».',
  'caption': 'A table for four: samurai — ninja — samurai — ninja.',
  'note': 'At a big table — eight players — it is convenient to split the deck and the discard pile in two and place them on opposite sides so that everyone can reach: the deck is shuffled, and the order of cards in the discard pile does not matter.',
 },
}
NUM = {k: i + 1 for i, (k, _) in enumerate(TXT['ru']['legend'])}

FS = 27          # кегль подписи в единицах картинки
BH = 38          # высота плашки в одну строку — узкие поля
LH = 29          # шаг строк в многострочной подписи (разделитель строк — «|»)
def lines(text):
    return text.split('|')
def box_w(text):
    return int(max(len(l) for l in lines(text)) * FS * 0.5) + 18    # PT Sans обычный ≈ 0.5 кегля на знак + узкие поля плашки
def box_h(text):
    return BH + (len(lines(text)) - 1) * LH

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def svg(lang):
    t = TXT[lang]
    out = []
    out.append(f'<svg class="table-overlay" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">')
    out.append('<defs><marker id="tf-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker>'
               + ''.join(f'<marker id="tf-arrow-{k}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker>' for k in ('attack', 'def', 'int', 'aura'))
               + '</defs>')
    out.append(f'<g transform="translate({PAD},0)">')   # все координаты — в пикселях фото, холст шире на PAD слева
    for key, cls, a0, a1, _, _, *_ in FLOWS:
        both = ' marker-start="url(#tf-arrow-aura)"' if key == 'aura' else ''   # аура — в обе стороны
        out.append(f'<path class="tf-flow tf-flow-{cls}" d="{arc_path(a0, a1, flow_r(key))}"{both}/>')
    # линии — под плашками
    out.append('<g class="tf-lines">')
    for key, (lx, ly), (tx, ty) in LABELS:
        w = box_w(t[key]); hw, hh = w / 2, box_h(t[key]) / 2
        dx, dy = tx - lx, ty - ly
        # точка выхода линии — на границе плашки
        k = min(hw / abs(dx) if dx else 9e9, hh / abs(dy) if dy else 9e9)
        sx, sy = lx + dx * k, ly + dy * k
        out.append(f'<line x1="{sx:.0f}" y1="{sy:.0f}" x2="{tx}" y2="{ty}"/>')
    out.append('</g>')
    out.append('<g class="tf-labels">')
    for key, (lx, ly), _ in LABELS:
        w = box_w(t[key]); h = box_h(t[key]); ls = lines(t[key])
        x0, y0 = lx - w / 2, ly - h / 2
        out.append(f'<g transform="translate({x0:.0f},{y0:.0f})"><rect width="{w}" height="{h}" rx="8"/>')
        for i, l in enumerate(ls):
            out.append(f'<text class="tf-txt" x="{w/2}" y="{BH/2 + 1 + i*LH}">{esc(l)}</text>')
        out.append('</g>')
    # подписи у стрелок хода — та же плашка, без линии
    for key, _, a0, a1, _, rl, *_ in FLOWS:
      lx, ly = polar((a0 + a1) / 2, rl) if rl else {'defends': DEF_LABEL, 'aura': AURA_LABEL}[key]
      w = box_w(t[key]); h = box_h(t[key])
      out.append(f'<g transform="translate({lx - w/2:.0f},{ly - h/2:.0f})"><rect width="{w}" height="{h}" rx="8"/><text class="tf-txt" x="{w/2}" y="{BH/2 + 1}">{esc(t[key])}</text></g>')
    out.append('</g>')
    out.append('<g class="tf-tags">')
    for key, (cx, cy) in TAGS:
        txt = t[key]; w = box_w(txt)
        out.append(f'<g transform="translate({cx - w/2:.0f},{cy - BH/2:.0f})">'
                   f'<rect width="{w}" height="{BH}" rx="23"/>'
                   f'<text x="{w/2}" y="{BH/2 + 1}">{esc(txt)}</text></g>')
    out.append('</g>')
    out.append('</g></svg>')
    return ''.join(out)

def section(lang):
    t = TXT[lang]
    icons = ''.join(f'<i class="ic tf-icon" data-b="{k}" style="left:{(x + PAD)/W*100:.2f}%;top:{y/H*100:.2f}%"></i>'
                    for k, (x, y) in flow_icons())   # значки типов на серединах дуг — поверх SVG
    return (f'\n      <h4>{esc(t["h4"])}</h4>\n'
            f'      <p>{esc(t["intro"])}</p>\n'
            f'      <figure class="table-figure">\n'
            f'        <div class="table-pic"><img src="media/table.webp" alt="" width="{W}" height="{H}">{svg(lang)}{icons}</div>\n'
            f'        <figcaption>{esc(t["caption"])}</figcaption>\n'
            f'      </figure>\n'
            f'      <aside class="note">{esc(t["note"])}</aside>\n')   # outro (про фигурки) не печатается: это уже сказано в главах о ловушке, яде и ауре

if __name__ == '__main__':
    print(section('ru'))
