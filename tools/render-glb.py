# -*- coding: utf-8 -*-
"""Превью 3D-моделей фигурок: для каждой модели из MODELS — заливка с
материалами файла и сетка (светлая заливка + рёбра) → 3d/preview/<key>.png
и <key>-mesh.png, PNG с альфой, обрезаны по содержимому.

Рендерит tools/glb-view.html (three.js) headless Chrome со скриншотом на
прозрачном фоне: WebGL через SwiftShader, доступ к file:// открыт флагом.
Модели без .glb (проект Bambu .3mf) сначала переводятся в .glb скриптом
tools/mf2glb.py в print/copyright_deposit_parts/.

    py -3 tools/render-glb.py              # недостающие превью
    py -3 tools/render-glb.py --force      # все заново
    py -3 tools/render-glb.py trap poison  # конкретные ключи
"""
import os, sys, subprocess, tempfile, shutil
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
OUT = '3d/preview'
GLB_CACHE = 'print/copyright_deposit_parts'      # сюда ложатся .glb, сделанные из .3mf
SIZE = 1200                                      # сторона кадра, px

# key, файл модели, подпись, цвет для .3mf (у .glb цвет свой), поправки камеры
MODELS = [
    ('flag',   '3d/flag.glb',        'Знамя ауры',                   None, {}),
    ('heart',  '3d/heart.glb',       'Жетон жизни',                  None, {}),
    ('honor',  '3d/honmor_new.glb',  'Очко победы',                  None, {}),
    ('trap',   '3d/trap.glb',        'Ловушка — макибиси',           None, {}),
    ('trap2',  '3d/trap2.glb',       'Ловушка — макибиси, вариант',  None, {}),
    ('poison', '3d/poison_prj.3mf',  'Бутылка яда',                  (0.16, 0.55, 0.25), {}),
]
MODES = {'shaded': '', 'mesh': '-mesh'}


def glb_for(key, src, color):
    if src.lower().endswith('.glb'):
        return src
    import mf2glb
    os.makedirs(GLB_CACHE, exist_ok=True)
    dst = os.path.join(GLB_CACHE, key + '.glb')
    if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
        nv, nt, size = mf2glb.convert(src, dst, color or (0.7, 0.7, 0.7))
        print(f'  {src} → {dst}: {nt} треугольников, {size} мм')
    return dst


def shoot(glb, mode, cam):
    url = 'file:///' + os.path.abspath('tools/glb-view.html').replace(os.sep, '/')
    url += f'?src=file:///{os.path.abspath(glb).replace(os.sep, "/")}&mode={mode}&size={SIZE}'
    url += ''.join(f'&{k}={v}' for k, v in cam.items())
    tmp = tempfile.mkdtemp(prefix='glb_')
    png = os.path.join(tmp, 'shot.png')
    try:
        subprocess.run([CHROME, '--headless=new', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                        '--allow-file-access-from-files', '--hide-scrollbars', '--default-background-color=00000000',
                        f'--user-data-dir={os.path.join(tmp, "profile")}', f'--window-size={SIZE},{SIZE}',
                        '--virtual-time-budget=60000', f'--screenshot={png}', url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        im = Image.open(png).convert('RGBA'); im.load()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    box = im.getbbox()
    if not box:
        raise RuntimeError(f'{glb} ({mode}): пустой кадр — модель не загрузилась')
    m = round(SIZE * 0.03)
    return im.crop((max(0, box[0] - m), max(0, box[1] - m), min(SIZE, box[2] + m), min(SIZE, box[3] + m)))


def render(key, src, color, cam, force=False):
    os.makedirs(OUT, exist_ok=True)
    glb, done = None, []
    for mode, suffix in MODES.items():
        dst = f'{OUT}/{key}{suffix}.png'
        if os.path.exists(dst) and not force and os.path.getmtime(dst) > os.path.getmtime(src):
            continue
        glb = glb or glb_for(key, src, color)
        shoot(glb, mode, cam).save(dst, 'PNG', optimize=True)
        done.append(dst)
    return done


if __name__ == '__main__':
    force = '--force' in sys.argv
    keys = [a for a in sys.argv[1:] if not a.startswith('--')]
    known = {m[0] for m in MODELS}
    if set(keys) - known:
        sys.exit(f'нет таких моделей: {", ".join(sorted(set(keys) - known))}; есть: {", ".join(sorted(known))}')
    for key, src, _cap, color, cam in MODELS:
        if keys and key not in keys:
            continue
        for dst in render(key, src, color, cam, force=force or bool(keys)):
            print(dst)
