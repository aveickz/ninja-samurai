#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen4.py - пакетная генерация вариантов арта карты через img_gen.py.

Запускает варианты волнами по два. Ровно по два: ~/.claude/skills/img/SKILL.md
говорит, что Codex всё равно сериализует запуски у себя, так что от большей
параллельности выигрыша нет, а риск словить ошибку квоты или перепутанные
файлы сессии - есть.

  py -3 .claude/skills/cardimg/gen4.py spec.json --tier preview

spec.json - массив объектов:
  [
    {"name": "kama_p1", "prompt": "<промпт одной строкой>", "refs": []},
    {"name": "kama_p2", "prompt": "...", "refs": ["cards/card_11_kama.png"]}
  ]

Тиры:
  preview - luna/low, 704x1008  (минимально допустимая площадь при 7:10)
  final   - sol/high, 1792x2560 (те же 7:10, под печать)

stdout: по строке на вариант, "<name>\t<путь|FAILED: причина>", в порядке спека.
stderr: прогресс.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# Скилл img переехал: скрипты лежат рядом с его SKILL.md, а в ~/.claude/imagegen/
# осталась только папка out/ с результатами. Старый путь проверяем первым - на
# машинах, где img_gen.py ещё лежит по-старому, ничего не меняется.
IMG_GEN_CANDIDATES = [
    pathlib.Path.home() / ".claude" / "imagegen" / "img_gen.py",
    pathlib.Path.home() / ".claude" / "skills" / "img" / "scripts" / "img_gen.py",
]
IMG_GEN = next((p for p in IMG_GEN_CANDIDATES if p.is_file()), IMG_GEN_CANDIDATES[0])

TIERS = {
    # (model, effort, size, timeout)
    "preview": ("luna", "low", "704x1008", 900),
    "final": ("sol", "high", "1792x2560", 1200),
}


def run_one(idx, total, variant, tier):
    model, effort, size, timeout = TIERS[tier]
    name = variant["name"]
    cmd = [
        sys.executable, str(IMG_GEN), variant["prompt"],
        "--name", name,
        "--size", size,
        "--model", model,
        "--effort", effort,
        "--timeout", str(timeout),
    ]
    for ref in variant.get("refs", []):
        cmd += ["--ref", str(pathlib.Path(ref).resolve())]

    print(f"[{idx}/{total}] {name}: старт ({len(variant.get('refs', []))} ref)",
          file=sys.stderr, flush=True)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        print(f"[{idx}/{total}] {name}: таймаут", file=sys.stderr, flush=True)
        return name, f"FAILED: таймаут {timeout + 60}s"

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        print(f"[{idx}/{total}] {name}: выход {proc.returncode}", file=sys.stderr, flush=True)
        return name, f"FAILED: выход {proc.returncode}; {' | '.join(tail)}"

    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return name, "FAILED: пустой stdout"
    path = lines[-1]
    if not pathlib.Path(path).is_file():
        return name, f"FAILED: последняя строка не файл: {path}"
    print(f"[{idx}/{total}] {name}: готово", file=sys.stderr, flush=True)
    return name, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="JSON-файл со списком вариантов")
    ap.add_argument("--tier", choices=sorted(TIERS), default="preview")
    ap.add_argument("--min-ref", type=int, default=2, metavar="N",
                    help="минимум файлов из папки ref/ в каждом варианте "
                         "(по умолчанию 2; 0 снимает проверку)")
    ap.add_argument("--dry-run", action="store_true",
                    help="прогнать валидацию и показать план, ничего не генерируя "
                         "и не тратя квоту")
    ap.add_argument("--jobs", type=int, default=2, choices=(1, 2), metavar="N",
                    help="сколько запусков параллельно (по умолчанию 2; "
                         "1 исключает подмену файлов между сессиями Codex)")
    args = ap.parse_args()

    if not IMG_GEN.is_file():
        sys.exit("не найден img_gen.py, проверены пути:\n  " +
                 "\n  ".join(str(p) for p in IMG_GEN_CANDIDATES))

    variants = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    if not isinstance(variants, list) or not variants:
        sys.exit("спек должен быть непустым JSON-массивом")

    for v in variants:
        if "name" not in v or "prompt" not in v:
            sys.exit(f"в варианте нет name/prompt: {v}")
        if "\n" in v["prompt"]:
            sys.exit(f"промпт варианта {v['name']} содержит перевод строки - "
                     "codex.CMD обрубит его на первом же \n, сверни в одну строку")
        for ref in v.get("refs", []):
            if not pathlib.Path(ref).is_file():
                sys.exit(f"нет файла-референса: {ref}")
        # считаем всё, что лежит под папкой ref/ на любой глубине - ref/old/ тоже
        from_ref_dir = sum(1 for r in v.get("refs", [])
                           if "ref" in (p.lower() for p in pathlib.Path(r).resolve().parts[:-1]))
        if from_ref_dir < args.min_ref:
            sys.exit(f"в варианте {v['name']} только {from_ref_dir} файл(ов) из ref/, "
                     f"нужно минимум {args.min_ref} - канон колоды живёт там, и без "
                     f"него выходит generic-самурай (снять: --min-ref 0)")

    total = len(variants)

    if args.dry_run:
        model, effort, size, timeout = TIERS[args.tier]
        print(f"tier={args.tier} model={model} effort={effort} size={size} "
              f"timeout={timeout}s, вариантов {total}, волнами по 2")
        for i, v in enumerate(variants, 1):
            print(f"[{i}/{total}] {v['name']}")
            for r in v.get("refs", []):
                print(f"        --ref {r}")
            print(f"        {v['prompt'][:110]}…")
        print("dry-run: квота не тронута")
        return

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(
            lambda p: run_one(p[0] + 1, total, p[1], args.tier),
            enumerate(variants)))

    # Codex пишет результат в ~/.codex/generated_images/<session-id>/, и при
    # параллельных запусках обёртка может забрать чужой файл. Наблюдалось
    # 30.08.2026: два варианта вернули байт-в-байт одну картинку. Ловим по хэшу.
    by_hash = defaultdict(list)
    for name, path in results:
        if not path.startswith("FAILED"):
            by_hash[hashlib.md5(pathlib.Path(path).read_bytes()).hexdigest()].append(name)
    for names in by_hash.values():
        if len(names) > 1:
            print(f"ВНИМАНИЕ: одинаковый файл у вариантов {', '.join(names)} - "
                  f"обёртка забрала чужой результат из сессии Codex; "
                  f"перезапусти их с --jobs 1", file=sys.stderr)

    for name, path in results:
        print(f"{name}\t{path}")


if __name__ == "__main__":
    main()
