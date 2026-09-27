"""Старый город, этап 1: земляные работы (CITY.md §7.3).

- озеро D и Соборный пруд: прямоугольные пруды со срезанными углами, вода
  Y 62…64, дно — песок Y 61, набережные из каменного кирпича Y 60…65;
  старая вода вне новых контуров засыпается (камень + дёрн);
- у набережных грунт подтягивается откосом (65 → 64 → 63), не выше рельефа;
- провал на линии проспекта С–Ю (X −691…−688, Z 1840…1846) засыпается до Y 64;
- южный край озера N внутри района (Z ≥ 1780) засыпается под проспект.

Запуск: gen_oldtown_1.py [--out schemas/oldtown-1-earthworks.json]
                         [--preview docs/districts/oldtown-1-preview.png]
Мир — tools/city/world_model.py. Порядок слоёв (BOT.md §12): 1) массивы
(набережные, засыпка), 2) полости (вода, воздух), 3) дно (песок) и дёрн.
Проверки: опоры + вода + порядок (decor_lib), кровля каньона >= 3,
резерв трасс (ниже Y 60 ничего), перепады грунта у прудов, негативные
прогоны проверок воды и кровли.
"""
import argparse
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO, built_before  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

# пруды: (имя, X0, X1, Z0, Z1) — контур воды; уровень воды, дно, низ и верх набережной
PONDS = [('озеро D', -705, -694, 1820, 1832), ('Соборный пруд', -698, -694, 1800, 1811)]
WATER_TOP, BOTTOM, QUAY_LO, QUAY_TOP = 64, 61, 60, 65
PIT = (-691, -688, 1840, 1846, 64)          # провал: засыпать до Y 64
LAKE_N = (-696, -684, 1780, 1782)           # южный край озера N внутри района
WORK = (-712, -682, 1783, 1848)             # окно поиска старой воды вокруг прудов
ROOF_MIN = 3
RESERVE_Y = 60


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'oldtown-1-earthworks.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-1-preview.png'))
    return p.parse_args()


def pond_cells(x0, x1, z0, z1):
    """Вода: прямоугольник без четырёх угловых клеток (срезанные углы)."""
    return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
            if not ((x in (x0, x1)) and (z in (z0, z1)))}


def ring(cells):
    """Набережная: клетки вокруг воды (8-соседство), не вода."""
    return {(x + a, z + b) for x, z in cells for a in (-1, 0, 1) for b in (-1, 0, 1)} - cells


def build(W):
    cells = {}

    def put(x, y, z, b): cells[(x, y, z)] = b

    WATER, QUAY = set(), set()
    for _, *r in PONDS:
        w = pond_cells(*r); WATER |= w; QUAY |= ring(w)
    # старая вода вне новых прудов (и не под набережной) — засыпать
    old = {(x, z) for x in range(WORK[0], WORK[1] + 1) for z in range(WORK[2], WORK[3] + 1)
           if W.water(x, z) is not None and W.water(x, z) >= W.surf(x, z)}
    lx0, lx1, lz0, lz1 = LAKE_N
    old |= {(x, z) for x in range(lx0, lx1 + 1) for z in range(lz0, lz1 + 1)
            if W.water(x, z) is not None and W.water(x, z) >= W.surf(x, z)}
    FILL = old - WATER - QUAY

    def land_h(x, z):  # высота окрестной суши (медиана), не ниже уровня старой воды
        hs = sorted(W.surf(x + a, z + b) for a in range(-2, 3) for b in range(-2, 3)
                    if (x + a, z + b) not in old and (x + a, z + b) not in WATER)
        h = hs[len(hs) // 2] if hs else WATER_TOP
        return max(h, W.water(x, z) or 0)

    # откос у набережных: грунт на расстоянии d от набережной не ниже QUAY_TOP - d (только подсыпка)
    SLOPE = {}
    for x, z in {(x + a, z + b) for x, z in QUAY for a in range(-2, 3) for b in range(-2, 3)} - QUAY - WATER:
        d = min(max(abs(x - qx), abs(z - qz)) for qx, qz in QUAY if abs(x - qx) <= 2 and abs(z - qz) <= 2)
        t = QUAY_TOP - d
        base = land_h(x, z) if (x, z) in FILL else W.surf(x, z)
        if (x, z) in FILL or base < t: SLOPE[(x, z)] = max(base, t)
    TGT = {k: land_h(*k) for k in FILL}
    TGT.update(SLOPE)
    px0, px1, pz0, pz1, py = PIT
    for x in range(px0, px1 + 1):
        for z in range(pz0, pz1 + 1):
            if W.surf(x, z) < py: TGT[(x, z)] = py

    def plant_top(x, z):
        y = max(W.surf(x, z), W.water(x, z) or 0) + 1
        while W.block(x, y, z) in ('plant', 'water'): y += 1
        return y - 1

    # 1. МАССИВЫ: набережные, засыпка
    for x, z in QUAY:
        for y in range(QUAY_LO, QUAY_TOP + 1): put(x, y, z, 'stonebrick')
    for (x, z), t in TGT.items():
        for y in range(W.surf(x, z) + 1, t): put(x, y, z, 'stone')
    # 2. ПОЛОСТИ: вода прудов, воздух над водой/засыпкой/набережной
    for x, z in WATER:
        for y in range(BOTTOM + 1, WATER_TOP + 1): put(x, y, z, 'water')
        for y in range(WATER_TOP + 1, max(plant_top(x, z), W.surf(x, z)) + 1): put(x, y, z, 'air')
    for x, z in QUAY:
        for y in range(QUAY_TOP + 1, max(plant_top(x, z), W.surf(x, z)) + 1): put(x, y, z, 'air')
    for (x, z), t in TGT.items():
        for y in range(t + 1, max(plant_top(x, z), W.surf(x, z)) + 1): put(x, y, z, 'air')
    # 3. ДНО И ДЁРН
    for x, z in WATER:
        for y in range(BOTTOM, BOTTOM + 1): put(x, y, z, 'sand')
    for (x, z), t in TGT.items():
        if t > W.surf(x, z): put(x, t, z, 'grass')
    return cells, WATER, QUAY, TGT


def main():
    args = parse_args()
    W = World(built_before('oldtown-1-earthworks.json'))   # мир до этой схемы (она уже в BUILT)
    cells, WATER, QUAY, TGT = build(W)

    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, '| габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, '| записей', len(cells))
    print('вода прудов', len(WATER), 'кл. | набережная', len(QUAY), 'кл. | засыпка/подсыпка', len(TGT), 'кл.')
    print(Counter(cells.values()).most_common(8))

    def final(x, y, z):
        b = cells.get((x, y, z)) or W.block(x, y, z)
        return 'air' if b == 'plant' else b

    def terrain_rel(x, y, z):
        b = W.block(x + ox, y + oy, z + oz)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)

    print('== ПРОВЕРКИ ==')
    errs = dl.check_water(rel, terrain_rel)
    se, wr = dl.check_supports(rel, order, terrain_rel)
    print('опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок', len(errs) + len(se), '| предупреждений', len(wr))
    for m in (errs + se)[:10]: print('  E', m)
    # вода мира рядом со схемой: не открылась ли в воздух (засыпка краёв озера N и старых берегов)
    leak = []
    for (x, y, z), b in cells.items():
        if b != 'air': continue
        for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + a, y, z + c)
            if n not in cells and W.block(*n) == 'water': leak.append(n)
    print('вода рельефа, открытая в воздух схемы:', len(leak), leak[:5])
    # кровля каньона
    def roof_errors(cave_fn):
        lo = {}
        for (x, y, z) in cells: lo[(x, z)] = min(lo.get((x, z), 999), y)
        r = [(y - cave_fn(x, z) - 1, x, z) for (x, z), y in lo.items() if cave_fn(x, z) is not None]
        return min(r) if r else None, [t for t in r if t[0] < ROOF_MIN]
    m, bad_roof = roof_errors(W.cave_top)
    print('кровля каньона под схемой: мин.', m[0] if m else '—', 'бл. (норма >=', ROOF_MIN, ') ошибок', len(bad_roof))
    low = [k for k, b in cells.items() if b != 'air' and k[1] < RESERVE_Y]
    print('резерв трасс: блоков ниже Y', RESERVE_Y, '—', len(low))
    # глубина и дно прудов
    for name, *r in PONDS:
        w = [k for k in WATER if r[0] <= k[0] <= r[1] and r[2] <= k[1] <= r[3]]
        dep = Counter(sum(1 for y in range(55, 70) if final(x, y, z) == 'water') for x, z in w)
        print(f'{name}: клеток воды {len(w)}, глубина {dict(dep)}')

    def top(x, z):
        for y in range(90, 40, -1):
            b = final(x, y, z)
            if b not in ('air', 'water') and not b.startswith('flowing'): return y
    cols = {(k[0], k[2]) for k in cells} - WATER - QUAY
    steep = [(x, z) for x, z in cols for a, c in ((1, 0), (0, 1))
             if (x + a, z + c) not in WATER and (x + a, z + c) not in QUAY and abs(top(x, z) - top(x + a, z + c)) > 1]
    print('грунт вне набережных: перепад > 1 между соседями —', len(steep), steep[:6])
    print('проходимость: пешеходных объектов в этапе нет (дорожки — этап 2)')

    # негативные прогоны
    bad = dict(rel)
    # убрать кусок набережной у воды на уровне воды -> должна быть утечка
    for (x, z) in sorted(QUAY):
        if any((x + a, z + c) in WATER for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            bad[(x - ox, WATER_TOP - oy, z - oz)] = 'air'; break
    print('НЕГАТИВ: вода с дырой в набережной — ошибок', len(dl.check_water(bad, terrain_rel)), '(ждём > 0)')
    print('НЕГАТИВ: каньон под прудами на Y 58 — ошибок кровли', len(roof_errors(lambda x, z: 58 if (x, z) in WATER else None)[1]), '(ждём > 0)')

    if args.preview: preview(args.preview, final, WATER, QUAY)


def preview(path, final, WATER, QUAY):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    X0, X1, Z0, Z1 = -716, -676, 1774, 1850
    S = 8
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 40 + 560, mh + 40), 'white')
    dr = ImageDraw.Draw(img)
    COL = {'stonebrick': (110, 110, 110), 'stone': (130, 130, 130), 'sand': (219, 207, 163)}
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 100
            while y > 30 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            if b == 'water':
                yb = y
                while final(x, yb, z) == 'water': yb -= 1
                dep = y - yb; c = (int(150 - 18 * dep), int(195 - 16 * dep), int(235 - 5 * dep))
            elif b.split(':')[0] in COL and (x, z) in QUAY: c = COL['stonebrick']
            elif b == 'ground' or b == 'grass':
                k = (max(60, min(y, 68)) - 60) / 8; c = (int(200 - 70 * k), int(215 - 40 * k), int(140 - 60 * k))
            else: c = (185, 180, 172)
            dr.rectangle([20 + (x - X0) * S, 20 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 20 + (z - Z0 + 1) * S - 1], fill=c)
    dr.text((20, 2), 'Старый город, этап 1 — вид сверху, X −716…−676, Z 1774…1850', fill='black', font=F(12))
    bx = mw + 40; S2 = 8

    def section(y0, label, pts):
        dr.text((bx, y0 - 16), label, fill='black', font=F(12))
        for u, (x, z) in enumerate(pts):
            for y in range(57, 70):
                b = final(x, y, z)
                if b == 'air': continue
                c = (70, 120, 200) if b == 'water' else (219, 207, 163) if b == 'sand' else (95, 150, 60) if b == 'grass' else \
                    (110, 110, 110) if b == 'stonebrick' else (150, 140, 110) if b == 'ground' else (130, 130, 130)
                yy = y0 + (69 - y) * S2
                dr.rectangle([bx + u * S2, yy, bx + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
            if (x - (pts[0][0]) if pts[0][1] == pts[-1][1] else z - pts[0][1]) % 5 == 0:
                dr.text((bx + u * S2, y0 + 13 * S2 + 2), str(x if pts[0][1] == pts[-1][1] else z), fill='black', font=F(9))
    section(40, 'разрез Z=1826 (озеро D), X −712…−676, Y 57…69', [(x, 1826) for x in range(-712, -676)])
    section(200, 'разрез Z=1806 (Соборный пруд), X −712…−676', [(x, 1806) for x in range(-712, -676)])
    section(360, 'разрез X=−696 (пруд, проспект, озеро D), Z 1796…1836', [(-696, z) for z in range(1796, 1864, 1)][:66])
    section(520, 'разрез X=−689 (провал, проспект), Z 1834…1850', [(-689, z) for z in range(1834, 1851)])
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
