"""
Снимает рельеф участка из файла региона Minecraft 1.12.2 (формат Anvil, .mca):
для каждой колонны (x,z) внутри бокса находит верх грунта (без растительности)
и верхний непустой не-водный блок, плюс Y поверхности воды (если есть).

Запуск:
    terrain_from_region.py <файл.mca> <выход.json> [--box X1 Z1 X2 Z2]

По умолчанию бокс - участок города (см. CITY.md §1.1): -800 1728 -593 1935.
Два угла бокса можно указывать в любом порядке (нормализуется по min/max).

Регион (RX,RZ) вычисляется из бокса, а не хардкодится: все четыре угла
бокса должны попасть в один и тот же файл региона (32x32 чанка) - если
бокс требует больше одного .mca, скрипт останавливается с явной ошибкой
(чтение сразу нескольких файлов региона не реализовано - не требовалось
для участка города, который целиком укладывается в один регион).

Чтение самого файла региона (NBT, локейшн-таблица, секции блоков) - в
region.py, общем для этого скрипта и terrain_caves.py.
"""
import argparse
import json
from collections import Counter

from region import resolve_box, load_region, read_chunk_sections, block_id_at, max_section_height

DEFAULT_BOX = (-800, 1728, -593, 1935)

AIR = {0}
WATER = {8, 9}
LAVA = {10, 11}
ICE = {79, 174, 212}
# растительность / мелочь, которую игнорируем для "грунта" (но не для top)
VEG = {6, 17, 18, 31, 32, 37, 38, 39, 40, 59, 78, 81, 83, 86, 99, 100, 103, 104,
       105, 106, 111, 127, 141, 142, 161, 162, 175, 199, 200, 207}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mca', help='путь к файлу региона (.mca)')
    p.add_argument('out', help='путь к выходному JSON')
    p.add_argument('--box', nargs=4, type=int, metavar=('X1', 'Z1', 'X2', 'Z2'),
                   default=list(DEFAULT_BOX),
                   help='бокс участка по двум углам, любой порядок (по умолчанию %s)' % (DEFAULT_BOX,))
    return p.parse_args()


def main():
    args = parse_args()
    X0, Z0, W, H, RX, RZ, cx0, cx1, cz0, cz1 = resolve_box(tuple(args.box))
    data = load_region(args.mca)

    ground = [None] * (W * H)
    gblock = [None] * (W * H)
    top = [None] * (W * H)
    tblock = [None] * (W * H)
    water = [None] * (W * H)
    missing = []
    ids = Counter()

    for cz in range(cz0, cz1 + 1):
        for cx in range(cx0, cx1 + 1):
            sections = read_chunk_sections(data, cx, cz, RX, RZ)
            if sections is None:
                missing.append((cx, cz))
                continue

            maxy = max_section_height(sections)
            for z in range(16):
                for x in range(16):
                    gx, gz = cx * 16 + x, cz * 16 + z
                    idx = (gz - Z0) * W + (gx - X0)
                    wtop = None
                    t = None
                    for y in range(maxy, -1, -1):
                        b = block_id_at(sections, x, y, z)
                        if b in AIR: continue
                        if b in WATER:
                            if wtop is None: wtop = y
                            continue
                        if t is None:
                            t = y
                            top[idx] = y
                            tblock[idx] = b
                        if b in VEG: continue
                        ground[idx] = y
                        gblock[idx] = b
                        ids[b] += 1
                        break
                    water[idx] = wtop

    note = ('index=(z-z0)*w+(x-x0); ground=верх грунта без растительности, groundBlock=его блок; '
            'top=первый непустой не-водный блок (включая растительность), topBlock=его блок; '
            'water=Y поверхности воды или null; блоки - числовые ID 1.12.2')
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump({'x0': X0, 'z0': Z0, 'w': W, 'h': H, 'note': note,
                   'ground': ground, 'groundBlock': gblock, 'top': top, 'topBlock': tblock, 'water': water},
                  f, separators=(',', ':'))

    g = [v for v in ground if v is not None]
    print('missing chunks', missing)
    if g:
        print('ground min/max', min(g), max(g), 'water cols', sum(1 for v in water if v is not None))
    print('surface ids', ids.most_common(15))


if __name__ == '__main__':
    main()
