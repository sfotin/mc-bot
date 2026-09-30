"""План района «Парк + зоопарк» v1 (CITY.md §7.5): рельеф + всё построенное (world_model.py),
озеро в новом контуре с островом, улицы (Парковая ул., продолжение главного проспекта, Горная
дорога к горе F), кольцевая аллея и дорожки, объекты парка и вольеры зоопарка, этапы, резерв
трасс (метро 1, коллектор, вестибюль «Парк»), профиль Горной дороги.

Запуск: plan_park_v1.py [--out docs/districts/park-plan-v1.png]
Печатает проверки плана: границы района, пересечения объектов, связность дорожек от проспекта до
каждого объекта (с негативным прогоном), кровля каньона под зданиями (норма >= 3), резерв трасс,
стыки со Старым городом, уклон Горной дороги (<= 0.5 на блок), озеро (площадь, берег, объекты
поверх построенного).
"""
import argparse
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO  # noqa: E402

X0, X1, Z0, Z1 = -674, -612, 1738, 1826      # окно картинки
DX0, DX1, DZ0, DZ1 = -660, -625, 1745, 1812  # район (CITY.md §2.3 + север до Z 1745, юг — до тротуара проспекта)
S = 11
ML, MT = 46, 30
WATER_Y = 63                                  # уровень воды озера (берег вровень, CITY.md §6)

AV = (95, 95, 95, 230)
ST = (140, 140, 140, 230)
WALK = (215, 205, 185, 240)
PATH = (226, 214, 190, 255)

# ---- улицы: (ключ, подпись, X0, X1, Z0, Z1, этап, заливка) ----
STREETS = [
    ('av', 'главный проспект', -660, -625, 1814, 1818, 1, AV),     # продолжение Старого города (X −661 — стык)
    ('av_n', 'тротуар', -660, -625, 1813, 1813, 1, WALK),
    ('av_s', 'тротуар', -660, -625, 1819, 1820, 1, WALK),
    ('pk', 'Парковая ул.', -660, -656, 1745, 1812, 1, ST),         # граница со Старым городом и окраинами
    ('gd', 'Горная дорога', -655, -625, 1769, 1773, 1, ST),        # дорога к горе F (§2.4), дальше — район 7
]
# ---- дорожки (мощение): (ключ, X0, X1, Z0, Z1, этап) ----
PATHS = [
    ('ring_n', -655, -636, 1774, 1775, 1),     # кольцевая аллея: север
    ('ring_w', -655, -654, 1774, 1795, 1),     # запад (набережная вдоль Парковой ул.)
    ('ring_s', -655, -636, 1793, 1795, 1),     # юг — продолжение Рыночного переулка (Z 1793…1795)
    ('ring_e', -637, -636, 1774, 1795, 1),     # восток — оркестр Зелёного театра между сценой и рядами
    ('al_s', -647, -646, 1796, 1812, 1),       # Южная аллея: проспект — кольцо
    ('p_rose', -645, -637, 1804, 1805, 1),     # дорожка к розарию
    ('z_main', -648, -646, 1749, 1768, 2),     # зоопарк: главная аллея от ворот на север
    ('z_cross', -655, -634, 1755, 1756, 2),    # поперечная аллея
    ('z_east', -636, -634, 1745, 1754, 2),     # к смотровой над ламами
]
CROSS = (-648, -646, 1769, 1773)               # переход через Горную дорогу: зоопарк — кольцо

# ---- объекты: (ключ, подпись, X0, X1, Z0, Z1, этап, здание?, цвет) ----
OBJ = [
    ('gate', 'Парковые ворота', -655, -654, 1792, 1796, 1, False, (240, 240, 235)),
    ('boat', 'Лодочная станция', -652, -649, 1796, 1799, 1, True, (70, 110, 170)),
    ('pier', 'причал', -651, -650, 1788, 1792, 1, False, (150, 110, 60)),
    ('isl', 'остров, ротонда', -649, -645, 1780, 1784, 1, True, (245, 245, 250)),
    ('brg', 'мостик', -653, -650, 1782, 1782, 1, False, (150, 110, 60)),
    ('cafe', 'Кафе «Озеро»', -645, -639, 1796, 1803, 1, True, (230, 150, 90)),
    ('play', 'Детская площадка', -655, -648, 1801, 1809, 1, False, (250, 200, 60)),
    ('rose', 'Розарий', -636, -627, 1800, 1811, 1, False, (235, 110, 170)),
    ('stage', 'сцена на воде', -640, -638, 1781, 1788, 1, True, (170, 120, 70)),
    ('thr', 'Зелёный театр', -635, -627, 1776, 1795, 1, False, (200, 175, 140)),
    ('zgate', 'Ворота зоопарка, касса, щитовая', -651, -646, 1764, 1768, 2, True, (200, 90, 70)),
    ('bear', 'Белые медведи (лёд, бассейн)', -655, -649, 1745, 1754, 2, False, (215, 240, 250)),
    ('wolf', 'Волки (ельник)', -655, -652, 1757, 1767, 2, False, (60, 110, 70)),
    ('dome', 'Тропический купол: оцелоты, попугаи', -645, -637, 1745, 1753, 2, True, (150, 220, 150)),
    ('farm', 'Контактный зоопарк: амбар, загон', -645, -634, 1757, 1767, 2, True, (190, 140, 80)),
    ('llama', 'Ламы (скалы)', -633, -626, 1745, 1767, 2, False, (150, 140, 125)),
]
VEST = ('Вестибюль М «Парк» (резерв)', -643, -640, 1809, 1812)
RESERVE = [('метро 1 + коллектор', -660, -625, 1812, 1820)]
OK_PAIRS = [('av', 'av_n'), ('av', 'av_s'), ('av', 'pk'), ('av_n', 'pk'), ('pk', 'gd'), ('gd', 'ring_n'),
            ('ring_n', 'ring_w'), ('ring_n', 'ring_e'), ('ring_w', 'ring_s'), ('ring_s', 'ring_e'), ('ring_s', 'al_s'),
            ('gate', 'ring_w'), ('gate', 'ring_s'), ('pier', 'ring_s'), ('p_rose', 'rose'), ('z_main', 'z_cross'),
            ('z_main', 'zgate'), ('z_cross', 'z_east'), ('av_n', 'vest'), ('brg', 'ring_w'), ('brg', 'isl'),
            ('al_s', 'p_rose'), ('gd', 'cross'), ('cross', 'ring_n'), ('zgate', 'cross')]
ISLAND = (-647, 1782, 2.2)                   # центр, радиус
THEATRE_C = (-639, 1785.5)                   # центр рядов
SQUARE = []


def noise(x, z, seed=5):
    """гладкий шум по координате (значения в узлах сетки 4 + билинейная интерполяция), −1…1"""
    def h(i, j):
        v = (i * 374761393 + j * 668265263 + seed * 2147483647) & 0xFFFFFFFF
        v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
        return (v & 0xFFFF) / 32767.5 - 1
    gx, gz = x / 4.0, z / 4.0
    i, j = math.floor(gx), math.floor(gz); fx, fz = gx - i, gz - j
    fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a = h(i, j) * (1 - fx) + h(i + 1, j) * fx
    b = h(i, j + 1) * (1 - fx) + h(i + 1, j + 1) * fx
    return a * (1 - fz) + b * fz


def lake_cells():
    """новый контур озера: эллипс с шумом внутри кольцевой аллеи, медиана 3×3; остров вычтен"""
    cx, cz, rx, rz = -645.8, 1784.0, 7.6, 8.4
    raw = {(x, z) for x in range(-653, -637) for z in range(1776, 1793)
           if ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 + 0.28 * noise(x, z) < 1.0}
    lake = set()
    for x in range(-653, -637):
        for z in range(1776, 1793):
            n = sum((x + a, z + b) in raw for a in (-1, 0, 1) for b in (-1, 0, 1))
            if n >= 5: lake.add((x, z))
    lake = {(x, z) for (x, z) in lake if -653 <= x <= -638 and 1776 <= z <= 1791}
    ix, iz, ir = ISLAND
    isl = {(x, z) for x in range(-650, -643) for z in range(1779, 1786) if math.hypot(x - ix, z - iz) <= ir}
    return lake - isl, isl


def theatre_cells():
    cx, cz = THEATRE_C
    seats = {(x, z) for x in range(-635, -626) for z in range(1776, 1796) if 4.5 <= math.hypot(x - cx, z - cz) <= 12.5}
    return seats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'park-plan-v1.png'))
    args = ap.parse_args()
    W = World()
    lake, isl = lake_cells()
    seats = theatre_cells()

    print('== проверки плана ==')
    area = {}
    def add(k, cells):
        for c in cells: area.setdefault(c, []).append(k)
    rc = lambda x0, x1, z0, z1: {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    for k, _, x0, x1, z0, z1, *_ in STREETS: add(k, rc(x0, x1, z0, z1))
    for k, x0, x1, z0, z1, _ in PATHS: add(k, rc(x0, x1, z0, z1))
    add('cross', rc(*CROSS))
    foot = {}
    for k, _, x0, x1, z0, z1, *_ in OBJ:
        c = rc(x0, x1, z0, z1)
        if k == 'thr': c = seats
        if k == 'isl': c = isl
        foot[k] = c; add(k, c)
    add('vest', rc(*VEST[1:]))
    zmax = {'av_s': 1820, 'av': 1818}
    outside = [k for c_, v in area.items() for k in v
               if not (DX0 <= c_[0] <= DX1 and DZ0 <= c_[1] <= zmax.get(k, 1813))]
    print('вне района:', sorted(set(outside)) or 'нет')
    okp = {frozenset(p) for p in OK_PAIRS}
    bad = sorted({tuple(sorted(set(v))) for v in area.values()
                  if len(set(v)) > 1 and not all(frozenset((a, b)) in okp for a in set(v) for b in set(v) if a < b)})
    print('пересечения объектов:', 'нет' if not bad else bad)
    wet = {k: len(c & lake) for k, c in foot.items() if c & lake}
    print('объекты на воде (сцена, причал — допустимо):', wet or 'нет')
    print('дорожки/улицы по воде:', sorted(set(k for c_, v in area.items() if c_ in lake for k in v
                                              if k not in ('stage', 'pier'))) or 'нет')

    # связность: от проспекта по мощению (улицы, дорожки, переход) до каждого объекта и вестибюля
    def lonely(skip=()):
        names = {s[0] for s in STREETS} | {p[0] for p in PATHS} | {'cross', 'brg', 'pier'}
        names -= set(skip)
        paved = {c for c, v in area.items() if any(n in names for n in v)}
        seen, st = set(), [(-650, 1816)]
        while st:
            c = st.pop()
            if c in seen or c not in paved: continue
            seen.add(c); st += [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]
        touch = lambda cells: any((x + a, z + b) in seen for x, z in cells for a, b in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
        out = [k for k, c in foot.items() if not touch(c)]
        if not touch(rc(*VEST[1:])): out.append('vest')
        return out, len(seen), seen
    lone, nseen, seen = lonely()
    print('объекты без мощёной дорожки от проспекта:', lone or 'нет', f'| мощёных клеток в сети {nseen}')
    print('стык с Рыночным переулком (X −661/−660, Z 1794) в сети:', (-660, 1794) in seen and (-655, 1794) in seen)
    print('НЕГАТИВ: без Южной аллеи кафе отрезано:', 'cafe' in lonely(('al_s', 'ring_s', 'p_rose'))[0])
    print('НЕГАТИВ: без мостика остров отрезан:', 'isl' in lonely(('brg',))[0])
    print('НЕГАТИВ: без аллей зоопарка купол отрезан:', 'dome' in lonely(('z_main', 'z_cross', 'z_east'))[0])

    # кровля каньона под зданиями
    roofs = {}
    for k, name, x0, x1, z0, z1, st, bld, *_ in OBJ:
        r = [W.surf(x, z) - W.cave_top(x, z) for x, z in foot[k] if W.cave_top(x, z) is not None]
        roofs[k] = min(r) if r else None
    print('кровля каньона под объектами (мин.):', {k: v for k, v in roofs.items() if v is not None})
    print('здания с кровлей < 3:', [k for k, v in roofs.items() if v is not None and v < 3] or 'нет')
    rv = sorted({k for k, c in foot.items() for x, z in c for n, x0, x1, z0, z1 in RESERVE if x0 <= x <= x1 and z0 <= z <= z1})
    print('объекты над резервом трасс (кроме вестибюля):', rv or 'нет')
    for nm, z in (('Рыночный переулок', 1794), ('проспект', 1816)):
        print(f'стык со Старым городом X −661/−660, {nm} Z {z}: Y {W.surf(-661, z)} / {W.surf(-660, z)}')
    ys = [W.surf(x, z) for x in range(-655, -626) for z in range(1776, 1793) if (x, z) in lake]
    shore = {(x + a, z + b) for x, z in lake for a in (-1, 0, 1) for b in (-1, 0, 1)} - lake - isl
    sh = [W.surf(x, z) for x, z in shore]
    print(f'озеро: {len(lake)} кл. (было 318), вода Y {WATER_Y}, дно по рельефу Y {min(ys)}…{max(ys)} → песок Y 60 '
          f'(глубина 3), берег по рельефу Y {min(sh)}…{max(sh)} → вровень Y {WATER_Y}; остров {len(isl)} кл.')
    # Горная дорога: профиль по оси Z 1771 — не круче 0.5 на блок (полублоки)
    prof = [(x, W.surf(x, 1771)) for x in range(-655, -624)]
    y, plan_y = 64.0, []
    for x, g in prof:
        y = max(64.0, min(y + 0.5, max(y, g - 1)))
        plan_y.append(y)
    slope = max(abs(b - a) for a, b in zip(plan_y, plan_y[1:]))
    cut = max(g - p for (x, g), p in zip(prof, plan_y)); fill = max(p - g for (x, g), p in zip(prof, plan_y))
    print(f'Горная дорога Z 1771: рельеф Y {min(g for _, g in prof)}…{max(g for _, g in prof)} (долина между холмом E и горой F), '
          f'покрытие Y {plan_y[0]:.1f}→{plan_y[-1]:.1f} у X −625, уклон макс. {slope} на блок (норма ≤ 0.5), насыпь до {fill:.1f}')
    built = [k for k, c in foot.items() if any((x, y_, z) in W.pre for x, z in c for y_ in range(60, 120))]
    print('объекты поверх построенного:', built or 'нет')
    thr_h = [W.surf(x, z) for x, z in seats]
    print(f'Зелёный театр: {len(seats)} кл. рядов, рельеф Y {min(thr_h)}…{max(thr_h)}; ряды 8 шт. Y 64…71 ступенями')
    ll = sorted(W.surf(x, z) for x, z in foot['llama'])
    print(f'вольер лам на склоне горы F: рельеф Y {ll[0]}…{ll[len(ll) * 9 // 10]} (90%; скалы — уступами, смотровая с z_east)')

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
    PH = 170
    img = Image.new('RGB', (ML + mw + 470, MT + mh + PH + 60), (250, 250, 247))
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
    # газон района
    for x in range(DX0, DX1 + 1):
        for z in range(DZ0, DZ1 + 1):
            if (x, z) not in area and (x, z) not in lake: rect(x, x, z, z, (135, 190, 105, 150))
    for x in range(X0, X1 + 2):
        if x % 16 == 0: dr.line([px(x), MT, px(x), MT + mh], fill=(90, 90, 90, 110), width=1)
    for z in range(Z0, Z1 + 2):
        if z % 16 == 0: dr.line([ML, pz(z), ML + mw, pz(z)], fill=(90, 90, 90, 110), width=1)
    for x in range(-670, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1740, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(11))
    for (x, z) in lake: rect(x, x, z, z, (60, 125, 215, 255))
    outline(lake, (20, 60, 140), 2)
    for k, _, x0, x1, z0, z1, st, fill in STREETS: rect(x0, x1, z0, z1, fill)
    for k, x0, x1, z0, z1, st in PATHS: rect(x0, x1, z0, z1, PATH)
    for i, z in enumerate(range(CROSS[2], CROSS[3] + 1)):
        rect(CROSS[0], CROSS[1], z, z, (255, 255, 255, 235) if i % 2 == 0 else (95, 95, 95, 230))
    for k, name, x0, x1, z0, z1, st, bld, fill in OBJ:
        c = foot[k]
        for (x, z) in c: rect(x, x, z, z, fill + (235,))
        outline(c, (30, 30, 30) if bld else (90, 70, 40), 2 if bld else 1)
    # ряды театра — дуги
    cx, cz = THEATRE_C
    for r in range(5, 13):
        dr.arc([px(cx) - r * S + S // 2, pz(cz) - r * S + S // 2, px(cx) + r * S + S // 2, pz(cz) + r * S + S // 2],
               -70, 70, fill=(110, 90, 60), width=1)
    rect(*VEST[1:], (120, 40, 160, 255), (60, 10, 90))
    dr.text((px(VEST[1]) + 12, pz(VEST[3]) + 10), 'M', fill='white', font=F(16, True))
    for n, x0, x1, z0, z1 in RESERVE: dashed(x0, x1, z0, z1, (120, 40, 160, 230), 2, 5)
    dashed(DX0, DX1, DZ0, DZ1, (0, 0, 0, 220), 2, 8)
    dashed(DX0, DX1, 1760, 1807, (0, 0, 0, 90), 1, 4)
    # деревья, фонари, скамейки (ориентир; точно — в генераторе)
    trees = []
    for x in range(DX0, DX1 + 1):
        for z in range(DZ0, DZ1 + 1):
            if (x, z) in area or (x, z) in lake: continue
            if any((x + a, z + b) in area for a in (-1, 0, 1) for b in (-1, 0, 1)): continue
            if (x * 7 + z * 3) % 9 == 0: trees.append((x, z))
    for (x, z) in trees:
        dr.ellipse([px(x) - 3, pz(z) - 3, px(x) + S + 2, pz(z) + S + 2], fill=(40, 125, 50), outline=(20, 70, 20))
    lamps = [(x, 1813) for x in range(-652, -625, 8)] + [(-656, z) for z in range(1749, 1812, 8)] + \
            [(x, 1774) for x in range(-652, -636, 6)] + [(x, 1795) for x in range(-652, -636, 6)] + [(-655, z) for z in (1779, 1786)]
    for (x, z) in lamps:
        dr.ellipse([px(x) + 3, pz(z) + 3, px(x) + S - 4, pz(z) + S - 4], fill=(240, 200, 40), outline=(120, 90, 0))
    print(f'озеленение (ориентир): деревьев {len(trees)}, фонарей {len(lamps)}')

    L = lambda x, z, s, sz=11, fill='black': dr.text((px(x), pz(z)), s, fill=fill, font=F(sz), stroke_width=3, stroke_fill=(255, 255, 255))
    L(-652, 1815, 'ГЛАВНЫЙ ПРОСПЕКТ →  промзона', 11)
    L(-673, 1760, 'П\nА\nР\nК\nО\nВ\nА\nЯ', 10); L(-659, 1747, '', 10)
    L(-652, 1770, 'ГОРНАЯ ДОРОГА → гора F', 10)
    L(-672, 1797, 'Рыночный\nпер. →', 9, (60, 60, 60))
    L(-652, 1788, 'ОЗЕРО', 12, (20, 60, 140))
    L(-670, 1818, 'СТАРЫЙ\nГОРОД', 10, (90, 90, 90))
    L(-623, 1786, 'ХОЛМ E\n(район 6)', 10, (90, 70, 40)); L(-623, 1750, 'ГОРА F\n(район 7)', 10, (90, 70, 40))
    L(-660, 1822, 'резерв: метро 1 + коллектор под проспектом', 9, (120, 40, 160))
    L(-653, 1741, 'ЗООПАРК', 12, (140, 40, 30))
    num = {}
    for i, (k, name, x0, x1, z0, z1, st, bld, fill) in enumerate(OBJ, 1):
        num[k] = i
        c = foot[k]; mx = sum(x for x, _ in c) / len(c); mz = sum(z for _, z in c) / len(c)
        dr.ellipse([px(mx) - 2, pz(mz) - 2, px(mx) + 16, pz(mz) + 16], fill=(255, 255, 255), outline=(200, 30, 30), width=2)
        dr.text((px(mx) + (3 if i < 10 else 0), pz(mz) - 1), str(i), fill=(200, 30, 30), font=F(12, True))

    # разрез по Z 1785 (запад → восток): Старый город — Парковая ул. — озеро с островом — сцена — театр — холм E
    ZC = 1785
    oy = MT + mh + 40
    dr.text((ML, oy - 20), f'Разрез по Z {ZC}: рельеф сейчас — коричневый контур, по плану — заливка', fill='black', font=F(12, True))
    base = oy + PH - 15
    sy = lambda yy: base - (yy - 58) * 6
    for yy in range(58, 84, 4):
        dr.line([ML, sy(yy), ML + mw, sy(yy)], fill=(215, 215, 215), width=1); dr.text((8, sy(yy) - 6), str(yy), fill='black', font=F(10))
    cx_, cz_ = THEATRE_C
    for x in range(X0, X1 + 1):
        g = W.surf(x, ZC); tags = area.get((x, ZC), [])
        if (x, ZC) in lake:
            dr.rectangle([px(x), sy(WATER_Y + 1), px(x + 1) - 1, sy(60 + 1)], fill=(60, 125, 215))
            dr.rectangle([px(x), sy(61), px(x + 1) - 1, base], fill=(225, 205, 140))
            if 'stage' in tags: dr.rectangle([px(x), sy(65), px(x + 1) - 1, sy(64)], fill=(170, 120, 70))
        elif 'thr' in tags:
            r = int(math.hypot(x - cx_, ZC - cz_) - 4.5)
            dr.rectangle([px(x), sy(65 + r), px(x + 1) - 1, base], fill=(200, 175, 140))
        elif tags or (DX0 <= x <= DX1):
            top = 65 if tags else (64 if x > -637 or (x, ZC) in isl else 64)
            if x > -627 and not tags: top = g + 1
            c = (95, 95, 95) if 'pk' in tags else (226, 214, 190) if tags else (245, 245, 250) if (x, ZC) in isl else (135, 190, 105)
            dr.rectangle([px(x), sy(top), px(x + 1) - 1, base], fill=c)
        else:
            dr.rectangle([px(x), sy(g + 1), px(x + 1) - 1, base], fill=(205, 195, 170))
        dr.line([px(x), sy(g + 1), px(x + 1) - 1, sy(g + 1)], fill=(120, 80, 40), width=2)
    for x, t in ((-660, 'Парковая'), (-648, 'остров'), (-640, 'сцена'), (-634, 'ряды театра'), (-622, 'холм E')):
        dr.text((px(x), sy(80)), t, fill='black', font=F(10), stroke_width=2, stroke_fill='white')
    # продолжение Горной дороги в район 7
    dr.line([px(-624), pz(1771) + S // 2, px(-613), pz(1766)], fill=(90, 90, 90, 200), width=4)

    # легенда
    lx = ML + mw + 20
    dr.text((lx, 10), 'ПАРК + ЗООПАРК — план v1', fill='black', font=F(17, True))
    lines = [('Этап 1 — парк (одна порция):', True)]
    lines += [(f' {num[k]}. {n}', False) for k, n, *_r in OBJ if _r[4] == 1]
    lines += [(' улицы: Парковая ул., проспект до X −625,', False), ('   Горная дорога до X −625 (дальше — район 7);', False),
              (' озеро: новый контур, вода Y 63 вровень', False), ('   с берегом, дно — песок Y 60 (глубина 3);', False),
              (' кольцевая аллея, газоны, деревья,', False), ('   фонари, скамейки, камыш, кувшинки', False),
              ('', False), ('Этап 2 — зоопарк (одна порция):', True)]
    lines += [(f' {num[k]}. {n}', False) for k, n, *_r in OBJ if _r[4] == 2]
    lines += [(' животных ставит игрок (яйца призыва)', False), ('   или бот позже (/summon отложен)', False),
              ('', False), ('Здания — city_lib.Tower; щитовые 3×3', True), (' с шахтой: в кафе (парк)', False),
              (' и у ворот зоопарка (зоопарк)', False), ('', False),
              ('Обозначения:', True), (' чёрный пунктир — район (тонкий —', False), ('   зона генплана Z 1760…1807;', False),
              ('   север до Z 1745 — под зоопарк)', False), (' фиолетовый пунктир — резерв трасс', False),
              (' M — вестибюль «Парк», строится', False), ('   со схемой тоннеля', False),
              (' жёлтые — фонари, зелёные — деревья', False), (' «зебра» — переход у ворот зоопарка', False)]
    for i, (t, b) in enumerate(lines):
        dr.text((lx, 40 + i * 19), t, fill='black', font=F(12, b))
    img.save(args.out)
    print('план', args.out, img.size)


if __name__ == '__main__':
    main()
