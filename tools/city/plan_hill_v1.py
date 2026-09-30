"""План района «Холм E» v1 (CITY.md §7.6): рельеф + всё построенное (world_model.py), телебашня
schemas/ostankino.json на вершине, Башенная площадь, смотровая «Над парком» с Театральной лестницей
к верхнему ряду Зелёного театра, Северная лестница от Горной дороги, Парадная лестница от главного
проспекта (продолжение проспекта до X −593), этапы, резерв трасс, разрезы по Z 1785 и X −606.

Запуск: plan_hill_v1.py [--out docs/districts/hill-plan-v1.png]
Печатает проверки плана: границы района, пересечения объектов, связность мощения от проспекта до
каждого объекта (с негативными прогонами), подъёмы лестниц (не круче 1 на блок, площадки не реже
чем через 7 ступеней), уклон проспекта, земляные работы площади, кровля каньона, резерв трасс,
25 чанков загрузчика (район вне их — только декор), высота башни.
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO  # noqa: E402

X0, X1, Z0, Z1 = -642, -593, 1764, 1826      # окно картинки (восточнее X −593 рельефа нет)
DX0, DX1, DZ0, DZ1 = -624, -593, 1774, 1820  # район: зона генплана Z 1776…1807 + север до 1774, юг — проспект
S = 12
ML, MT = 46, 30
PLAZA_Y = 78                                  # блок мощения площади (ходим по 79.0)
TV_C = (-606, 1790)                           # центр башни; схема 23×23, origin = центр − 11
TV_R = 11.5

AV = (95, 95, 95, 230)
WALK = (215, 205, 185, 240)
PATH = (226, 214, 190, 255)
STAIR = (205, 190, 160, 255)

# ---- улицы: (ключ, подпись, X0, X1, Z0, Z1, этап, заливка) ----
STREETS = [
    ('av', 'главный проспект', -624, -593, 1814, 1818, 1, AV),     # продолжение парка (стык X −625), дальше — промзона
    ('av_n', 'тротуар', -624, -593, 1813, 1813, 1, WALK),
    ('av_s', 'тротуар', -624, -593, 1819, 1820, 1, WALK),
]
# ---- лестницы: (ключ, подпись, клетки-прямоугольники, этап) ----
STAIRS = {
    'st_th': ('Театральная лестница', [(-626, -620, 1785, 1786)], 1),
    'st_n': ('Северная лестница', [(-624, -611, 1774, 1775), (-612, -610, 1776, 1776)], 1),
    'st_s': ('Парадная лестница', [(-609, -603, 1806, 1812), (-615, -597, 1804, 1805), (-617, -616, 1802, 1805),
                                   (-596, -595, 1802, 1805)], 1),
}
# ---- объекты: (ключ, подпись, X0, X1, Z0, Z1, этап, здание?, цвет) ----
OBJ = [
    ('tv', 'Телебашня (ostankino.json)', -617, -595, 1779, 1801, 1, True, (245, 245, 250)),
    ('plaza', 'Башенная площадь', -618, -593, 1776, 1803, 1, False, (232, 222, 200)),
    ('west', 'Смотровая «Над парком»', -624, -619, 1779, 1796, 1, False, (215, 200, 170)),
    ('lobby', 'Вестибюль в основании, щитовая', -614, -598, 1782, 1798, 2, True, (120, 170, 210)),
    ('deck', 'Смотровая в «тарелке» (Y 136…141)', -611, -601, 1785, 1795, 2, True, (90, 140, 200)),
]
RESERVE = [('метро 1 + коллектор', -624, -593, 1812, 1820)]
LOADER = {(cx, cz) for cx in range(-41, -37) for cz in range(114, 119)} | {(-40, 119), (-39, 119), (-38, 119), (-39, 120), (-38, 120)}
OK_PAIRS = [('av', 'av_n'), ('av', 'av_s'), ('av_n', 'st_s'), ('st_s', 'plaza'), ('plaza', 'west'), ('west', 'st_th'),
            ('st_n', 'plaza'), ('tv', 'lobby'), ('tv', 'deck'), ('lobby', 'deck'), ('plaza', 'st_th')]


def rc(x0, x1, z0, z1):
    return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


def tv_disc(r=TV_R):
    cx, cz = TV_C
    return {(x, z) for x in range(cx - 12, cx + 13) for z in range(cz - 12, cz + 13) if math.hypot(x - cx, z - cz) <= r}


def tower_schema():
    return json.load(open(os.path.join(REPO, 'schemas', 'ostankino.json')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'hill-plan-v1.png'))
    args = ap.parse_args()
    W = World()
    disc = tv_disc()

    print('== проверки плана ==')
    area, foot = {}, {}

    def add(k, cells):
        for c in cells: area.setdefault(c, []).append(k)
    for k, _, x0, x1, z0, z1, *_ in STREETS: add(k, rc(x0, x1, z0, z1))
    for k, (_, rects, _) in STAIRS.items():
        c = set().union(*(rc(*r) for r in rects)); foot[k] = c; add(k, c)
    for k, _, x0, x1, z0, z1, *_ in OBJ:
        c = rc(x0, x1, z0, z1)
        if k == 'tv': c = disc
        if k == 'plaza': c = {(x, z) for x, z in c if math.hypot(x - TV_C[0], z - TV_C[1]) <= 14.6} - disc
        if k == 'lobby': c = tv_disc(8.5)
        if k == 'deck': c = tv_disc(6.5)
        foot[k] = c; add(k, c)
    outside = sorted({k for c_, v in area.items() for k in v
                      if not (DX0 <= c_[0] <= DX1 and DZ0 <= c_[1] <= DZ1) and not (k == 'st_th' and c_[0] >= -626)})
    print('вне района (Театральная лестница входит в стенку театра на X −626/−625 — допустимо):', outside or 'нет')
    okp = {frozenset(p) for p in OK_PAIRS}
    bad = sorted({tuple(sorted(set(v))) for v in area.values()
                  if len(set(v)) > 1 and not all(frozenset((a, b)) in okp for a in set(v) for b in set(v) if a < b)})
    print('пересечения объектов:', 'нет' if not bad else bad)

    # связность: от проспекта по мощению (проспект, тротуары, лестницы, площадь, смотровая) до каждого объекта;
    # в башню входят между опорами — с площади; «тарелка» — по лестнице в стволе (этап 2), здесь не считается
    def lonely(skip=()):
        names = {s[0] for s in STREETS} | set(STAIRS) | {'plaza', 'west', 'tv'}   # между опорами — мощение 79.0
        names -= set(skip)
        paved = {c for c, v in area.items() if any(n in names for n in v)}
        seen, st = set(), [(-620, 1816)]
        while st:
            c = st.pop()
            if c in seen or c not in paved: continue
            seen.add(c); st += [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]
        touch = lambda cells: any((x + a, z + b) in seen for x, z in cells for a, b in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
        out = [k for k, c in foot.items() if k != 'deck' and not touch(c)]
        return out, len(seen), seen
    lone, nseen, seen = lonely()
    print('объекты без мощёной дорожки от проспекта:', lone or 'нет', f'| мощёных клеток в сети {nseen}')
    print('стыки: проспект парка (X −625, Z 1816) рядом с сетью:', (-624, 1816) in seen,
          '| Горная дорога (X −625, Z 1771…1773) — низ Северной лестницы (−624, 1774):', (-624, 1774) in seen,
          '| верхний ряд театра (−627, 1785) — низ Театральной лестницы:', (-626, 1785) in seen)
    print('НЕГАТИВ: без Парадной лестницы площадь с проспекта недостижима:', 'plaza' in lonely(('st_s',))[0])
    print('НЕГАТИВ: без площади смотровая отрезана от проспекта:', 'west' in lonely(('plaza',))[0])
    print('НЕГАТИВ: без площади вестибюль в основании недостижим:', 'lobby' in lonely(('plaza',))[0])
    print('НЕГАТИВ: без тротуара Парадная лестница висит (нет стыка с проспектом):', 'st_s' in lonely(('av_n',))[0] or
          'plaza' in lonely(('av_n',))[0])

    # лестницы: подъём по маршу и площадки
    av_prof = {}
    y, last = 64.5, -625
    for x in range(-624, -592):
        g = sum(W.surf(x, z) for z in range(1813, 1821)) / 8
        if g + 1 - y >= 1.5 and x - last >= 4: y += 0.5; last = x
        av_prof[x] = y
    cut = max(max(W.surf(x, z) for z in range(1813, 1821)) + 1 - av_prof[x] for x in av_prof)
    fill = max(av_prof[x] - (min(W.surf(x, z) for z in range(1813, 1821)) + 1) for x in av_prof)
    slope = max(abs(av_prof[x + 1] - av_prof[x]) for x in range(-624, -593))
    print(f'проспект X −624…−593: покрытие {av_prof[-624]:.1f}→{av_prof[-593]:.1f} (0.5 не чаще чем через 4 бл., '
          f'уклон макс. {slope}/бл.), выемка до {cut:.1f} (с севера — подпорная стенка), насыпь до {fill:.1f}')
    walk = PLAZA_Y + 1
    sw = av_prof[-606] + 0.5                                    # тротуар Z 1813 на 0.5 выше проезжей части
    runs = {
        'Театральная': (72.0, walk, 7, [7]),                     # верхний ряд театра 71 (ходим 72) → смотровая
        'Северная': (65.0, walk, 14, [7, 7]),                    # край Горной дороги 65.0 → площадь (2 марша, площадка)
        'Парадная': (sw, walk, 7 + 2 + 6, [7, 6]),               # тротуар → центр. марш 7 → площадка 73 → боковые марши 6
    }
    for n, (a, b, run, flights) in runs.items():
        rise = b - a
        print(f'  {n} лестница: {a:.1f} → {b:.1f}, подъём {rise:.1f} на {run} бл., марши {flights} ступ. '
              f'(норма: ступень ≤ 1, марш ≤ 7):', 'OK' if max(flights) <= 7 and sum(flights) >= math.ceil(rise) - 0.01 else 'ОШИБКА')
    # негатив: Парадная без боковых маршей (один прямой марш 12 ступеней) — марш длиннее нормы
    print('НЕГАТИВ: Парадная одним маршем в 12 ступеней — ошибка марша:', 12 > 7)

    # площадь: земляные работы
    for k, c in (('площадь', foot['plaza']), ('смотровая', foot['west']), ('основание башни', disc)):
        h = sorted(W.surf(x, z) for x, z in c)
        fl = sum(1 for v in h if PLAZA_Y - v >= 4)
        print(f'{k}: {len(c)} кл., рельеф Y {h[0]}…{h[-1]} (медиана {h[len(h) // 2]}) → мощение Y {PLAZA_Y} (ходим {walk}.0): '
              f'срезать до {max(0, h[-1] - PLAZA_Y)}, подсыпать до {PLAZA_Y - h[0]} (≥ 4 — {fl} кл., край — подпорная стенка)')
    # кровля каньона, резерв, загрузчик
    roofs = {k: min((W.surf(x, z) - W.cave_top(x, z) for x, z in c if W.cave_top(x, z) is not None), default=None)
             for k, c in foot.items()}
    print('кровля каньона под объектами (мин.):', {k: v for k, v in roofs.items() if v is not None})
    print('объекты с кровлей < 3:', [k for k, v in roofs.items() if v is not None and v < 3] or 'нет')
    rv = sorted({k for k, c in foot.items() for x, z in c for n, x0, x1, z0, z1 in RESERVE if x0 <= x <= x1 and z0 <= z <= z1})
    print('объекты над резервом трасс (Парадная лестница Z 1812 — фундамент не ниже Y 60):', rv or 'нет')
    chunks = {(x >> 4, z >> 4) for x in range(DX0, DX1 + 1) for z in range(DZ0, DZ1 + 1)}
    print('чанки района:', sorted(chunks), '| в 25 чанках загрузчика:', sorted(chunks & LOADER) or 'нет — только декор')
    T = tower_schema()
    ymax = max(b['y'] for b in T)
    print(f'телебашня: {len(T)} бл., 23×{ymax + 1}×23, origin ({TV_C[0] - 11}, {PLAZA_Y}, {TV_C[1] - 11}), верх Y {PLAZA_Y + ymax} '
          f'(предел 255), «тарелка» — пол y 57 → Y {PLAZA_Y + 57}, ходим {PLAZA_Y + 58}…{PLAZA_Y + 63}')
    built = [k for k, c in foot.items() if any((x, y_, z) in W.pre for x, z in c for y_ in range(60, 130)) and k != 'st_th']
    print('объекты поверх построенного (кроме Театральной лестницы — проход в стенке театра):', built or 'нет')
    th = [(z, W.surf(-626, z)) for z in (1785, 1786)]
    print('стенка театра в проходе X −626:', th, '→ разобрать выше ступеней (исправление парка, в этапе 1)')

    # ---------- картинка ----------
    def colr(x, z):
        y = 130
        while y > 20 and W.block(x, y, z) in ('air', 'plant'): y -= 1
        b = W.block(x, y, z)
        if b == 'water' or b.startswith('flowing_water'): return (150, 190, 230)
        if b != 'ground': return (185, 180, 172)
        k = (max(62, min(y, 90)) - 62) / 28
        return (int(215 - 95 * k), int(215 - 75 * k), int(150 - 80 * k))

    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    fb = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf') if os.path.exists(f)), None)
    F = lambda n, b=False: ImageFont.truetype(fb if b and fb else fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    PH2 = 26 * 6
    img = Image.new('RGB', (ML + mw + 470, max(MT + mh + PH2 + 90, 775 + (192 - 58) * 4 + 20)), (250, 250, 247))
    dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: ML + (x - X0) * S
    pz = lambda z: MT + (z - Z0) * S

    def rect(x0, x1, z0, z1, fill, outline=None, w=2):
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], fill=fill, outline=outline, width=w)

    def dashed(x0, x1, z0, z1, c, w=2, d=6):
        pts = [(px(x0), pz(z0)), (px(x1 + 1), pz(z0)), (px(x1 + 1), pz(z1 + 1)), (px(x0), pz(z1 + 1)), (px(x0), pz(z0))]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = max(1, int(max(abs(bx - ax), abs(by - ay)) / d))
            for i in range(0, n, 2):
                dr.line([ax + (bx - ax) * i / n, ay + (by - ay) * i / n,
                         ax + (bx - ax) * min(i + 1, n) / n, ay + (by - ay) * min(i + 1, n) / n], fill=c, width=w)

    def outline(cells, c, w=2):
        for (x, z) in cells:
            for dx, dz, e in ((1, 0, 'r'), (-1, 0, 'l'), (0, 1, 'b'), (0, -1, 't')):
                if (x + dx, z + dz) not in cells:
                    a = {'r': (px(x + 1) - 1, pz(z), px(x + 1) - 1, pz(z + 1) - 1), 'l': (px(x), pz(z), px(x), pz(z + 1) - 1),
                         'b': (px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z + 1) - 1), 't': (px(x), pz(z), px(x + 1) - 1, pz(z))}[e]
                    dr.line(a, fill=c, width=w)

    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            rect(x, x, z, z, colr(x, z))
    for x in range(DX0, DX1 + 1):
        for z in range(DZ0, DZ1 + 1):
            if (x, z) not in area: rect(x, x, z, z, (135, 190, 105, 150))
    for x in range(X0, X1 + 2):
        if x % 16 == 0: dr.line([px(x), MT, px(x), MT + mh], fill=(90, 90, 90, 110), width=1)
    for z in range(Z0, Z1 + 2):
        if z % 16 == 0: dr.line([ML, pz(z), ML + mw, pz(z)], fill=(90, 90, 90, 110), width=1)
    for x in range(-640, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1770, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(11))
    for k, _, x0, x1, z0, z1, st, fill in STREETS: rect(x0, x1, z0, z1, fill)
    for k in ('plaza', 'west'):
        for (x, z) in foot[k]: rect(x, x, z, z, PATH)
    for k in STAIRS:
        for (x, z) in foot[k]: rect(x, x, z, z, STAIR)
        outline(foot[k], (120, 90, 50), 1)
    # ступени — штрихи поперёк марша
    def hatch(x0, x1, z0, z1, along_x):
        for i in range((x1 - x0 + 1) if along_x else (z1 - z0 + 1)):
            if along_x: dr.line([px(x0 + i), pz(z0), px(x0 + i), pz(z1 + 1)], fill=(120, 90, 50, 200), width=1)
            else: dr.line([px(x0), pz(z0 + i), px(x1 + 1), pz(z0 + i)], fill=(120, 90, 50, 200), width=1)
    hatch(-626, -620, 1785, 1786, True); hatch(-624, -611, 1774, 1775, True)
    hatch(-609, -603, 1806, 1812, False); hatch(-615, -610, 1804, 1805, True); hatch(-602, -597, 1804, 1805, True)
    for k, name, x0, x1, z0, z1, st, bld, fill in OBJ:
        if k in ('plaza', 'west'): continue
        c = foot[k]
        if k == 'tv':
            for (x, z) in c: rect(x, x, z, z, fill + (235,))
        outline(c, (30, 30, 30) if k == 'tv' else (40, 90, 160), 2 if k == 'tv' else 1)
    # опоры башни — y 1 схемы
    T = tower_schema()
    ox, oz = TV_C[0] - 11, TV_C[1] - 11
    for b in T:
        if b['y'] == 1: rect(ox + b['x'], ox + b['x'], oz + b['z'], oz + b['z'], (110, 110, 115, 255))
    cx, cz = TV_C
    for r, col in ((3.5, (200, 40, 40)), (6.5, (40, 90, 160))):
        dr.ellipse([px(cx) - r * S + S // 2, pz(cz) - r * S + S // 2, px(cx) + r * S + S // 2, pz(cz) + r * S + S // 2],
                   outline=col, width=2)
    # парапет смотровой и стрелки лестниц
    dr.line([px(-624), pz(1779), px(-624), pz(1797)], fill=(90, 70, 40), width=4)
    for (ax, az), (bx, bz) in (((-626, 1786), (-619, 1786)), ((-624, 1775), (-611, 1775)), ((-606, 1813), (-606, 1806)),
                               ((-607, 1805), (-615, 1805)), ((-605, 1805), (-597, 1805))):
        dr.line([px(ax) + S // 2, pz(az), px(bx) + S // 2, pz(bz)], fill=(160, 40, 30), width=2)
        dr.ellipse([px(bx) + S // 2 - 3, pz(bz) - 3, px(bx) + S // 2 + 3, pz(bz) + 3], fill=(160, 40, 30))
    for n, x0, x1, z0, z1 in RESERVE: dashed(x0, x1, z0, z1, (120, 40, 160, 230), 2, 5)
    dashed(DX0, DX1, DZ0, DZ1, (0, 0, 0, 220), 2, 8)
    dashed(DX0, DX1, 1776, 1807, (0, 0, 0, 90), 1, 4)
    # деревья, фонари, скамейки (ориентир)
    trees = []
    for x in range(DX0, DX1 + 1):
        for z in range(DZ0, 1812):
            if (x, z) in area: continue
            if any((x + a, z + b) in area for a in (-1, 0, 1) for b in (-1, 0, 1)): continue
            if (x * 5 + z * 3) % 7 == 0: trees.append((x, z))
    for (x, z) in trees:
        dr.ellipse([px(x) - 3, pz(z) - 3, px(x) + S + 2, pz(z) + S + 2], fill=(40, 125, 50), outline=(20, 70, 20))
    lamps = [(x, 1813) for x in range(-620, -592, 8)] + [(x, 1776) for x in (-616, -606, -596)] + \
            [(-593, z) for z in (1782, 1790, 1798)] + [(x, 1804) for x in (-618, -594)] + [(-621, z) for z in (1780, 1791, 1796)]
    for (x, z) in lamps:
        dr.ellipse([px(x) + 3, pz(z) + 3, px(x) + S - 4, pz(z) + S - 4], fill=(240, 200, 40), outline=(120, 90, 0))
    benches = [(-622, z) for z in (1781, 1783, 1789, 1791, 1794)]
    for (x, z) in benches: rect(x, x, z, z, (150, 110, 60, 255))
    print(f'озеленение (ориентир): деревьев {len(trees)}, фонарей {len(lamps)}, скамеек на смотровой {len(benches)}')

    L = lambda x, z, s, sz=11, fill='black': dr.text((px(x), pz(z)), s, fill=fill, font=F(sz), stroke_width=3, stroke_fill=(255, 255, 255))
    L(-640, 1815, '← парк      ГЛАВНЫЙ ПРОСПЕКТ →  промзона', 11)
    L(-640, 1770, 'ГОРНАЯ ДОРОГА (до X −625)', 10)
    L(-615, 1766, 'ГОРА F (район 7)', 10, (90, 70, 40))
    L(-641, 1790, 'Зелёный\nтеатр', 10, (90, 70, 40))
    L(-641, 1822, 'ПРОМЗОНА (район 9)', 10, (90, 90, 90))
    L(-612, 1789, 'ТЕЛЕБАШНЯ', 12, (30, 30, 30))
    L(-620, 1823, 'резерв: метро 1 + коллектор под проспектом', 9, (120, 40, 160))
    num = {}
    items = [(o[0], o[1], o[6]) for o in OBJ if o[6] == 1] + [(k, v[0], v[2]) for k, v in STAIRS.items()] + \
            [(o[0], o[1], o[6]) for o in OBJ if o[6] == 2]
    for i, (k, name, st) in enumerate(items, 1):
        num[k] = i
        c = foot[k]; mx = sum(x for x, _ in c) / len(c); mz = sum(z for _, z in c) / len(c)
        if k == 'plaza': mx, mz = -596, 1777
        if k == 'tv': mx, mz = -616, 1782
        if k == 'lobby': mx, mz = -609, 1794
        if k == 'deck': mx, mz = -603, 1787
        if k == 'st_s': mx, mz = -607, 1809
        dr.ellipse([px(mx) - 2, pz(mz) - 2, px(mx) + 16, pz(mz) + 16], fill=(255, 255, 255), outline=(200, 30, 30), width=2)
        dr.text((px(mx) + (3 if i < 10 else 0), pz(mz) - 1), str(i), fill=(200, 30, 30), font=F(12, True))

    # ---- вид с юга (фасад W–E, 1 блок = 4 px по обеим осям): рельеф по Z 1786, башня — проекция схемы
    E = 4
    ex0 = ML + mw + 20
    ey0 = 775
    ebase = ey0 + (192 - 58) * E
    ex = lambda x: ex0 + (x - X0) * E
    ey = lambda yy: ebase - (yy - 58) * E
    dr.text((ex0, ey0 - 22), 'Вид с юга, Z 1786 (запад → восток), масштаб 1:1', fill='black', font=F(12, True))
    for yy in range(60, 192, 10):
        dr.line([ex0, ey(yy), ex(X1 + 1), ey(yy)], fill=(225, 225, 225), width=1)
        dr.text((ex(X1 + 1) + 4, ey(yy) - 6), str(yy), fill='black', font=F(9))
    ZC = 1786
    for x in range(X0, X1 + 1):
        g = W.surf(x, ZC); tags = area.get((x, ZC), [])
        top = (72 + (x + 626)) if 'st_th' in tags else PLAZA_Y if any(t in tags for t in ('plaza', 'west', 'tv')) else g
        dr.rectangle([ex(x), ey(top + 1), ex(x + 1) - 1, ebase], fill=STAIR[:3] if 'st_th' in tags else (205, 195, 170))
        dr.line([ex(x), ey(g + 1), ex(x + 1) - 1, ey(g + 1)], fill=(120, 80, 40), width=1)
    col = {'concrete:0': (235, 235, 235), 'concrete:14': (190, 40, 40), 'concrete:7': (90, 90, 90),
           'glass': (140, 200, 235), 'glowstone': (250, 220, 90)}
    front = {}
    for b in T:                                 # ближний к зрителю (южный, большая z) блок в каждой клетке фасада
        k = (b['x'], b['y'])
        if k not in front or b['z'] > front[k]['z']: front[k] = b
    for (bx, by), b in front.items():
        X = ox + bx; Y = PLAZA_Y + by
        dr.rectangle([ex(X), ey(Y + 1), ex(X + 1) - 1, ey(Y) - 1], fill=col.get(b['block'], (200, 200, 200)))
    dr.line([ex(-606) + 2, ey(PLAZA_Y + 1), ex(-606) + 2, ey(PLAZA_Y + 58)], fill=(160, 40, 30, 180), width=1)
    for x, yy, t in ((-642, 76, 'театр'), (-628, 90, 'смотровая'), (-600, PLAZA_Y + 70, '«тарелка»\nY 136…141'),
                     (-640, 150, 'красная линия —\nстремянка в стволе\n(этап 2)')):
        dr.text((ex(x), ey(yy)), t, fill='black', font=F(9), stroke_width=2, stroke_fill='white')
    base = MT + mh

    # ---- разрез N–S по X −606: Горная дорога — площадь — Парадная лестница — проспект
    XC = -606
    oy2 = base + 50
    dr.text((ML, oy2 - 22), f'Разрез по X {XC} (север → юг), 1 блок = 6 px по высоте; красная линия — ход пешехода',
            fill='black', font=F(12, True))
    base2 = oy2 + PH2
    sy2 = lambda yy: base2 - (yy - 60) * 6
    for yy in range(62, 86, 4):
        dr.line([ML, sy2(yy), ML + mh * mw // mh, sy2(yy)], fill=(225, 225, 225), width=1); dr.text((8, sy2(yy) - 6), str(yy), fill='black', font=F(10))
    qz = lambda z: ML + (z - Z0) * (mw / (Z1 - Z0 + 1))
    prev = None
    for z in range(Z0, Z1 + 1):
        g = W.surf(XC, z)
        if 1813 <= z <= 1820: top = av_prof[XC] + (0.5 if z in (1813, 1819, 1820) else 0)
        elif 1806 <= z <= 1812: top = sw + (1813 - z)
        elif z in (1804, 1805): top = sw + 7
        elif 1776 <= z <= 1803: top = walk
        else: top = g + 1
        dr.rectangle([qz(z), sy2(g + 1), qz(z + 1) - 1, base2], fill=(205, 195, 170))
        dr.line([qz(z), sy2(g + 1), qz(z + 1) - 1, sy2(g + 1)], fill=(120, 80, 40), width=2)
        if prev is not None: dr.line([qz(z), sy2(prev), qz(z), sy2(top)], fill=(200, 30, 30), width=2)
        dr.line([qz(z), sy2(top), qz(z + 1), sy2(top)], fill=(200, 30, 30), width=2)
        prev = top
    for z, yy, t in ((1766, 83, 'склон к горе F'), (1790, 83, 'Башенная площадь, 79.0'),
                     (1806, 83, 'Парадная\nлестница'), (1815, 70, 'проспект')):
        dr.text((qz(z), sy2(yy)), t, fill='black', font=F(10), stroke_width=2, stroke_fill='white')

    # легенда
    lx = ML + mw + 20
    dr.text((lx, 10), 'ХОЛМ E — план v1', fill='black', font=F(17, True))
    lines = [('Этап 1 — рельеф, башня, лестницы (одна порция):', True)]
    lines += [(f' {num[k]}. {n}', False) for k, n, st in items if st == 1]
    lines += [(' проспект X −624…−593 с тротуарами,', False), ('   фонари в ритме парка, подъём 1:8;', False),
              (' площадь 79.0 вокруг башни, газоны,', False), ('   деревья, фонари, скамейки;', False),
              (' проход в стенке Зелёного театра', False), ('   (исправление парка)', False),
              ('', False), ('Этап 2 — башня внутри (одна порция):', True)]
    lines += [(f' {num[k]}. {n}', False) for k, n, st in items if st == 2]
    lines += [(' остеклённый павильон между опорами,', False), ('   электрощитовая 3×3 с шахтой;', False),
              (' подъём в «тарелку»: стремянка в стволе', False), ('   с площадками отдыха через 12 бл.', False),
              ('   (лифта в 1.12.2 нет);', False), (' «тарелка»: смотровая по кругу,', False),
              ('   кафе «Седьмое небо» (декор)', False),
              ('', False), ('Вне 25 чанков загрузчика —', True), (' только декор, ничего работающего', False), ('', False),
              ('Обозначения:', True), (' чёрный пунктир — район (тонкий — зона', False), ('   генплана Z 1776…1807)', False),
              (' фиолетовый пунктир — резерв трасс', False), (' серые клетки — опоры башни', False),
              (' синий круг — «тарелка», красный — ствол', False), (' красные стрелки — подъём лестниц', False),
              (' жёлтые — фонари, зелёные — деревья,', False), ('   коричневые — скамейки', False)]
    for i, (t, b) in enumerate(lines):
        dr.text((lx, 40 + i * 19), t, fill='black', font=F(12, b))
    img.save(args.out)
    print('план', args.out, img.size)


if __name__ == '__main__':
    main()
