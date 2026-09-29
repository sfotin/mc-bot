"""Сити, этап 4: Т1 «Открывашка» (CITY.md §7.4, форма — P.t_opener из plan_city_v1.py).

Башня 13×13 у проспекта (X −764…−752, Z 1797…1809), верх Y 190. Этажи по 4 блока: каждый
этаж — призма по сечению формы на середине этажа, углы СВ и ЮЗ срезаются к верху до лезвия по
диагонали; перекрытие — объединение сечений соседних этажей (уступы среза — белые карнизы).
Вверху — сквозной трапециевидный проём (этажи 25–28 — две «ноги» по сторонам проёма), над
ним — смотровой зал (этаж 29, пол Y 183, потолок-кровля Y 190, парапет).

- фасад — голубое стекло `stained_glass:3`, у перекрытий — белый бетон; пол — белый бетон,
  в холле — кварц; в перекрытиях — морские фонари сеткой 4×4;
- подъём: винтовая лестница из полублоков вокруг бетонного столба в центре (8 ступеней по
  полблока на этаж, этажи 0–24; проём в перекрытии — над первой ступенью, просвет ≥ 3.5);
  выше — стремянки в ногах проёма: юго-восточная (от этажа 24 до смотрового зала) и
  северо-западная (от зала вниз в северо-западную ногу); стремянка крепится к бетонной полосе;
- холл: входы с юга (к проспекту, предплощадка Z 1810…1811) и с запада (дорожка X −766…−765);
  электрощитовая 3×3 и серверная МЭ 3×3 (CITY.md §6) в юго-восточном углу холла, двери
  с плитами с обеих сторон, проём для кабеля между ними и проём к терминалу; кабельная шахта
  1×1 от Y 60 с люками `iron_trapdoor:8` в каждом перекрытии до этажа 24;
- снаружи плит у дверей нет, изнутри — `stone_pressure_plate`.

Запуск: gen_city_4.py [--out schemas/city-4-opener.json] [--preview docs/districts/city-4-preview.png]
Мир — World() (после постройки — built_before('city-4-opener.json')).
Проверки: опоры + вода + порядок (decor_lib), проходимость без прыжков (с тротуара проспекта
в холл, щитовую, серверную, на каждый этаж 1–24, в обе ноги проёма, в смотровой зал),
подходы к наружным дверям, форма совпадает с планом, кровля каньона, негатив.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO, BUILT, built_before  # noqa: E402
from oldtown_lib import door_approach_issues, outdoor_doors, col, CL  # noqa: E402
import plan_city_v1 as P  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

CX, CZ = -758, 1803
F0 = 67                     # блок пола холла (ходовой уровень 68 — вровень с тротуаром проспекта)
NST = 29                    # этажи 0…28 по 4 блока; этаж 29 — смотровой зал (пол 183, кровля 190)
ROOF = 190
SPIRAL_TOP = 24             # винтовая лестница — до пола этажа 24 (Y 163), выше — проём
RING = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]   # по ходу подъёма
GLASS, BAND, FLOOR, LOBBY = 'stained_glass:3', 'concrete:0', 'concrete:0', 'quartz_block'
LAD_SE, ATT_SE = (4, 4), (5, 4)
LAD_NW, ATT_NW = (-4, -4), (-5, -4)
RISER = (5, 5)
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'city-4-opener.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'city-4-preview.png'))
    return p.parse_args()


def slab_y(k): return F0 + 4 * k if k <= NST else ROOF


def storey_fp(k):
    """Сечение этажа k (0…29) — форма плана на середине этажа, в смещениях (dx, dz) от центра."""
    ym = slab_y(k) + 2 if k < NST else 186
    return {(dx, dz) for dx in range(-6, 7) for dz in range(-6, 7) if P.t_opener(CX + dx, ym, CZ + dz)}


def ladder_meta(dx, dz): return {(0, -1): 3, (0, 1): 2, (-1, 0): 5, (1, 0): 4}[(dx, dz)]


def build(W):
    cells = {}

    def put(dx, y, dz, b): cells[(CX + dx, y, CZ + dz)] = b
    FP = [storey_fp(k) for k in range(NST + 1)]
    # фундамент: пол холла на Y 67, под ним камень до грунта; всё выше грунта в габарите — расчистка
    for dx in range(-6, 7):
        for dz in range(-6, 7):
            g = W.surf(CX + dx, CZ + dz)
            for y in range(g + 1, F0): put(dx, y, dz, 'stone')
    # этажи: перекрытие k = FP(k) ∪ FP(k−1); стены и воздух — по FP(k)
    for k in range(NST + 1):
        y0 = slab_y(k)
        slab = FP[k] | (FP[k - 1] if k else set())
        for (dx, dz) in slab:
            edge = any((dx + a, dz + b) not in slab for a, b in N4)
            put(dx, y0, dz, BAND if edge else (LOBBY if k == 0 else FLOOR))
        top = slab_y(k + 1) if k < NST else ROOF
        for (dx, dz) in FP[k]:
            edge = any((dx + a, dz + b) not in FP[k] for a, b in N4)
            for y in range(y0 + 1, top): put(dx, y, dz, GLASS if edge else 'air')
    for (dx, dz) in FP[NST]:                                  # кровля смотрового зала и парапет
        put(dx, ROOF, dz, BAND)
        if any((dx + a, dz + b) not in FP[NST] for a, b in N4): put(dx, ROOF + 1, dz, 'stone_slab:7')
    # свет: морские фонари в перекрытиях сеткой 4×4 (не у лестниц, шахты, фасада)
    busy = set(RING) | {(0, 0), LAD_SE, ATT_SE, LAD_NW, ATT_NW, RISER}
    for k in range(1, NST + 1):
        both = FP[k] & FP[k - 1]
        for (dx, dz) in both:
            if dx % 4 == 2 and dz % 4 == 2 and (dx, dz) not in busy and \
                    all((dx + a, dz + b) in both for a, b in N4):
                put(dx, slab_y(k), dz, 'sea_lantern')
    # винтовая лестница: столб в центре, 8 ступеней по полблока на этаж (ступень j на высоте L+0.5(j+1))
    for y in range(F0 + 1, slab_y(SPIRAL_TOP) + 4): put(0, y, 0, BAND)
    for k in range(SPIRAL_TOP + 1):                            # проём в перекрытиях над кольцом
        if k == 0: continue
        for (dx, dz) in RING[:-1]: put(dx, slab_y(k), dz, 'air')
    for k in range(SPIRAL_TOP):
        L = slab_y(k) + 1
        for j, (dx, dz) in enumerate(RING):
            h = L + 0.5 * (j + 1)
            if h == int(h): put(dx, int(h) - 1, dz, BAND)
            else: put(dx, int(h), dz, 'stone_slab')
    # стремянки в ногах проёма (крепятся к бетонной полосе)
    for (lad, att, y_lo) in ((LAD_SE, ATT_SE, slab_y(SPIRAL_TOP) + 1), (LAD_NW, ATT_NW, slab_y(SPIRAL_TOP) + 1)):
        m = ladder_meta(att[0] - lad[0], att[1] - lad[1])
        for y in range(y_lo, slab_y(NST) + 1):
            put(att[0], y, att[1], BAND)
            put(lad[0], y, lad[1], f'ladder:{m}')
    # холл: двери, щитовая, серверная, шахта
    doors = []

    def door(dx, dz, meta, inside):
        put(dx, F0 + 1, dz, f'birch_door:{meta}'); put(dx, F0 + 2, dz, 'birch_door:8')
        put(inside[0], F0 + 1, inside[1], 'stone_pressure_plate')
        doors.append((CX + dx, F0 + 1, CZ + dz, meta))
    door(0, 6, 3, (0, 5))                                      # юг — к проспекту
    door(-6, 0, 0, (-5, 0))                                    # запад — к дорожке
    for y in (F0 + 1, F0 + 2, F0 + 3):                         # стены комнат (белый бетон)
        for dz in range(-2, 6): put(2, y, dz, BAND)
        for dx in range(3, 6): put(dx, y, -2, BAND); put(dx, y, 2, BAND)
    for (dx, dz, meta, a, b) in ((2, 4, 2, (3, 4), (1, 4)), (4, -2, 1, (4, -1), (4, -3))):   # внутр. двери
        put(dx, F0 + 1, dz, f'birch_door:{meta}'); put(dx, F0 + 2, dz, 'birch_door:8')
        put(a[0], F0 + 1, a[1], 'stone_pressure_plate'); put(b[0], F0 + 1, b[1], 'stone_pressure_plate')
    put(4, F0 + 3, 2, 'air')                                   # кабель: щитовая → серверная
    put(3, F0 + 2, -2, 'air')                                  # проём к терминалу МЭ
    sx, sz = RISER
    for y in range(60, F0): put(sx, y, sz, 'air')
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            if (a, b) != (0, 0):
                for y in range(59, F0):
                    k_ = (CX + sx + a, y, CZ + sz + b)
                    if cells.get(k_, W.block(*k_)) in ('air', 'plant', 'water'): put(sx + a, y, sz + b, 'stonebrick')
    for k in range(SPIRAL_TOP + 1):
        if RISER in FP[k] and (k == 0 or RISER in FP[k - 1]): put(sx, slab_y(k), sz, 'iron_trapdoor:8')
    # предплощадки: юг Z 1810…1811 (X −764…−752), запад X −766…−765 (Z 1797…1811) — вровень с порогом
    pads = [(x, z) for x in range(-764, -751) for z in (1810, 1811)] + [(x, z) for x in (-766, -765) for z in range(1797, 1812)]
    for (x, z) in pads:
        g = W.surf(x, z)
        for y in range(g + 1, F0): cells[(x, y, z)] = 'stone'
        cells[(x, F0, z)] = 'double_stone_slab:8'
        for y in range(F0 + 1, max(g, F0) + 3):
            if W.block(x, y, z) in ('plant',) or y <= g: cells[(x, y, z)] = 'air'
    return cells, FP, doors


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before('city-4-opener.json')) if 'city-4-opener.json' in names else World()
    cells, FP, doors = build(W)
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    o = (min(xs), min(ys), min(zs))
    rel = {(x - o[0], y - o[1], z - o[2]): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print(f'city-4-opener.json: origin {o[0]} {o[1]} {o[2]} | габарит {max(xs) - o[0] + 1} {max(ys) - o[1] + 1} '
          f'{max(zs) - o[2] + 1} | записей {len(cells)}')
    print(f'этажей {NST} + смотровой зал (пол {slab_y(NST)}, кровля {ROOF}); сечение: этаж 0 — {len(FP[0])} кл., '
          f'этаж 24 — {len(FP[24])}, этажи 25–28 (ноги проёма) — {min(len(FP[k]) for k in range(25, 29))}…'
          f'{max(len(FP[k]) for k in range(25, 29))}, зал — {len(FP[NST])}')

    def final(x, y, z):
        b = cells.get((x, y, z)) or W.block(x, y, z)
        return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)

    def terr(x, y, z):
        b = W.block(x + o[0], y + o[1], z + o[2])
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
    print('== ПРОВЕРКИ ==')
    errs = dl.check_water(rel, terr)
    se, wr = dl.check_supports(rel, order, terr)
    print('опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок', len(errs) + len(se), '| предупреждений', len(wr))
    for m in (errs + se + wr)[:8]: print('   ', m)
    # форма против плана: этажи-призмы по сечению на середине этажа — расхождение только ступенчатостью
    kof = lambda y: min(NST, max(0, (y - F0 - 1) // 4))
    occ = {(x, y, z) for x in range(CX - 6, CX + 7) for z in range(CZ - 6, CZ + 7) for y in range(F0 + 1, ROOF)
           if P.t_opener(x, y, z)}
    env = {(CX + dx, y, CZ + dz) for y in range(F0 + 1, ROOF) for (dx, dz) in FP[kof(y)]}
    far = [p for p in occ ^ env if not any((p[0] + a, p[1], p[2] + b) in (env if p in occ else occ) for a, b in N4)]
    print(f'форма против плана (P.t_opener): объём плана {len(occ)}, здания {len(env)}, расхождение ступенчатостью '
          f'{len(occ ^ env)}, дальше соседней клетки — {len(far)}')
    di = door_approach_issues(final, doors)
    print('подходы к наружным дверям:', len(doors), 'дверей, ошибок', len(di), di[:3])
    roofs = [(W.surf(x, z) - W.cave_top(x, z), x, z) for x in range(CX - 7, CX + 8) for z in range(CZ - 7, CZ + 9)
             if W.cave_top(x, z) is not None]
    print('кровля каньона под башней: мин.', min(roofs)[0] if roofs else '—', '(норма >= 3); шахта кабеля до Y 60')
    # проходимость
    box = ((CX - 9, CX + 9), (CZ - 7, CZ + 10), (58, ROOF + 3))
    start = (CX, 68.0, 1812)

    def walk(fin): return dl.walk_reachable(fin, start, *box)
    seen = walk(final)
    targets = {'холл (с тротуара проспекта через южную дверь)': (CX, 68, CZ + 4),
               'щитовая': (CX + 4, 68, CZ + 4), 'серверная МЭ': (CX + 4, 68, CZ),
               'западная дверь снаружи (дорожка)': (-765, 68, 1803)}
    for k in range(1, SPIRAL_TOP + 1):
        targets[f'этаж {k}'] = (CX - 3, slab_y(k) + 1, CZ)
    for k in range(SPIRAL_TOP + 1, NST):
        targets[f'этаж {k}, ЮВ нога'] = (CX + 5, slab_y(k) + 1, CZ + 5)
        targets[f'этаж {k}, СЗ нога'] = (CX - 5, slab_y(k) + 1, CZ - 5)
    targets['смотровой зал'] = (CX, slab_y(NST) + 1, CZ)
    bad = 0
    for kname, (x, y, z) in targets.items():
        ok = dl.reached(seen, x, y, z); bad += 0 if ok else 1
        if not ok or kname in ('холл (с тротуара проспекта через южную дверь)', 'щитовая', 'серверная МЭ', 'этаж 12',
                               'этаж 24', 'смотровой зал', 'этаж 26, ЮВ нога', 'этаж 26, СЗ нога'):
            print(f'  маршрут → {kname}: {ok}')
    print(f'  (всего маршрутов {len(targets)})')
    print('ИТОГО недостижимых точек:', bad)
    # негатив: одна ступень винтовой лестницы на этаже 10 убрана — выше этажа 10 не попасть
    neg = dict(cells)
    L = slab_y(10) + 1
    dx, dz = RING[3]; h = L + 0.5 * 4
    neg[(CX + dx, int(h) - 1 if h == int(h) else int(h), CZ + dz)] = 'air'
    s2 = walk(lambda x, y, z: (lambda b: 'air' if b == 'plant' else ('stone' if b == 'ground' else b))(neg.get((x, y, z)) or W.block(x, y, z)))
    print('НЕГАТИВ: убрана ступень лестницы на этаже 10 — этаж 11 недостижим:', not dl.reached(s2, CX - 3, slab_y(11) + 1, CZ))
    if args.preview: preview(args.preview, final)


def preview(path, final):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    CX2 = dict(CL); CX2.update({'stained_glass:3': (150, 200, 235), 'concrete:0': (235, 235, 235), 'quartz_block': (240, 238, 232),
                                'double_stone_slab:8': (170, 170, 170), 'stone_slab': (160, 160, 160), 'ladder': (160, 125, 80)})
    cc = lambda b: CX2.get(b) or CX2.get(b.split(':')[0]) or col(b)
    S2 = 4
    H_ = ROOF + 3 - 60
    img = Image.new('RGB', (1500, H_ * S2 + 80), 'white')
    dr = ImageDraw.Draw(img)
    dr.text((10, 4), 'Сити, этап 4 — Т1 «Открывашка»: фасад с юга, фасад с востока, разрезы по оси X и по диагонали, планы этажей 0, 12, 24, 26, 29',
            fill='black', font=F(12))

    def elev(ox, label, cols, fn):
        dr.text((ox, 22), label, fill='black', font=F(11))
        for u, c in enumerate(cols):
            for y in range(60, ROOF + 3):
                b = fn(c, y)
                if not b or b == 'air': continue
                yy = 40 + (ROOF + 2 - y) * S2
                n = b.split(':')[0]
                half = n in ('stone_slab',) and int((b.split(':') + ['0'])[1]) < 8
                dr.rectangle([ox + u * S2, yy + (S2 // 2 if half else 0), ox + (u + 1) * S2 - 1, yy + S2 - 1],
                             fill=(150, 140, 110) if b == 'stone' else cc(b))
    xs = list(range(CX - 8, CX + 9)); zs = list(range(CZ - 8, CZ + 11))

    def front_s(x, y):
        for z in range(CZ + 10, CZ - 9, -1):
            b = final(x, y, z)
            if b not in ('air',) and not (b == 'stone' and y < 67): return b
        return None

    def front_e(z, y):
        for x in range(CX + 9, CX - 9, -1):
            b = final(x, y, z)
            if b not in ('air',) and not (b == 'stone' and y < 67): return b
        return None
    elev(10, 'фасад с юга', xs, front_s)
    elev(110, 'фасад с востока', zs, front_e)
    elev(220, 'разрез X=−758', zs, lambda z, y: final(CX, y, z))
    diag = [(CX + d, CZ + d) for d in range(-7, 8)]
    elev(320, 'разрез по диагонали', list(range(len(diag))), lambda u, y: final(diag[u][0], y, diag[u][1]))
    ox = 420
    for k, lab in ((0, 'этаж 0 (холл)'), (12, 'этаж 12'), (24, 'этаж 24'), (26, 'этаж 26 (ноги)'), (NST, 'смотровой зал')):
        y = slab_y(k) + 1
        dr.text((ox, 22), lab, fill='black', font=F(11))
        S3 = 12
        for x in range(CX - 7, CX + 8):
            for z in range(CZ - 7, CZ + 10):
                b = final(x, y, z)
                if b == 'air': b = final(x, y - 1, z); c = tuple(int(v * 0.8) for v in cc(b)) if b not in ('air',) else (255, 255, 255)
                else: c = cc(b)
                if b == 'stone': c = (150, 140, 110)
                dr.rectangle([ox + (x - CX + 7) * S3, 40 + (z - CZ + 7) * S3, ox + (x - CX + 8) * S3 - 1, 40 + (z - CZ + 8) * S3 - 1], fill=c)
        ox += 16 * 12 + 18
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
