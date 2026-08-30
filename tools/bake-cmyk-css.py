"""
Прогоняем sRGB-палитру нашего приложения через ICC Coated_Fogra39L_VIGC_300
туда и обратно (sRGB → CMYK → sRGB).

Результат — «как реально будет выглядеть после печати на офсете и
возврата в sRGB-монитор для просмотра» — это и есть soft-proof на экране.

Для каждой пары перехода используем intent = PERCEPTUAL: то же,
что обычно используют типографы для художественной печати.
"""
from PIL import Image, ImageCms
import os

ICC_PATH = '/sessions/keen-happy-johnson/mnt/ninja_samurai/app/profiles/Coated_Fogra39L_VIGC_300.icc'
OUT_CSS  = '/sessions/keen-happy-johnson/mnt/ninja_samurai/app/styles/proof-cmyk-baked.css'

# Профили
srgb  = ImageCms.createProfile('sRGB')
cmyk  = ImageCms.ImageCmsProfile(ICC_PATH)

# Двойной transform — туда и обратно
to_cmyk = ImageCms.buildTransform(srgb, cmyk, 'RGB', 'CMYK',
                                  renderingIntent=ImageCms.Intent.PERCEPTUAL)
to_srgb = ImageCms.buildTransform(cmyk, srgb, 'CMYK', 'RGB',
                                  renderingIntent=ImageCms.Intent.PERCEPTUAL)

def proof_color(hex_str):
    """sRGB hex → soft-proof'нутый sRGB hex"""
    h = hex_str.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    # 1×1 pix RGB image
    im = Image.new('RGB', (1, 1), (r, g, b))
    im_cmyk = ImageCms.applyTransform(im, to_cmyk)
    im_back = ImageCms.applyTransform(im_cmyk, to_srgb)
    rr, gg, bb = im_back.getpixel((0, 0))
    return '#{:02x}{:02x}{:02x}'.format(rr, gg, bb)

# Палитра приложения (вытащено из main.css/card.css/comments.css)
palette = [
    ('#1a1208', 'body / near-black background'),
    ('#2a1c0a', 'header gradient stop / panel bg'),
    ('#231a0e', 'filter button bg'),
    ('#231F20', 'card title bar — default'),
    ('#3a2a10', 'thin divider line'),
    ('#5a3e1b', 'paper text accent'),
    ('#6a5030', 'muted text / border'),
    ('#7a5a2a', 'subtitle / labels'),
    ('#a08050', 'tag color / muted'),
    ('#c8860a', 'gold action / active'),
    ('#c8a870', 'stats table text'),
    ('#dca300', 'defense / yellow plate'),
    ('#e8d5a3', 'body text on dark'),
    ('#f0c060', 'highlight gold'),
    # групповые цвета плашек
    ('#ED1C24', 'weapon / modifier red'),
    ('#43525A', 'trap dark blue-grey'),
    ('#5f8598', 'trap tag accent'),
    ('#6C8CC7', 'character blue'),
    ('#A78B6B', 'stance tan'),
    ('#3B8476', 'intervention teal'),
    ('#5d3c75', 'role purple'),
    ('#9c6ec0', 'role tag accent'),
    ('#891511', 'samurai title bg'),
    ('#0D233C', 'ninja title bg'),
    # яркие тэг-фоны/рамки
    ('#7fff7f', 'poison text'),
    ('#0d2e0d', 'poison bg'),
    ('#3a8a3a', 'poison border'),
    ('#a8d4f0', 'print text'),
    ('#0d1e2e', 'print bg'),
    ('#2a5a7a', 'print border'),
    ('#f0d080', 'draft text'),
    ('#2a2000', 'draft bg'),
    ('#7a6000', 'draft border'),
    ('#c0c0c0', 'trash text'),
    ('#1e1e1e', 'trash bg'),
    ('#555555', 'trash border'),
    # commentary палитра
    ('#e8453a', 'unread red dot'),
    ('#d63a3a', 'error red'),
    ('#4caf50', 'success green'),
    # вспомогательные тёплые
    ('#3a2410', 'desc prefix italic'),
    ('#1a1208', 'desc text on paper'),
]
# Уникальные
seen = set()
unique_palette = []
for h, label in palette:
    if h.lower() not in seen:
        seen.add(h.lower())
        unique_palette.append((h, label))

# Подготовим маппинг
print(f"{'sRGB':>8s} → {'proof':>8s}  Δ% notes")
mapping = []
for orig, label in unique_palette:
    proofed = proof_color(orig)
    # Δ для ориентира — сумма абсолютных отклонений по компонентам
    h1 = orig.lstrip('#')
    h2 = proofed.lstrip('#')
    d = sum(abs(int(h1[i:i+2], 16) - int(h2[i:i+2], 16)) for i in (0, 2, 4))
    print(f"  {orig} → {proofed}  Δ={d:3d}  {label}")
    mapping.append((orig, proofed, label))

# Генерируем CSS
lines = []
lines.append('/*')
lines.append('  proof-cmyk-baked.css — soft-proof через РЕАЛЬНУЮ конвертацию')
lines.append('  ICC Coated_Fogra39L_VIGC_300 (Fogra39) туда-обратно:')
lines.append('     sRGB → CMYK (perceptual) → sRGB')
lines.append('  Результат — как цвета выглядят ПОСЛЕ офсетной печати,')
lines.append('  показанные на твоём sRGB-мониторе.')
lines.append('  ')
lines.append('  Этот файл работает в ЛЮБОМ браузере, потому что это просто')
lines.append('  обычные #hex значения — никакого @color-profile / color()')
lines.append('  не используется. CSS-переменные перебивают исходную палитру.')
lines.append('  ')
lines.append('  Cгенерирован /tmp/bake-cmyk-css.py — править руками не нужно,')
lines.append('  пересобирайте скриптом при обновлении палитры.')
lines.append('*/')
lines.append('')
lines.append('body.proof-cmyk-baked {')
lines.append('  /* Цветовые соответствия sRGB → proof:')
for orig, proofed, label in mapping:
    lines.append(f'       {orig} → {proofed}  ({label})')
lines.append('  */')
lines.append('}')
lines.append('')

# Готовим переписывание: для каждого исходного цвета делаем правило
# с !important, чтобы перебить inline-стили.
# Используем замену через CSS-переменные? Нет, ICC меняет КОНКРЕТНЫЕ значения,
# поэтому просто переопределяем background/color/border-color там,
# где конкретный hex использовался.

# Сначала компилируем словарь sRGB→proof для удобства lookup'а в JS,
# но раз файл чисто CSS, сделаем мaпинг через атрибутный селектор/переменные.
# Самый чистый вариант — глобальные CSS-переменные с baked-значениями,
# которые перебивают такие же переменные исходного файла.
# Но исходники жёстко прописывают hex без переменных.
# Поэтому делаем точечные правила для самых заметных мест.

def proof_for(hex_str):
    for orig, proofed, _ in mapping:
        if orig.lower() == hex_str.lower():
            return proofed
    return hex_str

CSS_RULES = '''
/* ── Базовый фон/текст страницы ── */
body.proof-cmyk-baked {
  background: %(c_1a1208)s !important;
  background-image: radial-gradient(
    ellipse at top,
    %(c_2a1c0a)s 0%%,
    %(c_1a1208)s 60%%
  ) !important;
  color: %(c_e8d5a3)s !important;
}

/* ── Шапка ── */
body.proof-cmyk-baked .site-header h1 {
  color: %(c_f0c060)s !important;
}
body.proof-cmyk-baked .site-header .subtitle,
body.proof-cmyk-baked .stat-label,
body.proof-cmyk-baked .sidebar-title,
body.proof-cmyk-baked .section-label {
  color: %(c_7a5a2a)s !important;
}
body.proof-cmyk-baked .stat-value,
body.proof-cmyk-baked .site-header-link {
  color: %(c_f0c060)s !important;
}

/* ── Фильтр-кнопки ── */
body.proof-cmyk-baked .filter-btn {
  background: %(c_231a0e)s !important;
  color: %(c_a08050)s !important;
  border-color: %(c_3a2a10)s !important;
}
body.proof-cmyk-baked .filter-btn:hover { color: %(c_e8d5a3)s !important; }

/* ── Плашки заголовков по группам (перекрываем inline background) ── */
body.proof-cmyk-baked .card-item[data-group="weapon"]      .card-title-wrap,
body.proof-cmyk-baked .card-item[data-group="aoe"]         .card-title-wrap,
body.proof-cmyk-baked .card-item[data-group="effect"]      .card-title-wrap,
body.proof-cmyk-baked .card-item[data-group="action"]      .card-title-wrap {
  background: %(c_231F20)s !important;
}
body.proof-cmyk-baked .card-item[data-group="trap"]        .card-title-wrap {
  background: %(c_43525A)s !important;
}
body.proof-cmyk-baked .card-item[data-group="defense"]     .card-title-wrap {
  background: %(c_dca300)s !important;
}
body.proof-cmyk-baked .card-item[data-group="stance"]      .card-title-wrap {
  background: %(c_A78B6B)s !important;
}
body.proof-cmyk-baked .card-item[data-group="modifier"]    .card-title-wrap {
  background: %(c_ED1C24)s !important;
}
body.proof-cmyk-baked .card-item[data-group="intervention"].card-title-wrap {
  background: %(c_3B8476)s !important;
}
body.proof-cmyk-baked .card-item[data-group="character"]   .card-title-wrap {
  background: %(c_6C8CC7)s !important;
}
body.proof-cmyk-baked .card-item[data-group="role"]        .card-title-wrap {
  background: %(c_5d3c75)s !important;
}
/* Per-card override (роли с titleBgColor) */
body.proof-cmyk-baked .card-item[data-card-id="200"] .card-title-wrap {
  background: %(c_0D233C)s !important;
}
body.proof-cmyk-baked .card-item[data-card-id="201"] .card-title-wrap,
body.proof-cmyk-baked .card-item[data-card-id="202"] .card-title-wrap {
  background: %(c_891511)s !important;
}

/* ── Тэги типов ── */
body.proof-cmyk-baked .type-tag--poison {
  color: %(c_7fff7f)s !important;
  background: %(c_0d2e0d)s !important;
  border-color: %(c_3a8a3a)s !important;
}
body.proof-cmyk-baked .type-tag--print {
  color: %(c_a8d4f0)s !important;
  background: %(c_0d1e2e)s !important;
  border-color: %(c_2a5a7a)s !important;
}
body.proof-cmyk-baked .type-tag--draft {
  color: %(c_f0d080)s !important;
  background: %(c_2a2000)s !important;
  border-color: %(c_7a6000)s !important;
}
body.proof-cmyk-baked .type-tag--trash {
  color: %(c_c0c0c0)s !important;
  background: %(c_1e1e1e)s !important;
  border-color: %(c_555555)s !important;
}

/* ── Бейджи комментариев / share ── */
body.proof-cmyk-baked .card-comments-btn--has,
body.proof-cmyk-baked .card-share-btn {
  border-color: %(c_c8860a)s !important;
  color: %(c_f0c060)s !important;
}
body.proof-cmyk-baked .card-comments-btn--has::after {
  background: %(c_e8453a)s !important;
  box-shadow: none !important;  /* пульсация в proof-режиме не нужна */
  animation: none !important;
}

/* ── Текст на бумажной плашке описания ── */
body.proof-cmyk-baked .card-desc,
body.proof-cmyk-baked .card-desc-part {
  color: %(c_1a1208)s !important;
}
body.proof-cmyk-baked .card-desc-prefix {
  color: %(c_3a2410)s !important;
}
body.proof-cmyk-baked .card-desc-or-line {
  background: linear-gradient(
    to var(--or-line-dir, right),
    transparent,
    %(c_5a3e1b)s 40%%,
    %(c_5a3e1b)s
  ) !important;
}
body.proof-cmyk-baked .card-desc-or-label {
  color: %(c_5a3e1b)s !important;
}
'''.strip('\n')

# Подставляем все цвета
substitutions = {}
for orig, proofed, _ in mapping:
    key = 'c_' + orig.lstrip('#')
    substitutions[key] = proofed

# Если какой-то ключ запросили в шаблоне а его нет в палитре —
# Python кинет KeyError, что и хорошо: сразу заметим пропуск.
out_css = CSS_RULES % substitutions

with open(OUT_CSS, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
    f.write(out_css)
    f.write('\n')

print(f"\nWrote {OUT_CSS}")
print(f"Size: {os.path.getsize(OUT_CSS)} bytes")
