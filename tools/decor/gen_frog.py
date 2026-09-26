"""
Генератор «лягушки-водопад» (DECOR.md §6.1): парковая фигура с прудом,
источник воды во рту падает столбиком между «руками» в пруд. Строится по
плану ASCII (7 столбцов x=0..6, строки z=0..7), затем всё сдвигается на +2
по X (итоговая ширина 11 - поля для цветов по краям).

Легенда: G=wool:13 (мох), W=wool:0, B=wool:15, P=wool:6, ~=water, .=нет записи.

Запуск:
    gen_frog.py [--out schemas/decor-frog.json] [--plan]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decor_lib as dl  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LEGEND_IN = {'G': 'wool:13', 'W': 'wool:0', 'B': 'wool:15', 'P': 'wool:6', '~': 'water',
             'F': 'flowing_water:0'}  # F - источник во рту: спокойная water повисла бы (DECOR.md «Опыт»)

# план по слоям (ЛОКАЛЬНЫЕ координаты, до сдвига по X): y -> {z: "строка по x=0..6"}
LAYERS = {
    0: {0: '.......', 1: '.......', 2: '.......', 3: '.......',
        4: '...~...', 5: '~~~~~~~', 6: '~~~~~~~', 7: '.~~~~~.'},
    1: {0: 'GGGGGGG', 1: 'GGGGGGG', 2: 'GGGGGGG', 3: 'GGGGGGG', 4: 'GGG.GGG'},
    2: {0: 'GGGGGGG', 1: 'GGGGGGG', 2: 'GGGGGGG', 3: 'GGGGGGG', 4: '..G.G..'},
    3: {0: '.GGGGG.', 1: '.GGGGG.', 2: '.GGGGG.', 3: '.GGGGG.', 4: '..G.G..'},
    4: {0: '.GGGGG.', 1: '.GGGGG.', 2: '.GGGGG.', 3: '.GGGGG.', 4: '..G.G..'},
    5: {0: '.GGGGG.', 1: '.GGGGG.', 2: '.GGGGG.', 3: '.GGGGG.', 4: '..G.G..'},
    6: {0: 'GGGGGGG', 1: 'GGGGGGG', 2: 'GGGGGGG', 3: 'GGGGGGG', 4: 'GGGFGGG'},
    7: {0: 'GGGGGGG', 1: 'GGGGGGG', 2: 'GGGGGGG', 3: 'GGGGGGG', 4: 'PGGGGGP'},
    8: {0: 'GGGGGGG', 1: 'GGGGGGG', 2: 'GGGGGGG', 3: 'GGGGGGG', 4: 'WBGGGBW'},
    9: {3: 'WW...WW', 4: 'WW...WW'},
}

X_SHIFT = 2  # сдвиг по X после постройки фигуры (поля для цветов)

# растения (УЖЕ итоговые/глобальные координаты - после сдвига), y=1, кроме
# верхних половин double_plant (y=2). См. задание.
FLOWERS = [
    (0, 4, 1, 'double_plant:1'), (0, 4, 2, 'double_plant:8'),
    (1, 5, 1, 'red_flower:8'),
    (0, 6, 1, 'red_flower:0'),
    (1, 7, 1, 'red_flower:7'),
    (2, 8, 1, 'tallgrass:1'),
    (4, 8, 1, 'red_flower:8'),
    (5, 8, 1, 'red_flower:0'),
    (7, 8, 1, 'red_flower:7'),
    (9, 8, 1, 'tallgrass:1'),
    (10, 6, 1, 'double_plant:1'), (10, 6, 2, 'double_plant:8'),
    (9, 5, 1, 'red_flower:8'),
    (10, 4, 1, 'red_flower:0'),
    (9, 7, 1, 'tallgrass:1'),
]
WATERLILIES = [(4, 6, 1, 'waterlily'), (6, 6, 1, 'waterlily')]

EXPECTED = {
    'entries': 280,
    'counts': {
        'wool:13': 228, 'water': 20, 'flowing_water:0': 1, 'wool:0': 10, 'red_flower:8': 3, 'red_flower:0': 3,
        'tallgrass:1': 3, 'wool:6': 2, 'wool:15': 2, 'double_plant:1': 2, 'double_plant:8': 2,
        'red_flower:7': 2, 'waterlily': 2,
    },
    'size': (11, 10, 9),
}


def build():
    cells = {}
    for y, rows in LAYERS.items():
        for z, row in rows.items():
            for x, ch in enumerate(row):
                if ch == '.':
                    continue
                cells[(x + X_SHIFT, y, z)] = LEGEND_IN[ch]

    for x, z, y, block in FLOWERS:
        cells[(x, y, z)] = block
    for x, z, y, block in WATERLILIES:
        cells[(x, y, z)] = block

    return cells


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join('schemas', 'decor-frog.json'))
    p.add_argument('--plan', action='store_true', help='напечатать поэтажный план ASCII')
    return p.parse_args()


def main():
    args = parse_args()
    cells = build()

    order = dl.compute_order(cells)
    dl.save(cells, args.out, order)

    terrain = dl.make_terrain('y0')
    water_warnings = []
    water_errors = dl.check_water(cells, terrain, water_warnings)
    support_errors, support_warnings = dl.check_supports(cells, order, terrain)
    support_warnings = water_warnings + support_warnings
    errors = water_errors + support_errors

    err_count = dl.report(cells, order, errors, support_warnings, label=f'лягушка-водопад -> {args.out}')

    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    size = (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, max(zs) - min(zs) + 1)
    from collections import Counter
    counts = dict(Counter(cells.values()))
    ok = (len(cells) == EXPECTED['entries']) and (size == EXPECTED['size']) and (counts == EXPECTED['counts'])
    print(f'КОНТРОЛЬНЫЕ ЧИСЛА: {"СОВПАЛИ" if ok else "!!! НЕ СОВПАЛИ !!!"}')
    if not ok:
        print('  ожидалось entries=', EXPECTED['entries'], 'size=', EXPECTED['size'], 'counts=', EXPECTED['counts'])
        print('  получено  entries=', len(cells), 'size=', size, 'counts=', counts)

    if args.plan:
        legend = {v: k for k, v in LEGEND_IN.items()}
        legend['red_flower:8'] = 'x'
        legend['red_flower:0'] = 'm'
        legend['red_flower:7'] = 't'
        legend['tallgrass:1'] = 'f'
        legend['double_plant:1'] = 'l'
        legend['double_plant:8'] = 'L'
        legend['waterlily'] = 'o'
        dl.plan(cells, legend=legend)

    sys.exit(1 if err_count else 0)


if __name__ == '__main__':
    main()
