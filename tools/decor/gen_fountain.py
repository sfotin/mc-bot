"""
Генератор фонтана (DECOR.md §5.1/§5.2): трёхъярусный фонтан 9x9, либо (при
--size 13) тот же фонтан в центре с добавленным кольцевым каналом-уступом
13x13 вокруг него ("Набережная", DECOR.md §5.2).

Запуск:
    gen_fountain.py --size 9|13 --palette stone|med [--out PATH] [--plan]

Маски и порядок постройки - см. задание/DECOR.md §5. Палитра управляет
только материалом (S/C/s/D), геометрия от неё не зависит.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decor_lib as dl  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PALETTES = {
    'stone': {'S': 'stonebrick', 'C': 'stonebrick:3', 's': 'stone_slab:5', 'D': 'stonebrick'},
    'med': {'S': 'quartz_block', 'C': 'quartz_block:2', 's': 'stone_slab:7', 'D': 'double_stone_slab:9'},
}
STAIR_BLOCK = {'stone': 'stone_brick_stairs', 'med': 'quartz_stairs'}

SEA_LANTERN_CORE_Y0 = {(2, 4), (6, 4), (4, 2), (4, 6)}
SEA_LANTERN_RING_Y0 = {(6, 1), (6, 11), (1, 6), (11, 6), (2, 2), (10, 2), (2, 10), (10, 10)}
JET_MID = ((4, 1), (4, 7), (1, 4), (7, 4))
JET_INNER = ((4, 3), (4, 5), (3, 4), (5, 4))
RING_JETS = ((6, 1), (6, 11), (1, 6), (11, 6))

# facing "к центру" по первому соседу вне маски, в заданном порядке проверки
_RING_STAIR_DIRS = ((0, -1, 2), (0, 1, 3), (-1, 0, 0), (1, 0, 1))  # север,юг,запад,восток -> meta


def oct9(x, z):
    if not (0 <= x <= 8 and 0 <= z <= 8):
        return False
    if z in (0, 8):
        return 2 <= x <= 6
    if z in (1, 7):
        return 1 <= x <= 7
    return True


def mask5(x, z):
    if not (2 <= x <= 6 and 2 <= z <= 6):
        return False
    return (x, z) not in ((2, 2), (2, 6), (6, 2), (6, 6))


def oct13(x, z):
    if not (0 <= x <= 12 and 0 <= z <= 12):
        return False
    if z in (0, 12):
        return 3 <= x <= 9
    if z in (1, 11):
        return 2 <= x <= 10
    if z in (2, 10):
        return 1 <= x <= 11
    return True


def rim(mask_fn, x, z):
    if not mask_fn(x, z):
        return False
    return any(not mask_fn(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def build_core(pal, ox=0, oy=0, oz=0):
    cells = {}

    def put(x, y, z, block):
        cells[(x + ox, y + oy, z + oz)] = block

    # y0: дно
    for x in range(9):
        for z in range(9):
            if not oct9(x, z):
                continue
            put(x, 0, z, 'sea_lantern' if (x, z) in SEA_LANTERN_CORE_Y0 else pal['D'])

    # y1: борт нижней чаши / вода
    for x in range(9):
        for z in range(9):
            if not oct9(x, z):
                continue
            put(x, 1, z, pal['S'] if rim(oct9, x, z) else 'water')

    # y2: плита-край нижней чаши
    for x in range(9):
        for z in range(9):
            if not oct9(x, z):
                continue
            if rim(oct9, x, z):
                put(x, 2, z, pal['s'])

    # колонна (4,y,4), y=1..7
    for y in range(1, 8):
        put(4, y, 4, pal['C'])

    # y4: диск средней чаши (mask5), включая центр
    for x in range(2, 7):
        for z in range(2, 7):
            if not mask5(x, z):
                continue
            put(x, 4, z, pal['S'])

    # y5: борт средней чаши / вода, центр не трогаем
    for x in range(2, 7):
        for z in range(2, 7):
            if not mask5(x, z):
                continue
            if (x, z) == (4, 4):
                continue
            put(x, 5, z, pal['S'] if rim(mask5, x, z) else 'water')

    # струи со средней чаши
    for x, z in JET_MID:
        put(x, 5, z, 'water')
    # струи с макушки колонны в кольцо средней чаши
    for x, z in JET_INNER:
        put(x, 7, z, 'water')

    # козырьки над струями макушки + макушка
    for x, z in JET_INNER:
        put(x, 8, z, pal['s'])
    put(4, 8, 4, 'sea_lantern')
    put(4, 9, 4, 'stained_glass:3')
    put(4, 10, 4, pal['s'])

    return cells


def core_footprint_global(x, z, shift_x, shift_z):
    return oct9(x - shift_x, z - shift_z)


def build_ring(pal, stair_block, shift_x, shift_z):
    cells = {}

    def put(x, y, z, block):
        cells[(x, y, z)] = block

    for x in range(13):
        for z in range(13):
            if not oct13(x, z):
                continue
            put(x, 0, z, 'sea_lantern' if (x, z) in SEA_LANTERN_RING_Y0 else pal['D'])

    for x in range(13):
        for z in range(13):
            if not oct13(x, z):
                continue
            if core_footprint_global(x, z, shift_x, shift_z):
                continue  # след ядра на этом слое - ядро уже поставило свои блоки
            if rim(oct13, x, z):
                meta = None
                for dx, dz, m in _RING_STAIR_DIRS:
                    if not oct13(x + dx, z + dz):
                        meta = m
                        break
                put(x, 1, z, f'{stair_block}:{meta}')
            else:
                put(x, 1, z, 'water')

    for x, z in RING_JETS:
        put(x, 3, z, 'water')

    return cells


EXPECTED = {
    (9, 'stone'): {
        'entries': 223,
        'counts': {'stonebrick': 122, 'water': 60, 'stone_slab:5': 29, 'stonebrick:3': 6,
                   'sea_lantern': 5, 'stained_glass:3': 1},
        'size': (9, 11, 9),
    },
    (13, 'med'): {
        'entries': 448,
        'counts': {'double_stone_slab:9': 202, 'water': 104, 'quartz_block': 57, 'stone_slab:7': 29,
                   'sea_lantern': 13, 'quartz_stairs:2': 13, 'quartz_stairs:3': 13,
                   'quartz_block:2': 6, 'quartz_stairs:0': 5, 'quartz_stairs:1': 5, 'stained_glass:3': 1},
        'size': (13, 12, 13),
    },
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--size', type=int, choices=(9, 13), required=True)
    p.add_argument('--palette', choices=('stone', 'med'), required=True)
    p.add_argument('--out', default=None, help='выходная схема (по умолчанию schemas/decor-fountain-<size>[-<palette>].json)')
    p.add_argument('--plan', action='store_true', help='напечатать поэтажный план ASCII')
    return p.parse_args()


def main():
    args = parse_args()
    pal = PALETTES[args.palette]

    if args.size == 9:
        cells = build_core(pal)
    else:
        shift_x, shift_y, shift_z = 2, 1, 2
        cells = build_core(pal, ox=shift_x, oy=shift_y, oz=shift_z)
        ring = build_ring(pal, STAIR_BLOCK[args.palette], shift_x, shift_z)
        cells.update(ring)  # кольцо не трогает клетки ядра (см. build_ring: core_footprint_global пропускается)

    order = dl.compute_order(cells)

    default_name = f'decor-fountain-{args.size}.json' if args.size == 9 else f'decor-fountain-{args.size}-{args.palette}.json'
    out_path = args.out or os.path.join('schemas', default_name)
    dl.save(cells, out_path, order)

    terrain = dl.make_terrain('y0')
    water_errors = dl.check_water(cells, terrain)
    support_errors, support_warnings = dl.check_supports(cells, order, terrain)
    errors = water_errors + support_errors

    label = f'фонтан {args.size}x{args.size} ({args.palette}) -> {out_path}'
    err_count = dl.report(cells, order, errors, support_warnings, label=label)

    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    size = (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, max(zs) - min(zs) + 1)
    exp = EXPECTED.get((args.size, args.palette))
    if exp:
        from collections import Counter
        counts = dict(Counter(cells.values()))
        ok = (len(cells) == exp['entries']) and (size == exp['size']) and (counts == exp['counts'])
        print(f'КОНТРОЛЬНЫЕ ЧИСЛА: {"СОВПАЛИ" if ok else "!!! НЕ СОВПАЛИ !!!"}')
        if not ok:
            print('  ожидалось entries=', exp['entries'], 'size=', exp['size'], 'counts=', exp['counts'])
            print('  получено  entries=', len(cells), 'size=', size, 'counts=', counts)

    if args.plan:
        legend = {v: k for k, v in pal.items()}
        legend['water'] = '~'
        legend['sea_lantern'] = 'L'
        legend['stained_glass:3'] = 'g'
        if args.size == 13:
            legend[f'{STAIR_BLOCK[args.palette]}:0'] = '<'
            legend[f'{STAIR_BLOCK[args.palette]}:1'] = '>'
            legend[f'{STAIR_BLOCK[args.palette]}:2'] = '^'
            legend[f'{STAIR_BLOCK[args.palette]}:3'] = 'v'
        dl.plan(cells, legend=legend)

    sys.exit(1 if err_count else 0)


if __name__ == '__main__':
    main()
