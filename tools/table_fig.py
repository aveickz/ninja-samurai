# -*- coding: utf-8 -*-
"""Раздел «Стол во время партии» для rules-new*.html (импорт из build-rules-new.py):
картинка стола + SVG-слой со стрелками и подписями + легенда.
Координаты — в пикселях исходной картинки 1200×1173, общие для обоих языков."""
import os, re, math, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

W, H = 1192, 1165
# Картинка стола — rules/media/table.webp (скриншот стола, белый фон вырезан
# в прозрачность); координаты ниже — в её пикселях.

# (ключ, центр подписи (x,y), цель стрелки (x,y))
LABELS = [
    ('stance',    (170,  80), (540, 296)),
    ('role',      (170, 160), (592, 300)),
    ('deck',      (170, 240), (583, 540)),
    ('character', (170, 330), (356, 560)),
    ('hand',      (1030, 80), (742, 296)),
    ('discard',   (1030,160), (658, 540)),
    ('effect',    (1030,240), (884, 556)),
    ('life',      (180, 900), (576, 806)),
    ('vp',        (1010,900), (662, 812)),
    ('attack',    (965, 990), (722, 722)),
]
# фракционные метки у фигур: (текст-ключ, центр)
TAGS = [('samurai', (860, 150)), ('ninja', (1080, 395)), ('samurai', (760, 1060)), ('ninja', (140, 400))]

TXT = {
 'ru': {
  'stance': 'Стойка', 'role': 'Карта роли', 'deck': 'Колода', 'character': 'Персонаж',
  'hand': 'Рука', 'discard': 'Сброс', 'effect': 'Эффекты', 'life': 'Жизни',
  'vp': 'Победные очки', 'attack': 'Атака: оружие + модификатор',
  'samurai': 'Самурай', 'ninja': 'Ниндзя',
  'h4': 'Стол во время партии',
  'intro': 'Так выглядит стол в середине партии на четверых: у каждого игрока перед собой своя зона, посреди стола — общие стопки. Игроки сидят через одного, поэтому напротив — союзник, а по бокам — противники.',
  'legend': [
   ('character', 'карта персонажа лежит перед игроком в открытую всю партию; цифра в сердце — стартовые жизни.'),
   ('role',      'Самурай, Ниндзя или Сёгун — рядом с персонажем, тоже в открытую.'),
   ('stance',    'перед собой в открытую, не больше одной; новая заменяет старую.'),
   ('effect',    'справа от персонажа, в открытую. Сюда же ложатся эффекты, наложенные на вас другими игроками.'),
   ('life',      'жетоны-сердца по цифре на карте персонажа. Опустились до нуля — вы обескровлены.'),
   ('vp',        'жетоны победных очков, по умолчанию четыре. Убили — забрали очко у жертвы.'),
   ('hand',      'карты рубашкой вверх, в конце хода на руке не больше восьми.'),
   ('deck',      'общая колода посреди стола, рубашкой вверх. Кончилась — партия заканчивается.'),
   ('discard',   'рядом с колодой, картинкой вверх. Из сброса карты не возвращаются.'),
   ('attack',    'оружие и модификатор выкладываются на стол в сторону цели, после расчёта уходят в сброс.'),
  ],
  'outro': 'Ловушка кладётся перед собой рубашкой вверх с фигуркой на ней, аура — перед собой в открытую; на этой картинке их нет.',
  'caption': 'Стол на четверых: самурай — ниндзя — самурай — ниндзя.',
 },
 'en': {
  'stance': 'Stance', 'role': 'Role card', 'deck': 'Deck', 'character': 'Character',
  'hand': 'Hand', 'discard': 'Discard', 'effect': 'Effects', 'life': 'Life',
  'vp': 'Victory points', 'attack': 'Attack: weapon + modifier',
  'samurai': 'Samurai', 'ninja': 'Ninja',
  'h4': 'The table during play',
  'intro': 'This is what a four-player table looks like mid-game: every player has their own area in front of them, and the shared piles sit in the middle. Seats alternate, so the player opposite is your ally and the players on either side are enemies.',
  'legend': [
   ('character', 'the character card lies face up in front of the player for the whole game; the number in the heart is the starting life.'),
   ('role',      'Samurai, Ninja or Shogun — next to the character, also face up.'),
   ('stance',    'face up in front of you, one at most; a new one replaces the old.'),
   ('effect',    'to the right of the character, face up. Effects other players put on you go here too.'),
   ('life',      'heart tokens matching the number on the character card. Down to zero — you have bled out.'),
   ('vp',        'victory point tokens, four by default. Make a kill — take a point from the victim.'),
   ('hand',      'cards face down; at the end of your turn, eight at most.'),
   ('deck',      'the shared deck in the middle of the table, face down. When it runs out, the game ends.'),
   ('discard',   'next to the deck, face up. Cards never come back from the discard.'),
   ('attack',    'weapon and modifier are laid on the table towards the target; once resolved they go to the discard.'),
  ],
  'outro': 'A trap is placed face down in front of you with the figure on top; an aura goes face up in front of you. Neither is shown in this picture.',
  'caption': 'A table for four: samurai — ninja — samurai — ninja.',
 },
}
NUM = {k: i + 1 for i, (k, _) in enumerate(TXT['ru']['legend'])}

FS = 27          # кегль подписи в единицах картинки
BH = 46          # высота плашки
def box_w(text):
    return int(len(text) * FS * 0.50) + 78   # узкий шрифт + кружок с номером

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def svg(lang):
    t = TXT[lang]
    out = []
    out.append(f'<svg class="table-overlay" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">')
    out.append('<defs><marker id="tf-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker></defs>')
    # линии — под плашками
    out.append('<g class="tf-lines">')
    for key, (lx, ly), (tx, ty) in LABELS:
        w = box_w(t[key]); hw, hh = w / 2, BH / 2
        dx, dy = tx - lx, ty - ly
        # точка выхода линии — на границе плашки
        k = min(hw / abs(dx) if dx else 9e9, hh / abs(dy) if dy else 9e9)
        sx, sy = lx + dx * k, ly + dy * k
        out.append(f'<line x1="{sx:.0f}" y1="{sy:.0f}" x2="{tx}" y2="{ty}"/>')
    out.append('</g>')
    out.append('<g class="tf-labels">')
    for key, (lx, ly), _ in LABELS:
        w = box_w(t[key]); x0, y0 = lx - w / 2, ly - BH / 2
        out.append(f'<g transform="translate({x0:.0f},{y0:.0f})">'
                   f'<rect width="{w}" height="{BH}" rx="8"/>'
                   f'<circle class="tf-num" cx="{BH/2}" cy="{BH/2}" r="16"/>'
                   f'<text class="tf-numtxt" x="{BH/2}" y="{BH/2 + 1}">{NUM[key]}</text>'
                   f'<text class="tf-txt" x="{BH + 6}" y="{BH/2 + 1}">{esc(t[key])}</text></g>')
    out.append('</g>')
    out.append('<g class="tf-tags">')
    for key, (cx, cy) in TAGS:
        txt = t[key]; w = int(len(txt) * FS * 0.50) + 30
        out.append(f'<g transform="translate({cx - w/2:.0f},{cy - BH/2:.0f})">'
                   f'<rect width="{w}" height="{BH}" rx="23"/>'
                   f'<text x="{w/2}" y="{BH/2 + 1}">{esc(txt)}</text></g>')
    out.append('</g>')
    out.append('</svg>')
    return ''.join(out)

def section(lang):
    t = TXT[lang]
    items = ''.join(f'<li><b>{esc(t[k])}</b> — {esc(d)}</li>' for k, d in t['legend'])
    return (f'\n      <h4>{esc(t["h4"])}</h4>\n'
            f'      <p>{esc(t["intro"])}</p>\n'
            f'      <figure class="table-figure">\n'
            f'        <div class="table-pic"><img src="media/table.webp" alt="" width="{W}" height="{H}">{svg(lang)}</div>\n'
            f'        <figcaption>{esc(t["caption"])}</figcaption>\n'
            f'      </figure>\n'
            f'      <ol class="table-legend">{items}</ol>\n'
            f'      <p class="table-note">{esc(t["outro"])}</p>\n')

if __name__ == '__main__':
    print(section('ru'))
