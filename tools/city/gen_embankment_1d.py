"""
Генератор схемы 1d района «Набережная» (см. CITY.md - Районы - Набережная):
пересборка пляжа поверх этапа 1 (земляные работы/стенка), НЕ поверх
фактического результата 1b/1c на сервере - тот испорчен падением песка (см.
BOT.md §10.4.8 "Опыт": buildFillCommands до исправления ставил боксы не
снизу вверх, песок нередко уходил раньше опоры). Форма пляжа - та же, что
задумывалась в 1c (урез и подводный уклон по детерминированному шуму,
ограничение крутизны, медианное сглаживание 3x3), но каждая затронутая
колонна задаётся ЦЕЛИКОМ (каменное ядро, песок, вода, воздух) - это заодно
убирает любой упавший песок, что бы ни лежало на сервере сейчас. Колонны,
которых не касались ни 1b, ни 1c, и колонны, где итоговая высота не
отличается от рельефа после этапа 1, схема не трогает.

Читает docs/terrain/site.json (рельеф) и schemas/embankment-1-earthworks.json
(этап 1, как опору) как исходное состояние; schemas/embankment-1b-beach.json
и schemas/embankment-1c-beach-natural.json читает ТОЛЬКО чтобы знать, какие
колонны (x,z) они трогали (см. TOUCHED) - не их содержимое как опору.

Запуск:
    gen_embankment_1d.py [--site docs/terrain/site.json]
                          [--stage1 schemas/embankment-1-earthworks.json]
                          [--stage1-origin -776 56 1847]
                          [--stage1b schemas/embankment-1b-beach.json]
                          [--stage1b-origin -752 46 1860]
                          [--stage1c schemas/embankment-1c-beach-natural.json]
                          [--stage1c-origin -756 47 1863]
                          [--out schemas/embankment-1d-beach-rebuild.json]
                          [--preview docs/districts/embankment-1d-preview.png]

ВАЖНО: логика шума (vnoise/_grid), ограничения крутизны уреза (shore) и
медианного сглаживания (SM) - как согласовано, не менять без явного запроса.
Выход пишется отсортированным по Y (по возрастанию) - см. п.2 задания.
"""
import argparse
import json
import math
import os
import random
from collections import Counter, deque

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SITE = 'docs/terrain/site.json'
DEFAULT_STAGE1 = 'schemas/embankment-1-earthworks.json'
DEFAULT_STAGE1_ORIGIN = (-776, 56, 1847)
DEFAULT_STAGE1B = 'schemas/embankment-1b-beach.json'
DEFAULT_STAGE1B_ORIGIN = (-752, 46, 1860)
DEFAULT_STAGE1C = 'schemas/embankment-1c-beach-natural.json'
DEFAULT_STAGE1C_ORIGIN = (-756, 47, 1863)
DEFAULT_OUT = 'schemas/embankment-1d-beach-rebuild.json'
DEFAULT_PREVIEW = 'docs/districts/embankment-1d-preview.png'

X1, X2 = -760, -695


def _find_font_path(bold=False):
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold
        else '/System/Library/Fonts/Supplemental/Arial.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _load_font(size, bold=False):
    path = _find_font_path(bold)
    if path:
        return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--site', default=DEFAULT_SITE,
                    help='site.json от terrain_from_region.py (по умолчанию %(default)s)')
    p.add_argument('--stage1', default=DEFAULT_STAGE1,
                    help='схема этапа 1 - исходное состояние/опора (по умолчанию %(default)s)')
    p.add_argument('--stage1-origin', nargs=3, type=int, default=list(DEFAULT_STAGE1_ORIGIN), metavar=('X', 'Y', 'Z'),
                    help='origin схемы этапа 1 (по умолчанию %(default)s)')
    p.add_argument('--stage1b', default=DEFAULT_STAGE1B,
                    help='схема этапа 1b - только чтобы знать затронутые колонны (по умолчанию %(default)s)')
    p.add_argument('--stage1b-origin', nargs=3, type=int, default=list(DEFAULT_STAGE1B_ORIGIN), metavar=('X', 'Y', 'Z'),
                    help='origin схемы этапа 1b (по умолчанию %(default)s)')
    p.add_argument('--stage1c', default=DEFAULT_STAGE1C,
                    help='схема этапа 1c - только чтобы знать затронутые колонны (по умолчанию %(default)s)')
    p.add_argument('--stage1c-origin', nargs=3, type=int, default=list(DEFAULT_STAGE1C_ORIGIN), metavar=('X', 'Y', 'Z'),
                    help='origin схемы этапа 1c (по умолчанию %(default)s)')
    p.add_argument('--out', default=DEFAULT_OUT,
                    help='выходная схема (по умолчанию %(default)s)')
    p.add_argument('--preview', default=DEFAULT_PREVIEW,
                    help='превью PNG (по умолчанию %(default)s)')
    return p.parse_args()


def main():
    args = parse_args()

    with open(args.site, encoding='utf-8') as f:
        d = json.load(f)
    SX0, SZ0, SW = d['x0'], d['z0'], d['w']

    def G(x, z): return d['ground'][(z - SZ0) * SW + (x - SX0)]

    def T(x, z): return d['top'][(z - SZ0) * SW + (x - SX0)]

    def WA(x, z): return d['water'][(z - SZ0) * SW + (x - SX0)]

    # 1d НЕ опирается на фактический результат 1b/1c (он испорчен падением
    # песка) - опора только рельеф + этап 1.
    B1 = {}
    S1 = {}
    ox1, oy1, oz1 = args.stage1_origin
    with open(args.stage1, encoding='utf-8') as f:
        for e in json.load(f):
            S1[(e['x'] + ox1, e['y'] + oy1, e['z'] + oz1)] = e['block']

    def base(x, y, z):
        if (x, y, z) in B1: return B1[(x, y, z)]
        if (x, y, z) in S1: return S1[(x, y, z)]
        g = G(x, z); wa = WA(x, z)
        if y <= g: return 'ground'
        if wa is not None and y <= wa: return 'water'
        return 'air'

    SOL = lambda b: b not in ('air', 'water')

    def surf(fn, x, z):
        for y in range(75, 40, -1):
            if SOL(fn(x, y, z)): return y

    def _grid(i, j, layer):  # детерминированно по координате узла - не зависит от порядка вызовов
        seed = (i * 73856093 ^ j * 19349663 ^ layer * 83492791 ^ 20260925) & 0xffffffff
        return random.Random(seed).uniform(-1, 1)

    def vnoise(x, z, cell, layer):  # гладкий «случайный» шум без повторяющегося рисунка
        fx, fz = x / cell, z / cell; i, j = math.floor(fx), math.floor(fz); tx, tz = fx - i, fz - j
        sx = tx * tx * (3 - 2 * tx); sz = tz * tz * (3 - 2 * tz)
        a = _grid(i, j, layer); b = _grid(i + 1, j, layer); c = _grid(i, j + 1, layer); d2 = _grid(i + 1, j + 1, layer)
        return (a * (1 - sx) + b * sx) * (1 - sz) + (c * (1 - sx) + d2 * sx) * sz

    def _shore_raw(x):
        return 1867.5 + 2.2 * vnoise(x, 0, 8, 1) + 0.5 * vnoise(x, 0, 4, 2)

    _SH = {}

    def shore(x):  # урез: шум + ограничение крутизны (не больше 0.7 блока на блок по X)
        if not _SH:
            xs = list(range(-790, -660)); v = [_shore_raw(i) for i in xs]
            for _ in range(4):
                for i in range(1, len(v)): v[i] = max(min(v[i], v[i - 1] + 0.7), v[i - 1] - 0.7)
                for i in range(len(v) - 2, -1, -1): v[i] = max(min(v[i], v[i + 1] + 0.7), v[i + 1] - 0.7)
            _SH.update(zip(xs, v))
        return _SH[x]

    def slope(x):
        return 3.2

    def bumps(x, z):  # неровности дна, 2 октавы
        return 1.4 * vnoise(x, z, 6, 3) + 0.7 * vnoise(x, z, 3, 4)

    def east_edge(z):  # извилистый восточный край подводной отмели (вместо прямой по x=-717)
        return -717 + 0.45 * (z - 1870) + 2.0 * math.sin(z / 3.7) + 1.0 * math.sin(z / 1.9 + 0.6)

    def prof0(x, z):
        dd = z - shore(x) + 0.9 * vnoise(x, z, 2.5, 7)
        if dd <= -2.5: return 63
        if dd <= 0.5: return 62
        return min(62, 62 - math.floor((dd - 0.5) / slope(x) + 0.5 - bumps(x, z) * min(1, (dd - 0.5) / 3)))

    def prof(x, z):
        base_n = prof0(x, z)
        wt = -748 + 3 * vnoise(0, z, 5, 8)  # запад: к мысу подсыпка сходит на нет по неровной линии
        if x < wt and z - shore(x) > 1.5: base_n -= math.ceil((wt - x) * 0.8)
        if z >= 1870:  # за концом возвратной стенки: отмель плавно уходит вглубь к востоку
            p = x - (east_edge(z) - 7) + 2.5 * vnoise(x, z, 5, 5)
            if p > 0: base_n -= math.ceil(p / 3)
            tp = -713 + 4 * vnoise(0, z, 5, 6)  # к пирсу сходим на естественное дно по неровной линии
            if x > tp: base_n -= math.ceil((x - tp) * 0.7)
        return base_n

    cells = {}

    def put(x, y, z, b): cells[(x, y, z)] = b

    NN = {}
    for x in range(X1, X2 + 1):
        for z in range(1860, 1912):
            if x >= -716 and z <= 1869: continue  # стенка, парапет и настил не трогаем
            if x > -700 and z < 1876: continue      # углубление у стенки для лодок - не трогаем
            n = prof(x, z)
            if x >= -715 and z <= 1875:
                n -= math.ceil(max(0, x - (-713 + 3 * vnoise(x, z, 4, 9))) * 0.8)
                n = max(n, 57)  # не копаем глубже дна углубления
            NN[(x, z)] = n
    # сглаживание: медиана 3x3 убирает одиночные «зубцы» и прямоугольные выступы
    SM = {}
    for (x, z), n in NN.items():
        v = sorted(NN.get((x + a, z + b), n) for a in (-1, 0, 1) for b in (-1, 0, 1))
        SM[(x, z)] = v[4]

    # какие колонны трогали 1b/1c (только (x,z) - не их содержимое: то, что
    # реально стоит там сейчас на сервере, может быть испорчено падением)
    TOUCHED = set()
    ox1b, oy1b, oz1b = args.stage1b_origin
    with open(args.stage1b, encoding='utf-8') as f:
        for e in json.load(f):
            TOUCHED.add((e['x'] + ox1b, e['z'] + oz1b))
    ox1c, oy1c, oz1c = args.stage1c_origin
    with open(args.stage1c, encoding='utf-8') as f:
        for e in json.load(f):
            TOUCHED.add((e['x'] + ox1c, e['z'] + oz1c))

    for (x, z), n in SM.items():
        s0 = surf(base, x, z)  # поверхность до 1b/1c: рельеф + этап 1
        if x <= -750 and WA(x, z) is None and G(x, z) > 63: continue  # западный край - естественный склон
        if n < 49: n = s0
        if n < 62 and n < s0: n = s0  # под водой естественное дно не копаем
        if x <= -749 and n < s0: n = s0  # западный край: только подсыпка
        if n == s0 and (x, z) not in TOUCHED: continue
        # колонна задаётся целиком - заодно убирает песок, упавший при 1b/1c
        for y in range(s0 + 1, n - 1): put(x, y, z, 'stone')
        if n - 1 >= s0: put(x, n - 1, z, 'sand')
        elif not SOL(base(x, n - 1, z)): put(x, n - 1, z, 'stone')
        put(x, n, z, 'sand')
        for y in range(n + 1, 63): put(x, y, z, 'water')
        for y in range(max(n + 1, 63), 67): put(x, y, z, 'air')

    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    # отсортировано по Y (по возрастанию), затем X, затем Z - см. п.2 задания
    out = [{'x': x - ox, 'y': y - oy, 'z': z - oz, 'block': b}
           for (x, y, z), b in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2]))]
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'))
    print('origin', ox, oy, oz, 'size', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, 'entries', len(out))
    print(Counter(cells.values()))

    # ================= ВАЛИДАТОРЫ (обязательны перед отправкой схемы, см. BOT.md §12) =================
    def final(x, y, z): return cells.get((x, y, z)) or base(x, y, z)

    hang = [k for k, b in cells.items() if b == 'sand' and not SOL(final(k[0], k[1] - 1, k[2]))]
    leak = [k for k, b in cells.items() if b == 'water'
            and (final(k[0], k[1] - 1, k[2]) == 'air'
                 or any(final(k[0] + a, k[1], k[2] + b2) == 'air' for a, b2 in ((1, 0), (-1, 0), (0, 1), (0, -1))))]
    inflow = [k for k, b in cells.items() if b == 'air'
              and any((k[0] + a, k[1], k[2] + b2) not in cells and final(k[0] + a, k[1], k[2] + b2) == 'water'
                      for a, b2 in ((1, 0), (-1, 0), (0, 1), (0, -1)))]

    def stand(x, y, z): return SOL(final(x, y - 1, z)) and final(x, y, z) == 'air' and final(x, y + 1, z) == 'air'

    start = (-735, 65, 1859); seen = {start}; q = deque([start])
    while q:
        x, y, z = q.popleft()
        for a, b2 in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, -1, 1):
                nn = (x + a, y + dy, z + b2)
                if nn in seen or not (X1 <= nn[0] <= X2) or not (1855 <= nn[2] <= 1872): continue
                if stand(*nn): seen.add(nn); q.append(nn)
    dry = [(x, z) for x in range(X1, -716) for z in range(1860, 1872)
           if surf(final, x, z) >= 62 and not (x <= -750 and WA(x, z) is None and G(x, z) > 63)]
    reach = [(x, z) for (x, z) in dry if (x, surf(final, x, z) + 1, z) in seen]
    print('ВАЛИДАТОР ПРОХОДИМОСТИ: сухих клеток пляжа', len(dry), 'достижимо с аллеи', len(reach))
    print('ВАЛИДАТОР ОПОР: висящий песок', len(hang), hang[:5],
          '| утечка воды', len(set(leak)), list(set(leak))[:5],
          '| вода втекает', len(set(inflow)), sorted(set(inflow))[:5])

    # ================= ПРЕВЬЮ =================
    f11, f13 = _load_font(12), _load_font(14, bold=True)
    COL = {'sand': (240, 222, 160), 'stone': (140, 140, 140), 'ground': (120, 170, 95),
           'water': (70, 120, 200), 'air': (235, 242, 250)}

    def colr(h, fn, x, z):
        if fn(x, h + 1, z) == 'water' or (h < 62 and fn(x, 62, z) == 'water'):
            t = min(1, (62 - h) / 14); return (int(150 - 100 * t), int(205 - 110 * t), int(240 - 70 * t))
        b = fn(x, h, z)
        return COL.get(b, (236, 226, 190))

    K = 10; ZS = range(1856, 1912); XS = range(-762, -690)
    img = Image.new('RGB', (2 * len(XS) * K + 60, len(ZS) * K + 60), (250, 250, 247))
    dr = ImageDraw.Draw(img)
    for k, (fn, tt) in enumerate((
            (base, 'Рельеф до 1b/1c (+ этап 1)'),
            (final, 'После 1d (задумано как 1c)'))):
        ox2 = 20 + k * (len(XS) * K + 20)
        dr.text((ox2, 8), tt, font=f13, fill=(0, 0, 0))
        for i, x in enumerate(XS):
            for j, z in enumerate(ZS):
                h = surf(fn, x, z); dr.rectangle([ox2 + i * K, 30 + j * K, ox2 + i * K + K - 1, 30 + j * K + K - 1], fill=colr(h, fn, x, z))
        for j, z in enumerate(ZS):
            if z % 4 == 0: dr.text((ox2 - 18, 30 + j * K), str(z), font=f11, fill=(60, 60, 60))
    img.save(args.preview)
    print('preview', img.size)


if __name__ == '__main__':
    main()
