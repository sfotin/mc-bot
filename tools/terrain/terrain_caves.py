"""
Снимает карту подземных пустот участка из файла региона (.mca): для каждой
колонны (x,z) считает, сколько блоков воздуха лежит в узкой полосе под
грунтом (Y от 10 до ground-4, то есть под возможными подвалами/фундаментом,
но выше бедрока) - крупные пустоты в этой полосе выдают пещеры и каньоны,
которые не видны на карте рельефа (terrain_from_region.py).

Запуск:
    terrain_caves.py <файл.mca> <site.json> <выход caves.json> [--box X1 Z1 X2 Z2]

<site.json> - результат terrain_from_region.py для того же участка (нужно
поле "ground"). По умолчанию бокс - весь участок города, как у
terrain_from_region.py; должен совпадать с боксом site.json, иначе часть
колонн останется без данных о грунте (см. GROUND_MISSING ниже).

Регион и чтение .mca - через region.py (общий с terrain_from_region.py).
"""
import argparse
import json

from region import resolve_box, load_region, read_chunk_sections, block_id_at

DEFAULT_BOX = (-800, 1728, -593, 1935)

AIR = 0
Y_FLOOR = 10  # ниже не смотрим - это уже почти бедрок, а не "пустота под городом"
GROUND_MARGIN = 4  # верхняя граница диапазона - ground - GROUND_MARGIN


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mca', help='путь к файлу региона (.mca)')
    p.add_argument('site', help='site.json от terrain_from_region.py (нужно поле ground)')
    p.add_argument('out', help='путь к выходному JSON')
    p.add_argument('--box', nargs=4, type=int, metavar=('X1', 'Z1', 'X2', 'Z2'),
                   default=list(DEFAULT_BOX),
                   help='бокс участка по двум углам, любой порядок (по умолчанию %s)' % (DEFAULT_BOX,))
    return p.parse_args()


def main():
    args = parse_args()
    X0, Z0, W, H, RX, RZ, cx0, cx1, cz0, cz1 = resolve_box(tuple(args.box))
    data = load_region(args.mca)

    with open(args.site, encoding='utf-8') as f:
        site = json.load(f)
    sx0, sz0, sw, sh, sground = site['x0'], site['z0'], site['w'], site['h'], site['ground']

    def ground_at(gx, gz):
        sx, sz = gx - sx0, gz - sz0
        if not (0 <= sx < sw and 0 <= sz < sh):
            return None  # колонна вне бокса site.json - грунт неизвестен
        return sground[sz * sw + sx]

    air = [None] * (W * H)
    min_air = [None] * (W * H)
    missing = []

    for cz in range(cz0, cz1 + 1):
        for cx in range(cx0, cx1 + 1):
            sections = read_chunk_sections(data, cx, cz, RX, RZ)
            if sections is None:
                missing.append((cx, cz))
                continue

            for z in range(16):
                for x in range(16):
                    gx, gz = cx * 16 + x, cz * 16 + z
                    idx = (gz - Z0) * W + (gx - X0)
                    g = ground_at(gx, gz)
                    if g is None:
                        continue  # air/minAir остаются null - грунт неизвестен
                    count = 0
                    lowest = None
                    for y in range(Y_FLOOR, g - GROUND_MARGIN + 1):  # включительно до g-GROUND_MARGIN
                        if block_id_at(sections, x, y, z) == AIR:
                            count += 1
                            if lowest is None or y < lowest:
                                lowest = y
                    air[idx] = count
                    min_air[idx] = lowest

    note = (f'index=(z-z0)*w+(x-x0); air=число блоков воздуха в колонне '
            f'с Y {Y_FLOOR} до ground-{GROUND_MARGIN}; minAir=Y самого нижнего такого '
            f'воздуха или null')
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump({'x0': X0, 'z0': Z0, 'w': W, 'h': H, 'note': note,
                   'air': air, 'minAir': min_air},
                  f, separators=(',', ':'))

    print('missing chunks', missing)
    counted = [v for v in air if v is not None]
    if counted:
        print('cols with cave air', sum(1 for v in counted if v > 0), 'cols >=15 air', sum(1 for v in counted if v >= 15))
        big = [(x, z) for z in range(H) for x in range(W) if (air[z * W + x] or 0) >= 20]
        if big:
            xs = [p[0] for p in big]
            zs = [p[1] for p in big]
            print('bbox big (local x,z)', (min(xs), min(zs)), (max(xs), max(zs)))


if __name__ == '__main__':
    main()
