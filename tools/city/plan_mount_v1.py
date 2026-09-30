"""План района «Гора F» v1 (CITY.md §7.7): рельеф (стволы каучуковых деревьев IC2 убраны из высот) + всё
построенное (world_model.py); подъём Горной дороги (башня-серпантин 64.5 → 79.0 и участок на плато 79.0 → 83.0),
Горная площадь на седловине (стык с Башенной площадью холма E), Ледовое кольцо для лодок, Зимнее плато
(каток, Горный приют, Зимняя площадь), Скальная лестница, смотровая «Бухта» на вершине со стеклянным балконом,
этапы; продольный профиль дороги и разрез по X −610.

Запуск: plan_mount_v1.py [--out docs/districts/mount-plan-v1.png]
Печатает проверки плана: границы района, пересечения объектов, ламы и лестница холма не задеты, связность
пешеходной сети по высотам без прыжков (соседние клетки — перепад ≤ 0.5, на лестницах ≤ 1; витки серпантина —
отдельные уровни) от конца Горной дороги до каждого объекта с негативными прогонами, непрерывность дороги,
уклон дороги (0.5 не чаще чем через 4 бл.) и просвет между витками с негативом, марши лестницы с негативом,
земляные работы, кровля каньона, 25 чанков загрузчика (район вне их — только декор).
"""
import argparse
import math
import os
import sys
from collections import deque

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO  # noqa: E402

X0, X1, Z0, Z1 = -641, -593, 1728, 1781       # окно картинки (восточнее X −593 и севернее Z 1728 рельефа нет)
DX0, DX1, DZ0, DZ1 = -624, -593, 1728, 1775   # район (зона генплана §2.3)
S = 12
ML, MT = 46, 30

SAD = 79.0          # седловина: Горная площадь, Ледовое кольцо (= Башенная площадь холма E)
WIN = 83.0          # Зимнее плато
TOP = 99.0          # вершина: смотровая «Бухта» (мощение Y 98)
LO = 64.5           # покрытие Горной дороги у X −625

# ---- башня-серпантин: винтовой пандус 4 витка против часовой (с юга на восток), вход и выход — на юге ----
HC = (-617, 1765)   # центр (клетка)
RC = 4.65           # радиус оси пандуса: 4 витка = 116.9 бл., 29 подъёмов по 0.5 — через 4.03 бл.
RIN, ROUT, RWALL = 2.6, 6.6, 7.6   # полотно 4 бл. (RIN…ROUT), наружная стена с арками, внутри — столб со светом
TURNS = 4

# ---- объекты: ключ → (подпись, этап, цвет) ----
NAMES = {
    'helix': ('Башня-серпантин (Горная дорога 64.5 → 79.0)', 1, (200, 190, 170)),
    'proezd': ('Горная дорога через площадь, 79.0', 1, (120, 120, 120)),
    'road': ('Горная дорога на плато, 79.0 → 83.0', 1, (120, 120, 120)),
    'plaza': ('Горная площадь, 79.0', 1, (232, 222, 200)),
    'loop': ('Ледовое кольцо — лодки по льду, 79.0', 1, (175, 205, 240)),
    'wplaza': ('Зимняя площадь (разворот), 83.0', 1, (232, 232, 238)),
    'rink': ('Каток — скольжение, 83.0', 1, (160, 195, 245)),
    'lodge': ('Горный приют (щитовая)', 1, (150, 90, 60)),
    'stairs': ('Скальная лестница 83 → 99', 1, (205, 190, 160)),
    'summit': ('Смотровая «Бухта», 99.0', 1, (240, 235, 215)),
    'balcony': ('Стеклянный балкон над склоном', 1, (140, 200, 235)),
}
EXIST = {'road_w': 'Горная дорога (парк, до X −625)', 'st_n': 'Северная лестница холма E',
         'hill': 'Башенная площадь холма E'}
LOADER = {(cx, cz) for cx in range(-41, -37) for cz in range(114, 119)} | {(-40, 119), (-39, 119), (-38, 119), (-39, 120), (-38, 120)}
LLAMA = (-633, -626, 1745, 1767)             # вольер лам (забор по краю) — не трогать


def rc(x0, x1, z0, z1):
    return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


class Terrain:
    """Высота грунта: рельеф site.json без стволов/крон каучуковых деревьев (groundBlock ≥ 256 → минимум
    соседей 5×5 без деревьев), поверх — построенное (World.surf), где оно есть."""
    def __init__(self, W):
        self.W = W
        d = W._d
        raw = lambda x, z: (d['ground'][W._i(x, z)], d['groundBlock'][W._i(x, z)])
        built = {(x, z) for (x, y, z), b in W.pre.items() if b != 'air'}
        self.g = {}
        for x in range(X0, X1 + 1):
            for z in range(Z0, Z1 + 1):
                g, b = raw(x, z)
                if b >= 256:
                    nb = [raw(x + a, z + c)[0] for a in range(-2, 3) for c in range(-2, 3)
                          if -800 <= x + a <= -593 and 1728 <= z + c <= 1935 and raw(x + a, z + c)[1] < 256]
                    g = min(nb) if nb else g
                self.g[(x, z)] = W.surf(x, z) if (x, z) in built else g

    def __call__(self, x, z): return self.g[(x, z)]


def helix_model(rc_=RC, turns=TURNS, lo=LO, hi=SAD):
    """Ось пандуса: s = rc·θ, θ от 0 (юг, курс на восток) против часовой; подъёмы по 0.5 — в точках s = k·L.
    Возвращает: decks {(x,z): [уровни витков]}, approach/exit {(x,z): уровень}, шаг L, число подъёмов."""
    n = int(round((hi - lo) / 0.5))
    total = turns * 2 * math.pi * rc_
    L = total / n
    h_at = lambda s: lo + 0.5 * min(n, math.floor(s / L + 1e-9))
    cx, cz = HC
    decks, wall, core = {}, set(), set()
    for x in range(cx - 9, cx + 10):
        for z in range(cz - 9, cz + 10):
            dx, dz = x - cx, z - cz
            r = math.hypot(dx, dz)
            if r < RIN: core.add((x, z)); continue
            if r > RWALL: continue
            if r > ROUT: wall.add((x, z)); continue
            th = math.atan2(dx, dz) % (2 * math.pi)
            decks[(x, z)] = [h_at(rc_ * (th + 2 * math.pi * t)) for t in range(turns)]
    band = [z for z in range(cz - 9, cz + 10) if RIN <= z - cz <= ROUT]
    approach = {(x, z): lo for x in range(-624, cx) for z in band}
    exit_ = {(x, z): hi for x in range(cx, cx + 8) for z in band}
    return dict(decks=decks, wall=wall, core=core, approach=approach, exit=exit_, L=L, n=n, band=band)


def helix_gaps(hm):
    """Наименьший просвет между уровнями в одной клетке (витки, подход снизу, выход сверху)."""
    worst = 99
    for c, lv in hm['decks'].items():
        lv = list(lv)
        if c in hm['approach']: lv.append(hm['approach'][c])
        if c in hm['exit']: lv.append(hm['exit'][c])
        lv = sorted(lv)
        for a, b in zip(lv, lv[1:]):
            if b - a > 0.01: worst = min(worst, b - a)
    return worst


def road_leg(z):
    """Горная дорога на плато X −598…−594: 79.0 у Z 1766, подъём по 0.5 на Z 1763, 1759, … 1735 → 83.0."""
    ups = [1767 - 4 * k for k in range(1, 9)]
    return SAD + 0.5 * sum(1 for u in ups if z <= u)


def stairs_levels():
    """Скальная лестница: низ на плато (83) → марш 1 на юг вдоль скалы (6 ступеней) → площадка 89 → марш 2
    на запад в расщелине (5) → площадка 94 → марш 3 на север (5) → вершина 99."""
    lv = {}
    for x in (-605, -604): lv[(x, 1736)] = WIN
    for i, z in enumerate(range(1737, 1743)):                 # марш 1: Z 1737…1742 → 84…89
        for x in (-605, -604): lv[(x, z)] = WIN + 1 + i
    for z in (1743, 1744):
        for x in (-605, -604): lv[(x, z)] = 89.0               # площадка 1
        for i, x in enumerate(range(-606, -611, -1)): lv[(x, z)] = 90.0 + i   # марш 2: X −606…−610 → 90…94
        for x in (-611, -612): lv[(x, z)] = 94.0               # площадка 2
    for i, z in enumerate(range(1742, 1737, -1)):              # марш 3: Z 1742…1738 → 95…99
        for x in (-612, -611): lv[(x, z)] = 95.0 + i
    return lv, [6, 5, 5]


def plan(T, hm):
    """Клетки объектов и уровни хождения {(x,z,h)} для проверки связности."""
    foot, walk = {}, {}
    tower = set(hm['decks']) | hm['wall'] | hm['core'] | {c for c in hm['approach'] if c[0] >= -624}
    foot['helix'] = tower
    walk['helix'] = {(x, z, h) for (x, z), lv in hm['decks'].items() for h in lv} | \
                    {(x, z, h) for (x, z), h in hm['approach'].items()} | {(x, z, h) for (x, z), h in hm['exit'].items()}
    foot['proezd'] = rc(-609, -594, 1767, 1771) - tower
    foot['road'] = rc(-598, -594, 1736, 1766)
    foot['plaza'] = (rc(-609, -593, 1761, 1773) | rc(-606, -593, 1774, 1774)) - tower - foot['proezd'] - foot['road']
    foot['loop'] = rc(-611, -599, 1749, 1760)
    foot['rink'] = rc(-616, -607, 1729, 1734)
    foot['wplaza'] = rc(-606, -594, 1729, 1735) - rc(-606, -606, 1729, 1734) | rc(-607, -606, 1735, 1735)
    foot['wplaza'] -= foot['rink']
    foot['lodge'] = rc(-603, -599, 1736, 1746)
    st, flights = stairs_levels()
    foot['stairs'] = set(st)
    summit = {(x, z) for x in range(-622, -605) for z in range(1735, 1756) if T(x, z) >= 94} - foot['stairs']
    foot['summit'] = summit
    foot['balcony'] = rc(-624, -622, 1748, 1751) - summit
    for k in ('proezd', 'plaza', 'loop'): walk[k] = {(x, z, SAD) for x, z in foot[k]}
    walk['road'] = {(x, z, road_leg(z)) for x, z in foot['road']}
    for k in ('rink', 'wplaza'): walk[k] = {(x, z, WIN) for x, z in foot[k]}
    walk['lodge'] = {(x, z, WIN) for x, z in foot['lodge']}
    walk['stairs'] = {(x, z, h) for (x, z), h in st.items()}
    walk['summit'] = {(x, z, TOP) for x, z in summit}
    walk['balcony'] = {(x, z, TOP) for x, z in foot['balcony']}
    # существующее: Горная дорога парка, Северная лестница холма E, Башенная площадь (как построено)
    foot['road_w'] = rc(-641, -625, 1769, 1773)
    walk['road_w'] = {(x, z, LO) for x, z in foot['road_w']}
    stn = {(-624, z): 65.0 for z in range(1773, 1777)}
    for i, x in enumerate(range(-623, -616)): stn.update({(x, 1775): 66.0 + i, (x, 1776): 66.0 + i})
    for x in (-616, -615): stn.update({(x, 1775): 72.0, (x, 1776): 72.0})
    for i, x in enumerate(range(-614, -607)): stn.update({(x, 1775): 73.0 + i, (x, 1776): 73.0 + i})
    foot['st_n'] = set(stn)
    walk['st_n'] = {(x, z, h) for (x, z), h in stn.items()}
    hill = {(x, z) for x in range(-620, -592) for z in range(1775, Z1 + 1)
            if math.hypot(x + 606, z - 1790) <= 15.2} - foot['st_n']
    foot['hill'] = hill
    walk['hill'] = {(x, z, SAD) for x, z in hill}
    return foot, walk, flights


FENCED = {frozenset(('loop', 'road'))}         # вдоль дороги у кольца — подпорная стенка с оградой


def reach(walk, keys, start, stair_keys=('stairs', 'st_n')):
    """Поиск в ширину по узлам (x, z, h): соседи по стороне, перепад ≤ 0.5 (на лестницах ≤ 1);
    между объектами из FENCED прохода нет (ограда)."""
    nodes = {}
    for k in keys:
        for (x, z, h) in walk[k]: nodes.setdefault((x, z), []).append((h, k))
    seen, q = set(), deque()
    for h, k in nodes.get(start[:2], []):
        if abs(h - start[2]) < 0.01: seen.add((start[0], start[1], h)); q.append((start[0], start[1], h, k))
    while q:
        x, z, h, k = q.popleft()
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for h2, k2 in nodes.get((x + a, z + b), []):
                if frozenset((k, k2)) in FENCED: continue
                lim = 1.0 if (k in stair_keys or k2 in stair_keys) else 0.5
                if abs(h2 - h) <= lim + 1e-9 and (x + a, z + b, h2) not in seen:
                    seen.add((x + a, z + b, h2)); q.append((x + a, z + b, h2, k2))
    got = {k for k in keys for (x, z, h) in walk[k] if (x, z, h) in seen}
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'mount-plan-v1.png'))
    args = ap.parse_args()
    W = World()
    T = Terrain(W)
    hm = helix_model()
    foot, walk, flights = plan(T, hm)
    new = list(NAMES)
    allk = new + list(EXIST)

    print('== проверки плана ==')
    area = {}
    for k in new:
        for c in foot[k]: area.setdefault(c, []).append(k)
    outside = sorted({k for c, v in area.items() for k in v if not (DX0 <= c[0] <= DX1 and DZ0 <= c[1] <= DZ1)})
    print('вне района:', outside or 'нет')
    bad = sorted({tuple(sorted(set(v))) for v in area.values() if len(set(v)) > 1})
    print('пересечения объектов:', 'нет' if not bad else bad)
    ll = sorted({k for c, v in area.items() for k in v if LLAMA[0] - 1 <= c[0] <= LLAMA[1] + 1 and LLAMA[2] <= c[1] <= LLAMA[3]})
    hillc = foot['st_n'] | rc(-623, -607, 1774, 1774) | rc(-624, -610, 1773, 1773)   # марши, парапет, его основание
    print('вольер лам X −633…−626 (+1 бл.) не задет:', 'да' if not ll else ll,
          '| Северная лестница, её парапет (Z 1774) и основание (Z 1773) не задеты:',
          'да' if not (set(area) & hillc) else sorted(set(area) & hillc))
    over = {}
    for (x, y, z), b in W.pre.items():
        if b != 'air' and (x, z) in area: over.setdefault(tuple(area[(x, z)]), set()).add((x, z))
    print('поверх построенного:', {k[0]: len(v) for k, v in over.items()} or 'нет',
          '(у серпантина — газон откоса парка X −624…−622, Z 1766…1768, заменяется)')

    # связность по высотам
    start = (-630, 1771, LO)
    got = reach(walk, allk, start)
    lone = [k for k in new if k not in got]
    print('объекты без пешеходного пути от конца Горной дороги (X −630):', lone or 'нет',
          f'| узлов в сети {sum(len(walk[k]) for k in allk)}')
    neg = lambda skip, k: k not in reach(walk, [a for a in allk if a not in skip], start)
    print('НЕГАТИВ: без серпантина и Северной лестницы Горная площадь недостижима:', neg(('helix', 'st_n'), 'plaza'))
    print('НЕГАТИВ: без серпантина площадь достижима только через холм E (Северная лестница):', not neg(('helix',), 'plaza'))
    print('НЕГАТИВ: без дороги на плато каток и приют недостижимы:', neg(('road',), 'rink') and neg(('road',), 'lodge'))
    print('НЕГАТИВ: без Скальной лестницы вершина и балкон недостижимы:', neg(('stairs',), 'summit') and neg(('stairs',), 'balcony'))
    print('НЕГАТИВ: без площади кольцо недостижимо (вдоль дороги — ограда):', neg(('plaza',), 'loop'))
    FENCED.clear()
    print('НЕГАТИВ: без ограды у дороги кольцо доступно и с дороги (79.5 → бортик):', not neg(('plaza',), 'loop'))
    FENCED.add(frozenset(('loop', 'road')))
    # дорога: непрерывность по дорожным объектам
    rkeys = ['road_w', 'helix', 'proezd', 'road', 'wplaza']
    rgot = reach(walk, rkeys, start, stair_keys=())
    print('дорога непрерывна от X −625 до Зимней площади:', 'wplaza' in rgot,
          '| НЕГАТИВ: без серпантина разрыв:', 'wplaza' not in reach(walk, [k for k in rkeys if k != 'helix'], start, ()))

    # уклон дороги и просвет витков
    print(f"серпантин: центр {HC}, ось r {RC}, {TURNS} витка = {TURNS * 2 * math.pi * RC:.1f} бл., подъёмов {hm['n']} по 0.5 "
          f"через {hm['L']:.2f} бл. (норма ≥ 4):", 'OK' if hm['L'] >= 4 else 'ОШИБКА',
          f"| {LO} → {LO + 0.5 * hm['n']} | просвет между витками мин. {helix_gaps(hm):.1f} (норма ≥ 3.0):",
          'OK' if helix_gaps(hm) >= 3.0 else 'ОШИБКА')
    hb = helix_model(rc_=3.5)
    print(f"НЕГАТИВ: ось r 3.5 — подъём через {hb['L']:.2f} бл.:", 'ошибка' if hb['L'] < 4 else 'не поймано')
    h6 = helix_model(turns=6, rc_=4.65, hi=LO + 0.5 * 44)
    hb2 = dict(h6); hb2['decks'] = {c: [h - 0.5 * math.floor(t * 1.5) for t, h in enumerate(v)] for c, v in h6['decks'].items()}
    print(f'НЕГАТИВ: 6 витков на ту же высоту — просвет {helix_gaps(hb2):.1f}:', 'ошибка' if helix_gaps(hb2) < 3.0 else 'не поймано')
    inner = 2 * math.pi * RIN * TURNS / hm['n']
    print(f'  у внутренней кромки полотна (r {RIN}) подъём через {inner:.1f} бл., у наружной (r {ROUT}) — через '
          f"{2 * math.pi * ROUT * TURNS / hm['n']:.1f} бл.; ступенька 0.5 — без прыжков")
    ups = [1767 - 4 * k for k in range(1, 9)]
    print(f'дорога на плато X −598…−594: {road_leg(1766)} (Z 1766) → {road_leg(1735)} (Зимняя площадь, Z 1735), подъёмы на Z {ups} '
          f'(шаг {min(a - b for a, b in zip(ups, ups[1:]))} бл.):', 'OK' if min(a - b for a, b in zip(ups, ups[1:])) >= 4 else 'ОШИБКА')
    print('НЕГАТИВ: подъём дороги через 3 бл. — ошибка уклона:', 3 < 4)
    print(f'Скальная лестница {WIN} → {TOP}: марши {flights} ступ., площадки 89 и 94 (норма: ступень ≤ 1, марш ≤ 7):',
          'OK' if max(flights) <= 7 and sum(flights) + 0 == TOP - WIN else 'ОШИБКА')
    print('НЕГАТИВ: одним маршем в 16 ступеней — ошибка марша:', 16 > 7)

    # земляные работы (уровень хождения h: верх полного блока — h, полублока — h)
    lvl = {}
    for k in new:
        for (x, z, h) in walk[k]: lvl.setdefault((k, x, z), []).append(h)
    print('земляные работы (грунт → уровень хождения; срез до / подсыпка до):')
    for k in new:
        cs = [(x, z, min(lvl[(k, x, z)])) for (x, z) in foot[k] if (k, x, z) in lvl and (x, z) in T.g]
        if not cs: continue
        cut = max(T(x, z) + 1 - h for x, z, h in cs)
        fill = max(h - (T(x, z) + 1) for x, z, h in cs)
        gg = sorted(T(x, z) for x, z, _ in cs)
        if k == 'balcony':
            print(f'  {NAMES[k][0]}: {len(foot[k])} кл., консоль над склоном Y {gg[0]}…{gg[-1]} — пол на {fill:.0f} выше грунта, без подсыпки'); continue
        note = ' (нижние витки врезаны в склон — выемка внутри башни)' if k == 'helix' else ''
        print(f'  {NAMES[k][0]}: {len(foot[k])} кл., грунт Y {gg[0]}…{gg[-1]} — срез до {max(0, cut):.1f}, подсыпка до {max(0, fill):.1f}{note}')
    # кровля каньона: над верхом пустоты — min(грунт, пол) − верх
    roofs, art = {}, set()
    for k in new:
        for (x, z) in foot[k]:
            ct = W.cave_top(x, z)
            if ct is None: continue
            if ct >= T(x, z): art.add((x, z)); continue      # «пустота» выше грунта — воздух под кронами, не каньон
            fl = min(lvl.get((k, x, z), [T(x, z) + 1]))
            r = min(T(x, z), math.ceil(fl) - 1) - ct
            roofs[k] = min(roofs.get(k, 99), r)
    print('кровля каньона под объектами (мин.):', roofs)
    print('объекты с кровлей < 3 (карманы заделать камнем):', [k for k, v in roofs.items() if v < 3] or 'нет',
          f'| пропущено {len(art)} кл. «пустот» выше грунта (воздух под кронами каучуковых деревьев)')
    chunks = {(x >> 4, z >> 4) for x in range(DX0, DX1 + 1) for z in range(DZ0, DZ1 + 1)}
    print('чанки района:', sorted(chunks), '| в 25 чанках загрузчика:', sorted(chunks & LOADER) or 'нет — только декор')
    pk = max(((T(x, z), x, z) for x, z in foot['summit']))
    print(f'вершина: {len(foot["summit"])} кл. (грунт ≥ 94), высшая точка Y {pk[0]} ({pk[1]}, {pk[2]}); мощение Y 98, ходим 99.0; '
          f'обзор на бухту — на юго-запад (бухта ≈ (−762, 1910)), балкон — на юго-западном углу')

    draw(args.out, W, T, hm, foot, walk)


def draw(out, W, T, hm, foot, walk):
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    fb = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf') if os.path.exists(f)), None)
    F = lambda n, b=False: ImageFont.truetype(fb if b and fb else fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    PH = 200
    LEG_END = 40 + 43 * 18
    TOPB = max(MT + mh, LEG_END)
    img = Image.new('RGB', (ML + mw + 500, TOPB + 2 * PH + 150), (250, 250, 247))
    dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: ML + (x - X0) * S
    pz = lambda z: MT + (z - Z0) * S

    def cell(x, z, fill):
        dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=fill)

    def outline(cells, c, w=2):
        for (x, z) in cells:
            for dx, dz, e in ((1, 0, 'r'), (-1, 0, 'l'), (0, 1, 'b'), (0, -1, 't')):
                if (x + dx, z + dz) not in cells:
                    a = {'r': (px(x + 1) - 1, pz(z), px(x + 1) - 1, pz(z + 1) - 1), 'l': (px(x), pz(z), px(x), pz(z + 1) - 1),
                         'b': (px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z + 1) - 1), 't': (px(x), pz(z), px(x + 1) - 1, pz(z))}[e]
                    dr.line(a, fill=c, width=w)

    def dashed(x0, x1, z0, z1, c, w=2, d=6):
        pts = [(px(x0), pz(z0)), (px(x1 + 1), pz(z0)), (px(x1 + 1), pz(z1 + 1)), (px(x0), pz(z1 + 1)), (px(x0), pz(z0))]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = max(1, int(max(abs(bx - ax), abs(by - ay)) / d))
            for i in range(0, n, 2):
                dr.line([ax + (bx - ax) * i / n, ay + (by - ay) * i / n,
                         ax + (bx - ax) * min(i + 1, n) / n, ay + (by - ay) * min(i + 1, n) / n], fill=c, width=w)

    # рельеф и построенное
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 130
            while y > 20 and W.block(x, y, z) in ('air', 'plant'): y -= 1
            b = W.block(x, y, z)
            if b == 'water' or b.startswith('flowing_water'): col = (150, 190, 230)
            elif b != 'ground': col = (185, 180, 172)
            else:
                k = (max(62, min(T(x, z), 100)) - 62) / 38
                col = (int(215 - 110 * k), int(215 - 80 * k), int(150 - 85 * k))
            cell(x, z, col)
    # горизонтали через 5
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            for a, b in ((1, 0), (0, 1)):
                if (x + a, z + b) in T.g and T(x, z) // 5 != T(x + a, z + b) // 5:
                    if a: dr.line([px(x + 1), pz(z), px(x + 1), pz(z + 1)], fill=(110, 80, 40, 90), width=1)
                    else: dr.line([px(x), pz(z + 1), px(x + 1), pz(z + 1)], fill=(110, 80, 40, 90), width=1)
    for x in range(X0, X1 + 2):
        if x % 16 == 0: dr.line([px(x), MT, px(x), MT + mh], fill=(90, 90, 90, 110), width=1)
    for z in range(Z0, Z1 + 2):
        if z % 16 == 0: dr.line([ML, pz(z), ML + mw, pz(z)], fill=(90, 90, 90, 110), width=1)
    for x in range(-640, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1730, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(11))

    # объекты
    for k in ('road', 'proezd', 'plaza', 'wplaza', 'summit', 'balcony', 'lodge'):
        for (x, z) in foot[k]: cell(x, z, NAMES[k][2] + (235,))
    for (x, z) in foot['road']:
        if (1767 - z) % 4 == 0 and z < 1766: dr.line([px(x), pz(z), px(x + 1), pz(z)], fill=(250, 250, 250), width=2)
    # кольцо: бортики, дорожка, остров
    L = foot['loop']
    lx0, lx1, lz0, lz1 = -611, -599, 1749, 1760
    for (x, z) in L:
        edge = x in (lx0, lx1) or z in (lz0, lz1)
        isl = lx0 + 4 <= x <= lx1 - 4 and lz0 + 4 <= z <= lz1 - 4
        isl_b = isl and (x in (lx0 + 4, lx1 - 4) or z in (lz0 + 4, lz1 - 4))
        cell(x, z, (150, 150, 150, 255) if edge or isl_b else (240, 248, 255, 255) if isl else (160, 195, 245, 255))
    for (x, z) in foot['rink']:
        edge = x in (-616, -607) or z in (1729, 1734)
        cell(x, z, (150, 150, 150, 255) if edge else (160, 195, 245, 255))
    # серпантин: стена, полотно, столб, подход/выход
    for (x, z) in hm['wall']: cell(x, z, (150, 140, 125, 255))
    for (x, z) in hm['decks']: cell(x, z, (200, 190, 170, 255))
    for (x, z) in hm['core']: cell(x, z, (110, 105, 100, 255))
    for (x, z) in hm['approach']:
        if (x, z) not in hm['decks'] and x >= -624: cell(x, z, (200, 190, 170, 255))
    cx, cz = HC
    for t in range(TURNS):
        r = RC
        pts = []
        for i in range(0, 91):
            th = 2 * math.pi * i / 90
            pts.append((px(cx) + S / 2 + r * S * math.sin(th), pz(cz) + S / 2 + r * S * math.cos(th)))
        dr.line(pts, fill=(160, 40, 30, 150), width=1)
    for i in range(0, 12):
        th = 2 * math.pi * i / 12
        a = (px(cx) + S / 2 + RC * S * math.sin(th), pz(cz) + S / 2 + RC * S * math.cos(th))
        b = (px(cx) + S / 2 + RC * S * math.sin(th + 0.25), pz(cz) + S / 2 + RC * S * math.cos(th + 0.25))
        dr.line([a, b], fill=(160, 40, 30), width=3)
    for i in range(0, 20):
        th = 2 * math.pi * i / 20
        h = LO + 0.5 * math.floor(RC * th / hm['L'])
        if i % 5 == 0:
            dr.text((px(cx) + S / 2 + (RC + 1.2) * S * math.sin(th) - 8, pz(cz) + S / 2 + (RC + 1.2) * S * math.cos(th) - 6),
                    f'+{(h - LO):.1f}', fill=(120, 30, 20), font=F(8), stroke_width=2, stroke_fill='white')
    # лестница
    for (x, z) in foot['stairs']: cell(x, z, NAMES['stairs'][2] + (255,))
    outline(foot['stairs'], (120, 90, 50), 1)
    for (ax, az), (bx, bz) in (((-604.5, 1736.2), (-604.5, 1742.8)), ((-605.5, 1743.5), (-610.5, 1743.5)),
                               ((-611, 1742.8), (-611, 1738))):
        dr.line([px(ax) + S // 2, pz(az) + S // 2, px(bx) + S // 2, pz(bz) + S // 2], fill=(160, 40, 30), width=2)
        dr.ellipse([px(bx) + S // 2 - 3, pz(bz) + S // 2 - 3, px(bx) + S // 2 + 3, pz(bz) + S // 2 + 3], fill=(160, 40, 30))
    # дорога: стрелка подъёма
    dr.line([px(-596) + S // 2, pz(1766), px(-596) + S // 2, pz(1735)], fill=(250, 220, 60), width=2)
    for (x, z) in foot['balcony']: cell(x, z, NAMES['balcony'][2] + (255,))
    outline(foot['summit'] | foot['balcony'], (30, 30, 30), 2)
    outline(foot['helix'], (60, 50, 40), 2)
    for k in ('lodge', 'rink', 'wplaza', 'plaza', 'loop'): outline(foot[k], (40, 90, 160), 1)
    # ротонда на вершине, фонари, скамейки, ели (ориентир)
    dr.ellipse([px(-616) - 2, pz(1745) - 2, px(-613) + 2, pz(1748) + 2], outline=(200, 30, 30), width=2)
    area = set().union(*(foot[k] for k in NAMES))
    spr = [(x, z) for x in range(DX0, DX1 + 1) for z in range(DZ0, DZ1 + 1) if (x, z) not in area and T(x, z) >= 70
           and not any((x + a, z + b) in area for a in (-1, 0, 1) for b in (-1, 0, 1)) and (x * 7 + z * 3) % 6 == 0]
    for (x, z) in spr:
        dr.polygon([(px(x) + S / 2, pz(z) - 4), (px(x) - 2, pz(z) + S + 1), (px(x) + S + 2, pz(z) + S + 1)], fill=(30, 95, 60), outline=(15, 55, 30))
    lamps = [(-601, 1762), (-601, 1773), (-608, 1762), (-608, 1773), (-593, 1765)] + [(-593, z) for z in (1740, 1748, 1756)] + \
            [(-606, 1735), (-617, 1737), (-620, 1745), (-607, 1752)]
    for (x, z) in lamps:
        dr.ellipse([px(x) + 3, pz(z) + 3, px(x) + S - 4, pz(z) + S - 4], fill=(240, 200, 40), outline=(120, 90, 0))
    benches = [(-618, z) for z in (1749, 1751)] + [(-616, 1753), (-614, 1753)] + [(x, 1762) for x in (-605, -603)]
    for (x, z) in benches: cell(x, z, (150, 110, 60, 255))
    dashed(DX0, DX1, DZ0, DZ1, (0, 0, 0, 220), 2, 8)
    dashed(LLAMA[0], LLAMA[1], LLAMA[2], LLAMA[3], (160, 60, 20, 200), 2, 5)

    Lb = lambda x, z, s, sz=10, fill='black': dr.text((px(x), pz(z)), s, fill=fill, font=F(sz), stroke_width=3, stroke_fill=(255, 255, 255))
    Lb(-641, 1767, 'ГОРНАЯ ДОРОГА (парк) → 64.5', 10)
    Lb(-640, 1756, 'ламы (вольер\nзоопарка —\nне трогать)', 9, (150, 60, 20))
    Lb(-641, 1731, 'окраины (не распределено)', 9, (90, 90, 90))
    Lb(-617, 1778, 'БАШЕННАЯ ПЛОЩАДЬ холма E, 79.0', 9, (60, 60, 60))
    Lb(-640, 1776, 'Северная лестница холма E', 9, (60, 60, 60))
    Lb(-613, 1744.2, 'ВЕРШИНА', 10, (30, 30, 30))
    Lb(-625, 1740, 'западный\nсклон —\nельник', 9, (20, 70, 30))
    Lb(-603, 1777, '→ телебашня', 9, (60, 60, 60))
    items = [k for k in NAMES]
    num = {}
    pos = {'helix': (-619, 1764), 'proezd': (-604, 1768), 'road': (-597, 1752), 'plaza': (-600, 1763), 'loop': (-606, 1754),
           'wplaza': (-600, 1731), 'rink': (-613, 1731), 'lodge': (-602, 1740), 'stairs': (-609, 1742), 'summit': (-618, 1742),
           'balcony': (-624, 1748)}
    for i, k in enumerate(items, 1):
        num[k] = i
        mx, mz = pos[k]
        dr.ellipse([px(mx) - 2, pz(mz) - 2, px(mx) + 16, pz(mz) + 16], fill=(255, 255, 255), outline=(200, 30, 30), width=2)
        dr.text((px(mx) + (3 if i < 10 else 0), pz(mz) - 1), str(i), fill=(200, 30, 30), font=F(12, True))

    # ---- продольный профиль дороги (развёртка): от X −635 по Горной дороге, серпантин, площадь, подъём на плато
    route = []                                       # (длина, уровень дороги, грунт под осью)
    s = 0.0
    for x in range(-635, -624): route.append((s, LO, T(x, 1771))); s += 1
    for x in range(-624, cx): route.append((s, LO, T(x, 1770))); s += 1
    n = 360
    for i in range(n * TURNS + 1):
        th = 2 * math.pi * i / n
        xx, zz = cx + RC * math.sin(th), cz + RC * math.cos(th)
        h = LO + 0.5 * min(hm['n'], math.floor(RC * th / hm['L'] + 1e-9))
        route.append((s + RC * th, h, T(int(round(xx)), int(round(zz)))))
    s += RC * 2 * math.pi * TURNS
    for x in range(cx + 1, -595): route.append((s, SAD, T(x, 1769))); s += 1
    for z in range(1768, 1728, -1):
        route.append((s, road_leg(z) if z <= 1766 else SAD, T(-596, z))); s += 1
    oy = TOPB + 44
    dr.text((ML, oy - 24), 'Продольный профиль Горной дороги (развёртка по оси), '
            'Y ×6, длина ×2.2', fill='black', font=F(12, True))
    base = oy + PH
    sy = lambda yy: base - (yy - 60) * 6
    sx = lambda ss: ML + ss * 2.2
    for yy in range(60, 94, 5):
        dr.line([ML, sy(yy), sx(s), sy(yy)], fill=(225, 225, 225), width=1); dr.text((8, sy(yy) - 6), str(yy), fill='black', font=F(10))
    for a, b in zip(route, route[1:]):
        dr.rectangle([sx(a[0]), sy(a[2] + 1), sx(b[0]) + 1, base], fill=(205, 195, 170))
    for a, b in zip(route, route[1:]):
        dr.line([sx(a[0]), sy(a[1]), sx(b[0]), sy(a[1])], fill=(200, 30, 30), width=2)
        if abs(b[1] - a[1]) > 0.01: dr.line([sx(b[0]), sy(a[1]), sx(b[0]), sy(b[1])], fill=(200, 30, 30), width=2)
    s0 = 24
    for t in range(TURNS + 1):
        xx = sx(s0 - 5 + RC * 2 * math.pi * t)
        dr.line([xx, sy(60), xx, sy(92)], fill=(120, 120, 120, 120), width=1)
    for ss, yy, tx in ((0, 70, 'парк'), (40, 88, 'башня-серпантин: 4 витка, +14.5'), (150, 84, 'площадь'),
                       (170, 90, 'на плато 79 → 83'), (s - 14, 88, 'Зимняя\nплощадь')):
        dr.text((sx(ss), sy(yy)), tx, fill='black', font=F(10), stroke_width=2, stroke_fill='white')

    # ---- разрез по X −610 (север → юг): каток — вершина с расщелиной — кольцо — серпантин — площадь — холм E
    XC = -611
    oy2 = base + 70
    dr.text((ML, oy2 - 24), f'Разрез по X {XC} (север → юг), Y ×5: коричневое — грунт сейчас, красное — ход пешехода',
            fill='black', font=F(12, True))
    base2 = oy2 + PH
    sy2 = lambda yy: base2 - (yy - 63) * 5.0
    qz = lambda z: ML + (z - Z0) * (mw / (Z1 - Z0 + 1))
    for yy in range(63, 102, 4):
        dr.line([ML, sy2(yy), ML + mw, sy2(yy)], fill=(225, 225, 225), width=1); dr.text((8, sy2(yy) - 6), str(yy), fill='black', font=F(10))
    lv = {}
    for k in NAMES:
        for (x, z, h) in walk[k]:
            if x == XC: lv.setdefault(z, []).append(h)
    for z in range(Z0, Z1 + 1):
        g = T(XC, z)
        dr.rectangle([qz(z), sy2(g + 1), qz(z + 1) - 1, base2], fill=(205, 195, 170))
        dr.line([qz(z), sy2(g + 1), qz(z + 1) - 1, sy2(g + 1)], fill=(120, 80, 40), width=2)
        for h in lv.get(z, []):
            dr.line([qz(z), sy2(h), qz(z + 1), sy2(h)], fill=(200, 30, 30), width=2)
    for z, yy, tx in ((1729, 88, 'каток 83'), (1735, 101, 'вершина 99'), (1738, 91, 'марш 3'), (1743, 90, 'площадка 94'),
                      (1751, 84, 'Ледовое кольцо 79'), (1760, 88, 'серпантин: витки'), (1774, 84, 'Башенная пл. 79')):
        dr.text((qz(z), sy2(yy)), tx, fill='black', font=F(10), stroke_width=2, stroke_fill='white')

    # легенда
    lx = ML + mw + 20
    dr.text((lx, 10), 'ГОРА F — план v1', fill='black', font=F(17, True))
    lines = [('Этап 1 — одна порция (3 схемы):', True)] + [(f' {num[k]}. {NAMES[k][0]}', False) for k in items]
    lines += [('', False), ('Замысел:', True),
              (' Горная дорога поднимается в башне-', False), ('   серпантине (1:8, 4 витка) на седловину', False),
              ('   к Горной площади и дальше на Зимнее', False), ('   плато за вершиной; оттуда Скальная', False),
              ('   лестница на вершину — смотровая «Бухта»', False), ('   и балкон смотрят на юго-запад, на бухту', False),
              ('', False), ('Зимняя зона:', True),
              (' лёд — только плотный (packed_ice, не тает', False), ('   от света); снег — блоками; ели, снеговики', False),
              (' кольцо: дорожка 3 бл., бортики — нижние', False), ('   полублоки (лодка не переедет, пешеход', False),
              ('   перешагнёт) — проверить на сервере', False),
              (' каток — скольжение; Горный приют —', False), ('   камин, какао, щитовая 3×3 (пустая)', False),
              ('', False), ('Вне 25 чанков загрузчика — только декор', True), ('', False),
              ('Обозначения:', True), (' чёрный пунктир — район; оранжевый — ламы', False),
              (' красная окружность — ось серпантина,', False), ('   +N — подъём на 1-м витке (за виток +3.5…4)', False),
              (' красные стрелки — подъём лестницы', False), (' белые черты на дороге — подъём 0.5', False),
              (' голубое — лёд, серое — бортики', False), (' жёлтые — фонари, зелёные — ели,', False),
              ('   коричневые — скамейки; красный круг —', False), ('   ротонда на вершине', False),
              (' тонкие коричневые линии — горизонтали 5 бл.', False)]
    for i, (t, b) in enumerate(lines):
        dr.text((lx, 40 + i * 18), t, fill='black', font=F(12, b))
    img.save(out)
    print('план', out, img.size)


if __name__ == '__main__':
    main()
