"""Сити, этапы 5–7 (CITY.md §7.4) — башни на ровной земле, по одной схеме на здание, с дорожками:

- city-5-gate.json   — Т2 «Ворота» (две наклонённые ноги, подиум, перемычка; фасад — стекло с диагональной
                       решёткой), вертолётная площадка на кровле (Y 150, 9×9, «H» в круге, огни) и вертолёт
                       в воздухе; дорожка Z 1830 от площади;
- city-5-bridge.json — Т3 «Мост» (Биржа): две опоры, этажи на мосту над проездом, витражи (общественное
                       здание, CITY.md §6), электрощитовая и серверная МЭ на первом этаже моста; проезд
                       Z 1800…1804 — дорожка от аллеи к Пограничной;
- city-6-sail.json   — Т4 «Парус»: белый парус к морю, мачта до Y 175; дорожка X −786…−785;
- city-7-spiral.json — Т6 «Спираль»: этажи поворачиваются (оболочка точно по форме); предплощадка Z 1787;
- city-7-decks.json  — Т7 «Три башни» с палубой-парком на крыше (газон, деревья, стеклянное ограждение);
                       предплощадка Z 1786…1787;
- city-7-ring.json   — Т8 «Подкова»: кольцо плоскостью к морю (оболочка точно по форме); променад Z 1848
                       и проход в подпорной стенке к улице-набережной (X −738…−736).
«Галька», площадка «Вершина» и шар (этап 6, холм) — следующей порцией.

Общее (city_lib.Tower): этажи по 4 блока — призмы по сечению формы (у «Ворот», «Спирали», «Подковы» —
оболочка точно по форме на каждой высоте); перекрытия — белый бетон, холл — кварц; морские фонари
в перекрытиях сеткой 4×4; стремянки — автоматически к каждой части каждого этажа (и на кровлю, где по
ней ходят); в каждом здании электрощитовая 3×3 с кабельной шахтой от Y 60 (люки iron_trapdoor:8),
в Бирже ещё серверная МЭ; наружные двери — плита только изнутри; дорожки — шаг ≤ 0.5.

Запуск: gen_city_5.py [--outdir schemas] [--preview docs/districts/city-5-preview.png]
Проверки (по каждой схеме): опоры + вода + порядок (decor_lib), проходимость без прыжков от улиц
до каждого этажа (каждой части), кровель с доступом, щитовых и серверной; подходы к дверям; перепад
дорожек; кровля каньона; вертолётная площадка свободна; негатив.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import *  # noqa: E402,F401,F403
import plan_city_v1 as P  # noqa: E402

TOW = {t[0]: t for t in P.TOWERS}
NAMES = ['city-5-gate.json', 'city-5-bridge.json', 'city-6-sail.json', 'city-7-spiral.json', 'city-7-decks.json',
         'city-7-ring.json']


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'city-5-preview.png'))
    return p.parse_args()


def box_of(k, m=1):
    t = TOW[k]; return (t[2] - m, t[3] + m, t[4] - m, t[5] + m)


def gate_glass(x, y, z):
    u = x + z
    return 'concrete:7' if (u + y) % 6 == 0 or (u - y) % 6 == 0 else 'stained_glass:3'


def bridge_glass(x, y, z):
    if y % 4 == 3: return 'quartz_block'
    return 'stained_glass_pane:' + str((3, 11, 0, 9)[((x + z) // 2 + y // 4) % 4])


def spec(W):
    """Здания: (схема, Tower, дорожки {клетки}, фиксированные высоты дорожек {клетка: h}, старт проходимости, доп.)"""
    out = []
    # --- Т2 «Ворота» ---
    T = Tower(W, 'Ворота', P.t_gate, box_of('t2'), 67, 150, glass_fn=gate_glass, exact=True, roof_walk=True)
    T.shell()
    T.door(-750, 1831, 1); T.door(-749, 1831, 1)
    T.room('щитовая «Ворот»', (-755, -753, 1832, 1834), (-752, 1833, 2), shaft=(-755, 1832))
    hx0, hx1, hz0, hz1, hy = P.HELIPAD
    for x in range(hx0, hx1 + 1):                            # вертолётная площадка вровень с кровлей
        for z in range(hz0, hz1 + 1):
            r = math.hypot(x - (hx0 + hx1) / 2, z - (hz0 + hz1) / 2)
            u, v = x - (hx0 + 4), z - (hz0 + 4)
            H_ = (abs(u) == 2 and abs(v) <= 2) or (v == 0 and abs(u) <= 2)
            b = 'concrete:0' if H_ else ('concrete:4' if 3.2 <= r <= 4.2 else 'concrete:15')
            if (x in (hx0, hx1)) and (z in (hz0, hz1)): b = 'sea_lantern'
            T.put(x, hy - 1, z, b)
            for y in (hy, hy + 1): T.put(x, y, z, 'air')
    for (x, y, z) in P.HELI:                                  # вертолёт — висит статично
        dy = y - 161
        T.put(x, y, z, 'concrete:15' if dy >= 3 or dy == -1 else ('stained_glass:3' if x <= -745 and dy in (1, 2) else 'concrete:11'))
    paths = {(x, 1830) for x in range(-756, -729)}
    out.append(('city-5-gate.json', T, paths, (-750, 68.0, 1829), {}))
    # --- Т3 «Мост» (Биржа) ---
    T = Tower(W, 'Биржа', P.t_bridge, box_of('t3'), 67, 100, glass_fn=bridge_glass, band='quartz_block', exact=True)
    T.shell()
    T.door(-735, 1799, 3); T.door(-735, 1805, 1)
    T.room('электрощитовая Биржи', (-737, -735, 1797, 1799), (-734, 1798, 2), k=4, shaft=(-737, 1797),
           opening=[(-736, 3, 1800)])
    T.room('серверная МЭ', (-737, -735, 1801, 1803), (-734, 1802, 2), k=4, opening=[(-734, 2, 1803)])
    for y in range(T.ys[0], T.ys[4]):                         # шахта кабеля через северную опору до щитовой
        T.put(-737, y, 1797, 'air')
    for k in range(5): T.put(-737, T.ys[k], 1797, 'iron_trapdoor:8')
    T.reserved |= {(-737, 1797)}
    for k in range(4): T.res_k.setdefault(k, set()).add((-737, 1797))
    paths = {(x, z) for x in range(-739, -729) for z in range(1800, 1805)}
    out.append(('city-5-bridge.json', T, paths, (-741, 68.5, 1802), {}))
    # --- Т4 «Парус» ---
    T = Tower(W, 'Парус', P.t_sail, box_of('t4'), 66, 165, glass='stained_glass:0')
    T.shell()
    for x in range(-798, -784):
        for z in range(1820, 1836):
            for y in range(166, 176):
                if P.t_sail(x, y, z): T.put(x, y, z, 'concrete:0')     # мачта
    T.door(-787, 1827, 2); T.door(-787, 1828, 2)
    T.room('щитовая «Паруса»', (-796, -794, 1826, 1828), (-793, 1827, 2), shaft=(-796, 1826))
    paths = {(x, z) for x in (-786, -785) for z in range(1821, 1838)}
    out.append(('city-6-sail.json', T, paths, (-785, 67.0, 1820), {}))
    # --- Т6 «Спираль» ---
    T = Tower(W, 'Спираль', P.t_spiral, box_of('t6', 2), 67, 150, glass='stained_glass:9', exact=True)
    T.shell()
    T.door(-779, 1786, 3)
    T.room('щитовая «Спирали»', (-783, -781, 1780, 1782), (-780, 1781, 2), shaft=(-783, 1780))
    paths = {(x, 1787) for x in range(-785, -771)}
    out.append(('city-7-spiral.json', T, paths, (-772, 68.0, 1788), {}))
    # --- Т7 «Три башни» ---
    T = Tower(W, 'Три башни', P.t_deck, box_of('t7'), 67, 132, glass='stained_glass:11', roof_walk=True)
    T.shell()
    for a in (-764, -754, -744): T.door(a + 3, 1785, 3)
    T.room('щитовая «Трёх башен»', (-753, -751, 1778, 1780), (-752, 1781, 3), shaft=(-753, 1778))
    deck = T.FP[-1]
    for (x, z) in deck:                                       # палуба-парк: газон, деревья, стеклянное ограждение
        edge = any((x + a, z + b) not in deck for a, b in N4)
        if edge: T.put(x, 133, z, 'stained_glass_pane:0')
        else: T.put(x, 132, z, 'grass')
    for x in range(-762, -735, 6):
        if (x, 1781) in deck:
            T.put(x, 132, 1781, 'dirt')
            for y in (133, 134, 135): T.put(x, y, 1781, 'log:2')
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    T.put(x + a, 136, 1781 + b, 'leaves:6')
            T.put(x, 137, 1781, 'leaves:6')
    paths = {(x, z) for x in range(-766, -733) for z in (1786, 1787)}
    out.append(('city-7-decks.json', T, paths, (-750, 68.0, 1788), {}))
    # --- Т8 «Подкова» ---
    T = Tower(W, 'Подкова', P.t_ring, box_of('t8'), 68, 91, glass='stained_glass:11', exact=True)
    T.shell()
    T.door(-755, 1847, 3); T.door(-746, 1847, 3)            # две двери: комната делит холл на две части
    T.room('щитовая «Подковы»', (-752, -750, 1844, 1846), (-749, 1845, 2), shaft=(-751, 1846))
    paths = {(x, 1848) for x in range(-766, -729)} | {(x, 1849) for x in (-738, -737, -736)}
    out.append(('city-7-ring.json', T, paths, (-750, 65.0, 1851), {}))
    return out


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before(NAMES[0])) if NAMES[0] in names else World()
    total_bad = 0
    results = []
    for nm, T, paths, start, extra in spec(W):
        fixed = {}
        for (x, y, z, m) in T.doors:                          # перед дверью — вровень с порогом
            a, b = DOOR_IN[m]
            fixed[(x - a, z - b)] = float(y)
        skip = {(x, 1849) for x in range(-770, -725)} - paths          # верх подпорной стенки — не мощение
        H, anchors, bad = path_heights(W, paths | set(fixed), fixed, skip)
        pc = pave_cells(W, set(H), H)
        for k, v in pc.items():
            if T.cells.get(k) in (None, 'air'): T.cells[k] = v
        lost = T.plan_ladders()
        o, rel, order, dims = save_schema(T.cells, os.path.join(args.outdir, nm))
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(T.cells)} | '
              f'этажей {T.storeys()}, стремянок-звеньев {len(T.ladders)}, частей этажей без стремянки {lost}')
        cells = T.cells

        def final(x, y, z, cells=cells):
            b = cells.get((x, y, z)) or W.block(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)

        def terr(x, y, z, o=o):
            b = W.block(x + o[0], y + o[1], z + o[2])
            return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
        errs = dl.check_water(rel, terr)
        se, wr = dl.check_supports(rel, order, terr)
        print(f'{nm}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
        for m in (errs + se + wr)[:4]: print('   ', m)
        print(f'{nm}: перепад дорожек между соседями > 0.5 — {len(bad)}', bad[:3])
        di = door_approach_issues(final, T.doors)
        print(f'{nm}: подходы к наружным дверям: {len(T.doors)}, ошибок {len(di)}', di[:2])
        lo = {}
        for (x, y, z), b in cells.items():
            if b == 'air' and y <= W.surf(x, z): lo[(x, z)] = min(lo.get((x, z), 999), y)
        roofs = [y - W.cave_top(x, z) - 1 for (x, z), y in lo.items() if W.cave_top(x, z) is not None]
        print(f'{nm}: кровля каньона под выемками: мин. {min(roofs) if roofs else "—"} (норма >= 3)')
        xs = [k[0] for k in cells]; zs = [k[2] for k in cells]
        box = ((min(xs) - 3, max(xs) + 3), (min(zs) - 3, max(zs) + 4), (58, max(k[1] for k in cells) + 3))
        seen = dl.walk_reachable(final, start, *box)
        targets = T.level_targets(); targets.update(T.targets)
        for (x, y, z, m) in T.doors:
            a, b = DOOR_IN[m]; targets[f'{T.name}: перед дверью ({x},{z})'] = (x - a, y, z - b)
        bad_t = [k for k, (x, y, z) in targets.items() if not dl.reached(seen, x, y, z)]
        for k in bad_t[:8]: print(f'  маршрут → {k}: False')
        print(f'{nm}: маршрутов {len(targets)} (все этажи и их части, комнаты, двери), недостижимо {len(bad_t)}')
        total_bad += len(bad_t) + lost
        if nm == 'city-5-gate.json':
            hx0, hx1, hz0, hz1, hy = P.HELIPAD
            above = sum(1 for x in range(hx0, hx1 + 1) for z in range(hz0, hz1 + 1) for y in range(hy, hy + 8)
                        if final(x, y, z) != 'air')
            pad = dl.reached(seen, hx0 + 4, hy, hz0 + 4)
            print(f'{nm}: вертолётная площадка Y {hy}: над ней препятствий {above}, дойти с улицы — {pad}')
            total_bad += (0 if pad else 1) + (1 if above else 0)
        results.append((nm, T, final, H))
    print('ИТОГО недостижимых точек:', total_bad)
    # негатив: у «Спирали» убрано одно звено стремянки — верхние этажи недостижимы
    nm, T, final, H = results[3]
    x, z = T.ladders[len(T.ladders) // 2]
    lad = [k for k, b in T.cells.items() if b.startswith('ladder') and abs(k[0] - x) + abs(k[2] - z) == 1]
    neg = dict(T.cells)
    for k in lad: neg[k] = 'air'
    fin2 = lambda x, y, z: (lambda b: 'air' if b == 'plant' else ('stone' if b == 'ground' else b))(neg.get((x, y, z)) or W.block(x, y, z))
    s2 = dl.walk_reachable(fin2, (-772, 68.0, 1788), (-790, -768), (1772, 1792), (58, 155))
    tg = T.level_targets()
    miss = sum(1 for (x, y, z) in tg.values() if not dl.reached(s2, x, y, z))
    print('НЕГАТИВ: у «Спирали» убраны стремянки — недостижимые этажи найдены:', miss > 0)
    if args.preview: preview(args.preview, results, W)


def preview(path, results, W):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    CX = dict(CL); CX.update({'stained_glass:3': (150, 200, 235), 'stained_glass:0': (240, 245, 248), 'stained_glass:9': (90, 170, 175),
                              'stained_glass:11': (70, 100, 190), 'concrete:0': (235, 235, 235), 'concrete:7': (70, 75, 80),
                              'concrete:15': (25, 25, 25), 'concrete:4': (240, 200, 40), 'concrete:11': (40, 60, 150),
                              'quartz_block': (240, 238, 232), 'grass': (95, 150, 60), 'stained_glass_pane': (150, 180, 220)})
    cc = lambda b: CX.get(b) or CX.get(b.split(':')[0]) or col(b)
    allc = {}
    for nm, T, final, H in results: allc.update(T.cells)
    fin = lambda x, y, z: (lambda b: 'air' if b == 'plant' else ('stone' if b == 'ground' else b))(allc.get((x, y, z)) or W.block(x, y, z))
    X0, X1, Y0, Y1 = -800, -725, 60, 180
    S = 5
    img = Image.new('RGB', (max((X1 - X0 + 1) * S + 40, 560), (Y1 - Y0 + 1) * S + 40), 'white')
    dr = ImageDraw.Draw(img)
    dr.text((10, 4), 'Сити, этапы 5–7 (без холма): вид с моря (с юга), башни ближе к морю — поверх', fill='black', font=F(12))
    for x in range(X0, X1 + 1):
        for y in range(Y0, Y1 + 1):
            for z in range(1856, 1774, -1):
                b = fin(x, y, z)
                if b not in ('air', 'stone', 'ground', 'grass', 'water') and not b.startswith(('leaves', 'log', 'dark_oak_fence', 'sea_lantern', 'quartz_block:1', 'stone_slab:7')) or \
                        (b in ('grass',) and y > 100):
                    dr.rectangle([20 + (x - X0) * S, 30 + (Y1 - y) * S, 20 + (x - X0 + 1) * S - 1, 30 + (Y1 - y + 1) * S - 1], fill=cc(b))
                    break
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
