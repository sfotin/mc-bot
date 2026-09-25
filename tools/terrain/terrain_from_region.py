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
"""
import argparse
import struct
import zlib
import json
from collections import Counter

DEFAULT_BOX = (-800, 1728, -593, 1935)

AIR = {0}
WATER = {8, 9}
LAVA = {10, 11}
ICE = {79, 174, 212}
# растительность / мелочь, которую игнорируем для "грунта" (но не для top)
VEG = {6, 17, 18, 31, 32, 37, 38, 39, 40, 59, 78, 81, 83, 86, 99, 100, 103, 104,
       105, 106, 111, 127, 141, 142, 161, 162, 175, 199, 200, 207}


# --- минимальный NBT-ридер (формат региона 1.12.2, без сжатия внешнего слоя) ---
def nbt(buf):
    p = [0]

    def rd(fmt):
        v = struct.unpack_from('>' + fmt, buf, p[0])
        p[0] += struct.calcsize('>' + fmt)
        return v[0]

    def rstr():
        n = rd('H')
        s = buf[p[0]:p[0] + n].decode('utf-8', 'replace')
        p[0] += n
        return s

    def payload(t):
        if t == 1: return rd('b')
        if t == 2: return rd('h')
        if t == 3: return rd('i')
        if t == 4: return rd('q')
        if t == 5: return rd('f')
        if t == 6: return rd('d')
        if t == 7:
            n = rd('i')
            v = buf[p[0]:p[0] + n]
            p[0] += n
            return v
        if t == 8: return rstr()
        if t == 9:
            et = rd('b')
            n = rd('i')
            return [payload(et) for _ in range(n)]
        if t == 10:
            d = {}
            while True:
                tt = rd('b')
                if tt == 0: return d
                name = rstr()
                d[name] = payload(tt)
        if t == 11:
            n = rd('i')
            v = struct.unpack_from('>%di' % n, buf, p[0])
            p[0] += 4 * n
            return list(v)
        if t == 12:
            n = rd('i')
            v = struct.unpack_from('>%dq' % n, buf, p[0])
            p[0] += 8 * n
            return list(v)
        raise ValueError('tag %d' % t)

    t = rd('b')
    rstr()
    return payload(t)


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
    bx1, bz1, bx2, bz2 = args.box
    X0, X1 = sorted((bx1, bx2))
    Z0, Z1 = sorted((bz1, bz2))
    W = X1 - X0 + 1
    H = Z1 - Z0 + 1

    cx0, cx1 = X0 >> 4, X1 >> 4
    cz0, cz1 = Z0 >> 4, Z1 >> 4

    regions = {(cx >> 5, cz >> 5) for cx in (cx0, cx1) for cz in (cz0, cz1)}
    if len(regions) != 1:
        raise SystemExit(
            f'ОШИБКА: бокс X {X0}..{X1} Z {Z0}..{Z1} (чанки X {cx0}..{cx1}, Z {cz0}..{cz1}) '
            f'охватывает несколько файлов региона {sorted(regions)} - один .mca не читает.'
        )
    RX, RZ = regions.pop()

    data = open(args.mca, 'rb').read()

    ground = [None] * (W * H)
    gblock = [None] * (W * H)
    top = [None] * (W * H)
    tblock = [None] * (W * H)
    water = [None] * (W * H)
    missing = []
    ids = Counter()

    for cz in range(cz0, cz1 + 1):
        for cx in range(cx0, cx1 + 1):
            lx, lz = cx - RX * 32, cz - RZ * 32
            i = lz * 32 + lx
            off = struct.unpack('>I', data[i * 4:i * 4 + 4])[0]
            sec, cnt = off >> 8, off & 0xFF
            if sec == 0:
                missing.append((cx, cz))
                continue
            length = struct.unpack('>I', data[sec * 4096:sec * 4096 + 4])[0]
            comp = data[sec * 4096 + 4]
            raw = data[sec * 4096 + 5: sec * 4096 + 4 + length]
            root = nbt(zlib.decompress(raw) if comp == 2 else raw)
            lvl = root['Level']
            assert lvl['xPos'] == cx and lvl['zPos'] == cz
            blocks = {}
            for s in lvl.get('Sections', []):
                B = s['Blocks']
                A = s.get('Add')
                blocks[s['Y']] = (B, A)

            def bid(x, y, z):
                s = blocks.get(y >> 4)
                if not s: return 0
                B, A = s
                k = ((y & 15) << 8) | (z << 4) | x
                v = B[k]
                if A:
                    a = A[k >> 1]
                    v |= ((a >> 4) if k & 1 else (a & 15)) << 8
                return v

            maxy = (max(blocks) + 1) * 16 - 1 if blocks else 0
            for z in range(16):
                for x in range(16):
                    gx, gz = cx * 16 + x, cz * 16 + z
                    idx = (gz - Z0) * W + (gx - X0)
                    wtop = None
                    t = None
                    for y in range(maxy, -1, -1):
                        b = bid(x, y, z)
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
                  f, separators=(',', ':'), ensure_ascii=False)

    g = [v for v in ground if v is not None]
    print('missing chunks', missing)
    if g:
        print('ground min/max', min(g), max(g), 'water cols', sum(1 for v in water if v is not None))
    print('surface ids', ids.most_common(15))


if __name__ == '__main__':
    main()
