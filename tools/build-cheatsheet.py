# -*- coding: utf-8 -*-
"""Запуск: py -3 tools/build-cheatsheet.py

Собирает памятку-схему на A5 landscape: rules/cheatsheet.html (RU, оригинал)
и rules/cheatsheet-en.html (EN, перевод). Прежняя трёхколоночная памятка —
в rules/obsolete/cheatsheet-columns*.html.

Компоновка — по эскизу автора. Три полосы: вверху заголовок и цепочка
порядка расчёта; посередине атака и защита (оружие с модификатором и карта
защиты по центру, подписи по бокам); внизу — стол игрока, как он лежит
перед ним: рука веером в левом нижнем углу, сердца столбиком, персонаж с
бутылкой яда и роль, над ними ловушка; стойка с аурой над ней; два эффекта
внахлёст; мелочи столбиком в правом нижнем углу. Карты — превью из
rules/media/cards/ (для EN — *-en.webp), фигурки из rules/media/fig/,
жетоны из media/. У предметов ничего не рисуется: подпись со значком
просто стоит рядом.

Оформление — по макету ref/cheatsheet-mockup-2026-09-16.png (/img по нашей
раскладке): фон rules/media/cheat-bg.webp — васи с тушевыми украшениями,
разделённый широким кистевым штрихом на две зоны: верхняя — война
(красное небо, катаны с кабуто, знамёна, конница, стрелы, горящий замок:
полоса действий — вмешательство под веткой сливы слева, атака по центру,
защита справа), нижняя — мир (серо-зелёные горы, бамбук, сосна с пагодой:
стол игрока). Штрих идёт от ~61 мм слева до ~52 мм справа, всё содержимое
стола лежит ниже него. Орнаменты обеих зон выцвечены примерно до 35 %,
чтобы текст читался; штрих-граница — в полную силу. Прежние фоны —
media/obsolete/cheat-bg-v1.webp (без зон), v2-zones (мирный верх),
v3-war (война в полную силу), v4-war-55 (та же война, выцветание ~55 %).
Заголовки выносок на кистевом мазке rules/media/fig/brush-plate.webp,
значки — чёрные круги с белым знаком, под текстом мягкое бумажное свечение.

Все координаты — в миллиметрах листа (210 × 148). Геометрия общая для
языков, тексты — в TXT. Правится здесь, HTML руками не трогать."""
import os, sys, math, re
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

W, H = 210, 148            # базовая геометрия — A5 landscape; A6 — та же раскладка в масштабе K
CW, CH = 17, 27.2          # карта 5:8
FORMATS = {
 # k — масштаб геометрии; fs — кегль текста выносок (на A6 не масштабируем, иначе нечитаемо);
 # co — какой набор текстов: 'co' (полный) или 'co6' (короткий, под A6)
 'a5': dict(w=210, h=148, k=1.0,   fs='6.9pt', h4='7.4pt', ic='3.4mm', h4ic='4mm', chain_fs='6pt', chain_w='7.9mm', chain_ic='3.6mm', page='A5 landscape', co='co',  suffix='',
            lh='1.25', h4pad='.7mm 3mm .7mm 1.2mm', h4mb='.6mm'),
 'a6': dict(w=148, h=105, k=0.705, fs='5.4pt', h4='5.8pt', ic='2.6mm', h4ic='3mm', chain_fs='4.6pt', chain_w='5.9mm', chain_ic='2.6mm', page='A6 landscape', co='co6', suffix='-a6',
            lh='1.2', h4pad='.5mm 2.4mm .5mm 1mm', h4mb='.4mm'),
}

# ---------- предметы: key -> dict(x, y, w, h, rot, cid|src, cls) ----------
OBJ = {}
def card(key, x, y, cid, rot=0, w=CW, h=CH, cls='card'):
    OBJ[key] = dict(x=x, y=y, w=w, h=h, rot=rot, cid=cid, cls=cls)
def lcard(key, x, y, cid):
    """Карта, лежащая боком: видимый прямоугольник (x, y, CH, CW)."""
    cx, cy = x + CH / 2, y + CW / 2
    card(key, cx - CW / 2, cy - CH / 2, cid, rot=90)
def fig(key, x, y, w, h, src, rot=0, cls='fig'):
    OBJ[key] = dict(x=x, y=y, w=w, h=h, rot=rot, src=src, cls=cls)

# --- рука: левый нижний угол, веер с сильным наклоном, подпись под ним ---
for i in range(5):
    fig(f'hand{i}', 6 + i * 5.4, 97 + (i - 2) ** 2 * .8, 14, 22.4, 'media/cards/back.webp', rot=-38 + i * 8, cls='card hand')

# --- атака и защита: полоса под заголовком; подписи атаки и вмешательства — над картами ---
card('interv',   36, 20, 124, rot=-8)              # Удар дракона — вмешательство, под веткой сливы слева
card('weapon',   92, 17, 1)                        # Катана
card('modifier', 107, 24, 70)                      # Гнев сёгуна — внахлёст
card('defense',  134, 21, 48)                      # Защита

# --- зона игрока: низ по центру ---
for i in range(4):
    fig(f'hp{i}', 57.5, 95.5 + i * 5.2, 4.6, 4.6, '../media/hp.png', cls='tok')
card('char', 65, 95, 137)                          # Сайго
card('role', 84, 95, 201)                          # Самурай
fig('poison', 89.5, 105, 6.1, 8, 'media/fig/poison.webp')   # бутылка яда — на карте роли
for i in range(4):
    fig(f'vp{i}', 64.5 + i * 5.2, 124.5, 4.6, 4.6, '../media/winpoint.png', cls='tok')
lcard('trapcard', 69, 75, 'back')                  # ловушка — рубашкой вверх, над персонажем
fig('trap', 77, 78, 11, 11, 'media/fig/trap.webp')
card('stance', 106, 97, 1166)                     # Лучник
card('aura',   106, 62, 1204)                      # Спина к спине — над стойкой
fig('banner', 116.5, 76.5, 6.6, 11.2, 'media/fig/banner.webp')   # знамя ауры — на карте ауры, как бутылка на роли
card('effect0', 128.5, 90, 91)                     # Метка убийцы
card('effect1', 142, 93.5, 97)                     # Пыль в глаза — внахлёст

# ---------- выноски: геометрия общая, тексты по языкам ----------
# (цели, плашка (x, y, w), сторона (осталась для точки яда), значок, ключ текста)
CALL = [
 (['weapon','modifier'], (92, 2, 34), 'top', 'weapon', 'attack'),           # над оружием, по его ширине
 (['interv'], (5, 12, 30), 'left', 'intervention', 'interv'),                # слева от «Удара дракона», под веткой
 (['defense'], (154, 18, 51), 'right', 'defense', 'defense'),
 (['trapcard','trap'], (58, 55, 44), 'top', 'trap', 'trap'),
 (['aura','banner'], (125, 63, 40), 'right', 'aura', 'aura'),
 (['effect0','effect1'], (162, 91, 43), 'right', 'effect', 'effects'),       # справа от стопки эффектов
 (['hp0','hp1','hp2','hp3','char','role'], (5, 70, 51), 'left', 'hp', 'char'),
 (['hand0','hand1','hand2','hand3','hand4'], (5, 124, 48), 'bottom', 'card', 'hand'),
 (['vp0','vp1','vp2','vp3'], (56, 130, 27), 'bottom', 'winpoint', 'vp'),    # под очками, по ширине персонажа
 (['poison'], (84, 130, 21), 'bottom', 'poison', 'poison'),                  # под ролью, по её ширине
 (['stance'], (106, 127, 22), 'bottom', 'stance', 'stance'),                 # под стойкой
]
CHAIN_KEYS = ['character', 'stance', 'aura', 'poison', 'effect', 'weapon', 'modifier']
STRIP_ICONS = []   # столбик мелочей убран по решению автора

TXT = {
 'ru': dict(
  out='rules/cheatsheet.html', lang='ru',
  title='Последний самурай — памятка A5', ttl='Последний самурай',
  note='Памятка на стол · A5 горизонтально · <a href="rules.html">правила</a> · <a href="../app.html">картотека</a>',
  switch='<span class="lang-switch-current">RU</span><a href="cheatsheet-en.html">EN</a>',
  zone_act='行動', zone_tbl='陣',   # действие · позиция
  chain_title='Порядок расчёта',
  chain=['персонаж', 'стойка', 'аура', 'яд', 'эффект', 'оружие', 'модификатор'],
  strip=[
   ('Вмешательство', 'играется не в свой ход; всё сыгранное — одновременно, порядок выбирает тот, чья жизнь на кону.'),
   ('Выпад', 'раны напрямую: не атака, без защиты и ловушки, не тратит атаку.'),
   ('Порядок', 'у защищающегося то же, последней — ловушка; «не менее 1» — с места, где встретился.'),
   ('Конец партии', 'колода кончилась · чьи-то 0 очков · по договорённости, доиграв раунд до игрока перед начинающим.'),
  ],
  co={
   'hand':    ('Рука', 'Старт — <b>7</b>. В начале хода не больше <b>9</b>, лишнее в сброс. В конце хода набор <b>3</b> <i>(меньшая команда +1)</i>, затем каждый противник берёт <b>1</b>. Между ходами не ограничена.'),
   'attack':  ('Атака', 'До <b>2</b> за ход. Оружие берёт цель, если его сложность ≥ сложности цели (обычно 1); метательное — любую. Один модификатор.'),
   'interv':  ('Вмешательство', 'Не в свой ход: «Удар дракона» добивает на <b>1</b>. Всё сыгранное — одновременно, порядок выбирает тот, чья жизнь на кону.'),
   'defense': ('Защита', 'Своя — атака отбита, бонусы атакующего не срабатывают. Союзная, как вмешательство: одна — раны до <b>1</b>, две от команды — до <b>0</b>. Беззащитного не спасти.'),
   'trap':    ('Ловушка', 'Одна, рубашкой вверх, фигурка сверху. Срабатывает, если атакуют и вы не защищаетесь; метательное её не будит. Подложили не ловушку — умираете.'),
   'aura':    ('Аура', 'Над стойкой, одна на игрока, сверху — знамя. Действует на всех за столом; у команды складываются. Новая — прежняя в руку.'),
   'effects': ('Эффекты', 'Справа, в открытую, сколько угодно. Постоянные — до смерти, разовые — до срабатывания. Одноимённые не повторяются. Только на живых.'),
   'stance':  ('Стойка', 'Раз за ход, одна, работает сразу. Новая — прежняя в руку.'),
   'char':    ('Персонаж и роль', 'Жизни — цифра в сердце, это же максимум для <i>полного здоровья</i>. Роль рядом: Самурай или Ниндзя. <b>0</b> жизней — мертвы до конца хода: очко убийце, открытые карты в сброс, вас никто не трогает. Со следующего хода живы; в свой ход — восстановление: сброс любых карт, добор до <b>7</b>.'),
   'poison':  ('Яд', 'В конце хода <b>−2</b>; отравленная атака по вам <b>+1</b>. Смерть от яда — без восстановления.'),
   'life':    ('Жизни', '<b>0</b> — мертвы до конца хода: очко убийце, открытые карты в сброс, вас никто не трогает. Со следующего хода живы; в свой ход — восстановление: сброс любых карт, добор до <b>7</b>.'),
   'vp':      ('Очки', 'Старт — <b>4</b>. Убили — очко у жертвы. Чьи-то <b>0</b> — конец партии.'),
  },
  co6={
   'hand':    ('Рука', 'Старт <b>7</b>. В начале хода ≤ <b>9</b>. В конце — набор <b>3</b>, противники по <b>1</b>.'),
   'attack':  ('Атака', 'До <b>2</b> за ход. Сложность оружия ≥ сложности цели (обычно 1). Один модификатор.'),
   'interv':  ('Вмешательство', 'Не в свой ход. Всё сыгранное — одновременно; порядок — у того, чья жизнь на кону.'),
   'defense': ('Защита', 'Своя — атака отбита. Союзная: одна — раны до <b>1</b>, две — до <b>0</b>. Беззащитного не спасти.'),
   'trap':    ('Ловушка', 'Одна, рубашкой вверх, фигурка сверху. Срабатывает, если не защищаетесь; метательное не будит.'),
   'aura':    ('Аура', 'Одна на игрока, сверху — знамя. Действует на всех. Новая — прежняя в руку.'),
   'effects': ('Эффекты', 'В открытую, сколько угодно; одноимённые не повторяются. Только на живых.'),
   'stance':  ('Стойка', 'Раз за ход, одна. Новая — прежняя в руку.'),
   'char':    ('Персонаж и роль', 'Жизни — цифра в сердце. <b>0</b> — мертвы до конца хода: очко убийце, открытые карты в сброс. В свой ход — восстановление до <b>7</b>.'),
   'poison':  ('Яд', 'В конце хода <b>−2</b>; атака ядом <b>+1</b>. Смерть — без восстановления.'),
   'vp':      ('Очки', 'Старт <b>4</b>. Убили — очко у жертвы. Чьи-то <b>0</b> — конец.'),
  }),
 'en': dict(
  out='rules/cheatsheet-en.html', lang='en',
  title='The Last Samurai — A5 cheat sheet', ttl='The Last Samurai',
  note='Table cheat sheet · A5 landscape · <a href="rules-en.html">rules</a> · <a href="../app.html?lang=en">card catalogue</a>',
  switch='<a href="cheatsheet.html">RU</a><span class="lang-switch-current">EN</span>',
  zone_act='行動', zone_tbl='陣',
  chain_title='Order of resolution',
  chain=['character', 'stance', 'aura', 'poison', 'effect', 'weapon', 'modifier'],
  strip=[
   ('Intervention', 'played outside your turn; everything played counts as simultaneous, the order is picked by whoever\'s life is at stake.'),
   ('Thrust', 'wounds directly: not an attack, no defense or trap, does not spend an attack.'),
   ('Order', 'the defender\'s chain is the same, ending with the trap; a «no less than 1» floor holds from where it appears.'),
   ('End of the game', 'the deck runs out · someone has 0 points · by agreement, after finishing the round up to the player before the one who starts.'),
  ],
  co={
   'hand':    ('Hand', 'Start — <b>7</b>. At the start of your turn no more than <b>9</b>, discard the rest. At the end of your turn draw <b>3</b> <i>(smaller team +1)</i>, then every opponent draws <b>1</b>. Unlimited between turns.'),
   'attack':  ('Attack', 'Up to <b>2</b> per turn. A weapon reaches the target if its complexity ≥ the target\'s (usually 1); thrown — anyone. One modifier. Fists — 1/1 for both attacks.'),
   'interv':  ('Intervention', 'Outside your turn: «Dragon Strike» finishes a wounded player for <b>1</b>. Everything played is simultaneous; the order is picked by whoever\'s life is at stake.'),
   'defense': ('Defense', 'Your own — attack blocked, attacker\'s bonuses do not fire. An ally\'s, as an intervention: one card — wounds down to <b>1</b>, two from the team — to <b>0</b>. The defenceless cannot be saved.'),
   'trap':    ('Trap', 'One, face down, figure on top. Fires when you are attacked and do not defend; thrown weapons do not wake it. Planted something else — you die.'),
   'aura':    ('Aura', 'Above the stance, one per player, banner on top. Affects everyone at the table; a team\'s auras stack. New one — the old returns to hand.'),
   'effects': ('Effects', 'To the right, face up, any number. Permanent — until death, one-shot — until they fire. No two of the same name. Living players only.'),
   'stance':  ('Stance', 'Once per turn, one. Works right away. New one — the old returns to hand.'),
   'char':    ('Character and role', 'Life — the number in the heart, also the maximum for <i>full health</i>. Role next to it: Samurai or Ninja. <b>0</b> life — dead until the end of the turn: point to the killer, face-up cards discarded, nobody touches you. Alive from the next turn; on your own turn — recovery: discard any cards, draw back up to <b>7</b>.'),
   'poison':  ('Poison', 'End of turn <b>−2</b>; poisoned attack on you <b>+1</b>. Death by poison — no recovery.'),
   'life':    ('Life', '<b>0</b> — dead until the end of the turn: point to the killer, face-up cards discarded, nobody touches you. Alive from the next turn; on your own turn — recovery: discard any cards, draw back up to <b>7</b>.'),
   'vp':      ('Points', 'Start — <b>4</b>. A kill takes one from the victim. Anyone at <b>0</b> — game over.'),
  },
  co6={
   'hand':    ('Hand', 'Start <b>7</b>. Start of turn ≤ <b>9</b>. End of turn draw <b>3</b>, opponents <b>1</b> each.'),
   'attack':  ('Attack', 'Up to <b>2</b> per turn. Weapon complexity ≥ target complexity (usually 1). One modifier.'),
   'interv':  ('Intervention', 'Outside your turn. All played at once; order picked by whoever is at stake.'),
   'defense': ('Defense', 'Own — attack blocked. Ally: one — wounds to <b>1</b>, two — to <b>0</b>. Defenceless can\'t be saved.'),
   'trap':    ('Trap', 'One, face down, figure on top. Fires if you do not defend; thrown weapons do not wake it.'),
   'aura':    ('Aura', 'One per player, banner on top. Affects everyone. New one — old returns to hand.'),
   'effects': ('Effects', 'Face up, any number; no duplicates by name. Living players only.'),
   'stance':  ('Stance', 'Once per turn, one. New one — old returns to hand.'),
   'char':    ('Character and role', 'Life — the number in the heart. <b>0</b> — dead until end of turn: point to killer, face-up cards discarded. On your turn — recovery to <b>7</b>.'),
   'poison':  ('Poison', 'End of turn <b>−2</b>; poison attack <b>+1</b>. Death — no recovery.'),
   'vp':      ('Points', 'Start <b>4</b>. A kill takes one. Anyone at <b>0</b> — game over.'),
  }),
}

def ic(key):
    if key in ('winpoint', 'card'):
        src = '../media/winpoint.png' if key == 'winpoint' else 'media/cards/back.webp'
        return f'<img class="mk" src="{src}" alt="">'
    return f'<i class="ic" data-b="{key}"></i>'

def obj_src(o, lang):
    if 'src' in o:
        return o['src']
    cid = o['cid']
    suffix = '-en' if (lang == 'en' and cid != 'back') else ''
    return f'media/cards/{cid}{suffix}.webp'

def objects_html(lang, K=1.0):
    out = []
    for k, o in OBJ.items():
        st = f"left:{o['x']*K:.2f}mm;top:{o['y']*K:.2f}mm;width:{o['w']*K:.2f}mm;height:{o['h']*K:.2f}mm;"
        if o['rot']:
            st += f"transform:rotate({o['rot']}deg);"
        out.append(f'<img class="{o["cls"]}" data-k="{k}" src="{obj_src(o, lang)}" alt="" style="{st}">')
    return '\n'.join(out)

BOTTOM_LIFT = {'a5': 0, 'a6': 2.5}   # мм: подписи нижнего ряда (side='bottom') на A6 чуть выше
def callouts_html(t, K=1.0, coset='co', fmt='a5'):
    out = []
    for keys, (x, y, w), side, icon, tid in CALL:
        title, text = t[coset][tid]
        yy = y * K - (BOTTOM_LIFT[fmt] if side == 'bottom' else 0)
        out.append(f'<div class="co co-{side}" style="left:{x*K:.2f}mm;top:{yy:.2f}mm;width:{w*K:.2f}mm"><h4>{ic(icon)}{title}</h4><p>{text}</p></div>')
    return '\n'.join(out)

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

# ---------- две зоны: полоса действий (верх) и стол игрока (низ) ----------
# Граница — кистевой штрих, в мм листа A5; чуть поднимается вправо, как на макете.
ZONE_Y0, ZONE_Y1 = 60, 55      # высота границы у левого и правого края
ZONE_WASH = False              # подкраска и штрих рисуются CSS только если фон без зон; cheat-bg.webp уже с ними

def zones_html(t, K=1.0):
    """SVG под предметами: мягкие подкраски двух зон и рваная кистевая граница между ними."""
    y0, y1 = ZONE_Y0, ZONE_Y1
    # рваная кромка штриха: ломаная с мелким «дрожанием»
    import random
    rnd = random.Random(7)
    n = 40
    top, bot = [], []
    for i in range(n + 1):
        x = W * i / n
        y = y0 + (y1 - y0) * i / n
        top.append((x, y - 1.1 + rnd.uniform(-.5, .5)))
        bot.append((x, y + 1.1 + rnd.uniform(-.5, .5)))
    brush = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in top) + ' L' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in reversed(bot)) + ' Z'
    wash = ''
    if ZONE_WASH:
        wash = (f'<path class="z-act" d="M0,0 H{W} V{y1} L0,{y0} Z"/>'
                f'<path class="z-tbl" d="M0,{y0} L{W},{y1} V{H} H0 Z"/>')
    return (f'<svg class="zones" viewBox="0 0 {W} {H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
            '<defs><filter id="zink" x="-2%" y="-20%" width="104%" height="140%">'
            '<feTurbulence type="fractalNoise" baseFrequency=".9 .35" numOctaves="2" seed="3" result="n"/>'
            '<feDisplacementMap in="SourceGraphic" in2="n" scale="1.2" xChannelSelector="R" yChannelSelector="G"/></filter></defs>'
            + wash + (f'<path class="z-brush" d="{brush}" filter="url(#zink)"/>' if ZONE_WASH else '') + '</svg>'
            f'<div class="z-lbl z-lbl-act">{t["zone_act"]}</div><div class="z-lbl z-lbl-tbl">{t["zone_tbl"]}</div>')

def svg_html():
    """Слой поверх стола: только точка на бутылке яда (скобки и штрихи убраны)."""
    dots = []
    for keys, box, side, _i, _t in CALL:
        if side == 'dot':
            x0, y0, x1, y1 = bbox(keys)
            dots.append(f'<circle class="pin" cx="{(x0+x1)/2:.1f}" cy="{(y0+y1)/2:.1f}" r="1.1"/>')
    return (f'<svg class="ov" viewBox="0 0 {W} {H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg"><g>' + ''.join(dots) + '</g></svg>')

def chain_html(t):
    chain = ''.join(f'<span class="s"><i class="ic" data-b="{k}"></i>{lbl}</span><span class="arr">→</span>' for k, lbl in zip(CHAIN_KEYS, t['chain']))
    chain = chain[:-len('<span class="arr">→</span>')]
    return f'<div class="chain"><b>{t["chain_title"]}</b>{chain}</div>'

def misc_html(t):
    if not STRIP_ICONS:
        return ''
    items = ''.join(f'<p><i class="ic" data-b="{k}"></i><b>{title}</b> — {d}</p>' for k, (title, d) in zip(STRIP_ICONS, t['strip']))
    return f'<div class="misc">{items}</div>'

CSS = r"""
  @font-face { font-family: 'Han Zi Web'; src: url('fonts/Han-Zi_Regular.woff') format('woff'); font-display: swap; }
  :root {
    --paper-light:#f4ead2; --paper-deep:#c4a86a; --ink:#1c1410; --ink-soft:#3a2a1d; --ink-faded:#6a4a30;
    --vermilion:#b1281d; --vermilion-dk:#7a1410; --gold:#8b6a2a;
    --fs: {{fs}}; --ic: {{ic}};
  }
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; background: radial-gradient(ellipse at top, #2a1a10 0%, #150a05 70%), #0a0503;
    color: var(--ink); font-family: 'PT Sans Narrow', 'PT Sans', Arial, sans-serif; min-height:100vh; }
  .desk { min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:24px 16px 40px; gap:14px; }
  .desk-note { color:#b39a6f; font-size:14px; letter-spacing:.04em; opacity:.8; }
  .desk-note a { color:#d8c39a; }
  .lang-switch { margin:0; letter-spacing:.14em; line-height:1; }
  .lang-switch a, .lang-switch .lang-switch-current { display:inline-block; padding:3px 9px; font-size:13px; font-weight:700; border:1px solid #8a6a44; text-decoration:none; }
  .lang-switch a { color:#b39a6f; }
  .lang-switch a:hover { color:#f2e6cf; background:#8a6a44; }
  .lang-switch .lang-switch-current { color:#f2e6cf; background:#6b4a28; border-color:#6b4a28; cursor:default; }
  .lang-switch a + .lang-switch-current, .lang-switch .lang-switch-current + a { border-left:0; }

  /* Лист: сгенерированный фон — бумага васи с тушевыми украшениями по краям */
  .sheet { position:relative; width:{{w}}mm; height:{{h}}mm; overflow:hidden; font-size:var(--fs); line-height:{{lh}};
    background: url('media/cheat-bg.webp') center / 100% 100% no-repeat var(--paper-light);
    box-shadow: 0 0 0 1px rgba(60,30,10,.4), 0 20px 50px rgba(0,0,0,.65); }

  /* заголовок — верхний левый угол, как заголовок главы */
  .ttl { position:absolute; left:calc(5mm * {{k}}); top:calc(3mm * {{k}}); max-width:calc(48mm * {{k}}); white-space:nowrap; display:flex; align-items:center; gap:2mm;
    font-family:'Han Zi Web','Shippori Mincho',serif; font-size:calc(7.6pt * {{k}} + 1.2pt); text-transform:uppercase; letter-spacing:.04em; color:var(--ink); line-height:1; }
  .ttl .kanji { font-family:'Shippori Mincho','Noto Serif JP','Yu Mincho',serif; font-size:9pt; color:rgba(122,20,16,.45); text-transform:none; letter-spacing:.06em; }
  .ttl .kanji::before { content:"·"; font-family:'PT Sans Narrow',sans-serif; font-size:8pt; color:rgba(70,58,50,.28); margin-right:2mm; }

  /* предметы */
  .card { position:absolute; display:block; border-radius:.9mm; box-shadow:0 .5mm 1.2mm rgba(40,20,5,.35); outline:.32mm solid #fff; }
  .card.hand { outline-width:.28mm; box-shadow:0 .4mm 1mm rgba(40,20,5,.35); }
  .fig { position:absolute; display:block; filter: drop-shadow(0 .5mm .6mm rgba(0,0,0,.45)); }
  .tok { position:absolute; display:block; filter: drop-shadow(0 .3mm .4mm rgba(0,0,0,.35)); }

  .ov { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
  .ov .pin { fill:var(--vermilion); opacity:.9; }

  /* две зоны: подкраска и кистевая граница — под предметами */
  .zones { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
  .zones .z-act { fill:rgba(177,40,29,.075); }
  .zones .z-tbl { fill:rgba(60,110,70,.085); }
  .zones .z-brush { fill:var(--ink-soft); opacity:.72; }
  /* подписи зон — бледные иероглифы у правого края, как водяные знаки */
  .z-lbl { position:absolute; right:calc(5mm * {{k}}); font-family:'Shippori Mincho','Noto Serif JP','Yu Mincho',serif; font-size:calc(13pt * {{k}} + 2pt);
    letter-spacing:.12em; color:rgba(122,20,16,.32); user-select:none; pointer-events:none; line-height:1; }
  .z-lbl-act { top:calc(40mm * {{k}}); }
  .z-lbl-tbl { top:calc(64mm * {{k}}); color:rgba(40,80,50,.38); }

  /* выноски: заголовок на кистевом мазке, значок — чёрный круг с белым знаком */
  .co { position:absolute; isolation:isolate; }
  /* текст на мягком бумажном свечении — орнаменты фона уходят под него */
  .co p, .misc p, .chain, .ttl { background: rgba(244,234,210,.78); box-shadow: 0 0 2.5mm 2.5mm rgba(244,234,210,.78); border-radius: 1mm; }
  .co h4 { position:relative; margin:0 0 {{h4mb}} -1.2mm; padding:{{h4pad}}; font-size:{{h4}}; font-weight:700; color:#f4ead2;
    display:inline-flex; align-items:center; gap:1.6mm; line-height:1.1; }
  .co h4::before { content:""; position:absolute; inset:-.6mm -2mm -.6mm -.8mm; z-index:-1;
    background:url('media/fig/brush-plate.webp') center / 100% 100% no-repeat; opacity:.92; }
  .co h4 .ic { background:#1c1410 !important; box-shadow:0 0 0 .35mm #f4ead2; --ic:{{h4ic}}; }
  .co h4 .ic.raw > img { filter:none; }
  .co h4 .mk { background:#1c1410; border-radius:50%; padding:.5mm; width:{{h4ic}}; height:{{h4ic}}; box-shadow:0 0 0 .35mm #f4ead2; }
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

  /* цепочка порядка расчёта — верхний правый угол, одной строкой */
  .chain { position:absolute; left:calc(133mm * {{k}}); top:calc(125mm * {{k}}); width:calc(72mm * {{k}}); display:flex; flex-wrap:wrap; align-items:flex-start; gap:.3mm; font-size:{{chain_fs}}; color:var(--ink-soft); line-height:1.1; }
  .chain > b { width:100%; font-size:6.8pt; margin-bottom:.8mm; white-space:nowrap; }
  .chain .s { display:inline-flex; flex-direction:column; align-items:center; width:{{chain_w}}; text-align:center; }
  .chain .s .ic { --ic:{{chain_ic}}; margin-bottom:.3mm; }
  .chain .arr { color:rgba(70,58,50,.35); font-size:5.5pt; margin:1mm -.6mm 0; }

  /* мелочи — правый нижний угол */
  .misc { position:absolute; left:162mm; top:100mm; width:43mm; font-size:6.3pt; line-height:1.2; }
  .misc p { margin:0 0 .7mm; color:var(--ink); }
  .misc p .ic { --ic:2.9mm; margin-right:.9mm; vertical-align:-.7mm; }
  .misc p b { color:var(--ink-soft); }

  @page { size: {{page}}; margin:0; }
  @media print {
    html, body { background:#fff; }
    .desk { min-height:auto; padding:0; gap:0; display:block; }
    .desk-note, .lang-switch { display:none; }
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

def build(lang, fmt='a5'):
    t = TXT[lang]; F = FORMATS[fmt]
    css = CSS
    for key, val in F.items():
        css = css.replace('{{' + key + '}}', str(val))
    out = t['out'].replace('.html', F['suffix'] + '.html')
    switch = t['switch'].replace('.html', F['suffix'] + '.html')
    # ссылка на другой формат — в подписи над листом
    other = 'a6' if fmt == 'a5' else 'a5'
    other_href = t['out'].split('/')[-1].replace('.html', FORMATS[other]['suffix'] + '.html')
    note = t['note'] + f' · <a href="{other_href}">{other.upper()}</a>'
    html = f'''<!DOCTYPE html>
<html lang="{t['lang']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t['title']}</title>
<link rel="icon" type="image/svg+xml" href="../media/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Sans+Narrow:wght@400;700&family=Shippori+Mincho:wght@400&display=swap" rel="stylesheet">
<!-- СОБИРАЕТСЯ tools/build-cheatsheet.py — руками не править. -->
<style>{css}</style>
</head>
<body>
<div class="desk">
  <div class="desk-note">{note}</div>
  <p class="lang-switch">{switch}</p>
  <div class="sheet">
    <div class="ttl">{t['ttl']} <span class="kanji">覚</span></div>
{zones_html(t, F['k'])}
{objects_html(lang, F['k'])}
{svg_html()}
{callouts_html(t, F['k'], F['co'], fmt)}
{chain_html(t)}
{misc_html(t)}
  </div>
</div>
<script>{SCRIPT}</script>
</body>
</html>
'''
    open(out, 'w', encoding='utf-8', newline='\n').write(html)
    print('written', out)

if __name__ == '__main__':
    for fmt in FORMATS:
        build('ru', fmt); build('en', fmt)
