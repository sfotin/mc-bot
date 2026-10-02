"""
Точная съёмка пустот по колоннам из файла региона (.mca) — для трасс под землёй
(метро, коллектор; формат как у docs/terrain/industry-voids.json, но несколько
боксов в одном файле).

Для каждой колонны (x, z) бокса:
  ground — верх твёрдого (без растительности, деревьев, снега, жидкостей);
  voids  — интервалы [y0, y1, тип] пустот ниже ground, от Y 3: a — воздух
           (и прозрачная мелочь: факелы, рельсы, трава и т.п.), w — вода, l — лава.
Пустоты включают и построенное (залы, галереи) — генератор сверяет с моделью
мира и отделяет природные полости.

Запуск:
    terrain_voids.py <r.-2.3.mca> <выход.json> --box X1 Z1 X2 Z2 [--box …] [--note текст]
"""
import argparse
import json

from region import resolve_box, load_region, read_chunk_sections, block_id_at

AIR_LIKE = {0, 6, 27, 28, 30, 31, 32, 37, 38, 39, 40, 50, 51, 55, 59, 63, 65, 66, 68, 69, 70, 72, 75, 76, 77, 78,
            83, 104, 105, 106, 111, 115, 131, 132, 141, 142, 143, 147, 148, 157, 171, 175, 141}
WATER = {8, 9}
LAVA = {10, 11}
NOT_GROUND = AIR_LIKE | WATER | LAVA | {17, 18, 161, 162, 99, 100, 81, 83, 106, 127, 175}
Y_MIN = 3


def survey_box(data, box):
    X0, Z0, W, H, RX, RZ, cx0, cx1, cz0, cz1 = resolve_box(box)
    ground, voids = [None] * (W * H), [None] * (W * H)
    for cx in range(cx0, cx1 + 1):
        for cz in range(cz0, cz1 + 1):
            secs = read_chunk_sections(data, cx, cz, RX, RZ)
            if secs is None: continue
            top = (max(secs) + 1) * 16 - 1 if secs else 0
            for lx in range(16):
                for lz in range(16):
                    x, z = cx * 16 + lx, cz * 16 + lz
                    if not (X0 <= x < X0 + W and Z0 <= z < Z0 + H): continue
                    col = [block_id_at(secs, lx, y, lz) for y in range(top + 1)]
                    g = next((y for y in range(top, -1, -1) if col[y] not in NOT_GROUND), None)
                    iv = []
                    if g is not None:
                        cur = None
                        for y in range(Y_MIN, g):
                            b = col[y]
                            t = 'w' if b in WATER else 'l' if b in LAVA else 'a' if b in AIR_LIKE else None
                            if t and cur and cur[2] == t and cur[1] == y - 1: cur[1] = y
                            else:
                                if cur: iv.append(cur)
                                cur = [y, y, t] if t else None
                        if cur: iv.append(cur)
                    i = (z - Z0) * W + x - X0
                    ground[i], voids[i] = g, iv
    return dict(x0=X0, z0=Z0, w=W, h=H, ground=ground, voids=voids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mca'); ap.add_argument('out')
    ap.add_argument('--box', nargs=4, type=int, action='append', required=True)
    ap.add_argument('--note', default='')
    a = ap.parse_args()
    data = load_region(a.mca)
    parts = [survey_box(data, tuple(b)) for b in a.box]
    note = (a.note + '; ' if a.note else '') + ('index=(z-z0)*w+(x-x0); ground=верх твёрдого (без растительности, '
            'деревьев, снега, жидкостей); voids=интервалы [y0,y1,тип] ниже ground с Y 3: a — воздух, w — вода, l — лава')
    json.dump(dict(note=note, parts=parts), open(a.out, 'w'), separators=(',', ':'), ensure_ascii=False)
    n = sum(1 for p in parts for v in p['voids'] if v)
    print(f'{a.out}: боксов {len(parts)}, колонн с пустотами {n}')


if __name__ == '__main__':
    main()
