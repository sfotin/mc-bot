"""Гора F, план — редакция 2 (переделка по замечаниям владельца после этапа 1, CITY.md §7.7).

Замысел: ледовая трасса для лодок на одном уровне (лёд — верх Y 90), большая — через плато горы и за границы
участка на север и восток (съёмка окрестностей docs/terrain/mount.json), на виадуках над низиной к северу от
зоопарка; старт у седловины, лестница к старту от Горной площади. Всё построенное этапом 1, кроме Горной площади
с проездом, — снос с возвратом рельефа (башня-серпантин, кольцо, плато с катком и приютом, лестница, вершина).

Запуск: plan_mount_r2.py [--out docs/districts/mount-plan-r2.png]
Печатает проверки плана: трасса замкнута и на одном уровне, ширина льда и радиусы поворотов, участки трассы не
сближаются, лодке некуда выйти, длина круга; выемки, насыпи и виадуки (высоты); на юг не дальше Z 1760, вольеры
зоопарка и лестница холма E не задеты; путь пешехода от Горной дороги до старта по высотам без прыжков (марши ≤ 7)
с негативами; кровля каньона в выемках; 25 чанков загрузчика; что сносится из этапа 1.
"""
import argparse
import json
import math
import os
import sys
from collections import deque

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO, built_before  # noqa: E402

X0, X1, Z0, Z1 = -664, -530, 1636, 1778           # окно картинки
ICE = 90                                            # верх льда (плотный лёд на Y 89)
HALF = 2.8                                          # полширины льда на прямой (лёд 5 бл.)
EXT = 3.0                                           # в повороте лёд шире наружу на 3 бл. (8 бл.)
RAMP = 10.0                                         # расширение нарастает на 10 бл. до поворота и спадает после
KERB = 1.0                                          # поребрик красно-белый вровень со льдом (в поворотах, с обеих сторон)
RUN = 3.0                                           # зона вылета снаружи поворота (снег вровень, лодку тормозит)
R = 10                                              # радиус поворота по оси
# ось трассы — замкнутая ломаная (повороты по 90°, скругление радиусом R); по часовой, старт — на южной прямой
WAY = [(-546, 1738), (-546, 1652), (-584, 1652), (-584, 1712), (-612, 1712), (-612, 1652),
       (-652, 1652), (-652, 1738)]
START = (-588, 1738)                                # линия старта (на южной прямой, курс на восток)
TUN = 97                                            # грунт ≥ 97 над осью — тоннель (свод на Y 94, над ним ≥ 3 бл. породы)
SAD = 79.0                                          # Горная площадь
PAV = (-592, -584, 1742, 1747)                      # павильон «Старт» (ходим 90.0)
STAND = (-604, -593, 1742, 1748)                    # трибуна у старта: ряды на склоне лицом к прямой
STAIRS = [((-591, -590), 1761, 79.0)] + [((-591, -590), z, 80.0 + i) for i, z in enumerate(range(1760, 1754, -1))] + \
         [((-591, -590), z, 85.0) for z in (1754, 1753)] + [((-591, -590), z, 86.0 + i) for i, z in enumerate(range(1752, 1747, -1))]
LINK = [(-593, 1761), (-592, 1761)]                 # проход с площади к лестнице (79.0), в восточном парапете — проём
ZOO = {'медведи': (-655, -649, 1745, 1754), 'волки': (-655, -652, 1757, 1767), 'купол': (-645, -637, 1745, 1753),
       'контактный': (-645, -634, 1757, 1767), 'ламы': (-633, -626, 1745, 1767)}
LOADER = {(cx, cz) for cx in range(-41, -37) for cz in range(114, 119)} | {(-40, 119), (-39, 119), (-38, 119), (-39, 120), (-38, 120)}
M1 = ('mount-1-ground.json', 'mount-1-tower.json', 'mount-1-build.json')


def centerline(step=0.25):
    """Точки оси: (x, z, s, tx, tz, ext, osign): касательная, расширение наружу в повороте (0…EXT) и сторона
    наружу (+1 — справа по ходу, −1 — слева). Прямые и дуги радиуса R."""
    n = len(WAY)
    raw, arcs = [], []
    s = 0.0
    sgn = lambda v: (v > 0) - (v < 0)
    for i in range(n):
        p0, p1, p2 = WAY[i - 1], WAY[i], WAY[(i + 1) % n]
        a = (sgn(p1[0] - p0[0]), sgn(p1[1] - p0[1]))
        b = (sgn(p2[0] - p1[0]), sgn(p2[1] - p1[1]))
        q0 = (p0[0] + a[0] * R, p0[1] + a[1] * R)
        q1 = (p1[0] - a[0] * R, p1[1] - a[1] * R)
        L = abs(q1[0] - q0[0]) + abs(q1[1] - q0[1])
        for j in range(int(L / step)):
            t = j * step
            raw.append([q0[0] + a[0] * t, q0[1] + a[1] * t, s + t, a[0], a[1]])
        s += L
        c = (p1[0] - a[0] * R + b[0] * R, p1[1] - a[1] * R + b[1] * R)
        cr = a[0] * b[1] - a[1] * b[0]                  # поворот направо (по часовой, z вниз) — cr > 0
        osign = -1 if cr > 0 else 1                     # наружу — в сторону, противоположную центру дуги
        L2 = math.pi / 2 * R
        u = (q1[0] - c[0], q1[1] - c[1]); v = (p1[0] + b[0] * R - c[0], p1[1] + b[1] * R - c[1])
        s0 = s
        for j in range(int(L2 / step)):
            ph = j * step / R
            x = c[0] + u[0] * math.cos(ph) + v[0] * math.sin(ph); z = c[1] + u[1] * math.cos(ph) + v[1] * math.sin(ph)
            tx = -u[0] * math.sin(ph) + v[0] * math.cos(ph); tz = -u[1] * math.sin(ph) + v[1] * math.cos(ph)
            m = math.hypot(tx, tz); raw.append([x, z, s + j * step, tx / m, tz / m])
        s += L2
        arcs.append((s0, s, osign))
    lap = s
    pts = []
    for (x, z, ss, tx, tz) in raw:
        ext, osg = 0.0, 1
        for (a0, a1, o) in arcs:
            d = 0 if a0 <= ss <= a1 else min(abs(ss - a0), abs(ss - a1), lap - abs(ss - a0), lap - abs(ss - a1))
            e = EXT * max(0.0, 1 - d / RAMP)
            if e > ext: ext, osg = e, o
        pts.append((x, z, ss, tx, tz, ext, osg))
    return pts, lap


def raster(pts):
    """Клетки: лёд, поребрик (в поворотах), зона вылета (снаружи поворота), ограждение. По ближайшей точке оси:
    боковое смещение l (+ — наружу поворота) и расширение ext этой точки."""
    near = {}
    reach_ = HALF + EXT + KERB + RUN + 1.5
    for (x, z, ss, tx, tz, ext, osg) in pts:
        for cx in range(math.floor(x - reach_), math.ceil(x + reach_) + 1):
            for cz in range(math.floor(z - reach_), math.ceil(z + reach_) + 1):
                d = math.hypot(cx - x, cz - z)
                if d <= reach_ and ((cx, cz) not in near or d < near[(cx, cz)][0]):
                    lat = (tx * (cz - z) - tz * (cx - x)) * osg        # вправо по ходу = +, умножено на сторону наружу
                    near[(cx, cz)] = (d, ss, lat, ext)
    ice, kerb, run, barrier = set(), set(), set(), set()
    for c, (d, ss, lat, ext) in near.items():
        corner = ext > 0.5
        hi = HALF + ext                                   # наружу
        lo = -HALF                                        # внутрь
        if lo - 0.01 <= lat <= hi + 0.01: ice.add(c)
        elif corner and (hi < lat <= hi + KERB + 0.01 or lo - KERB - 0.01 <= lat < lo): kerb.add(c)
        elif corner and hi + KERB < lat <= hi + KERB + RUN * min(1, ext / EXT) + 0.01: run.add(c)
        elif (not corner and HALF < abs(lat) <= HALF + 1.01) or \
             (corner and (hi + KERB + RUN * min(1, ext / EXT) < lat <= hi + KERB + RUN * min(1, ext / EXT) + 1.01
                          or lo - KERB - 1.01 <= lat < lo - KERB)):
            barrier.add(c)
    run -= ice | kerb
    kerb -= ice
    N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for c in list(run):                                   # зона вылета не касается льда — между ними поребрик
        if any((c[0] + a, c[1] + b) in ice for a, b in N4): run.discard(c); kerb.add(c)
    track = ice | kerb | run
    for c in list(ice):                                   # в повороте лёд не касается ограждения — край льда в поребрик
        if near[c][3] > 0.5 and any((c[0] + a, c[1] + b) not in track for a, b in N4): ice.discard(c); kerb.add(c)
    track = ice | kerb | run
    barrier = {(x + a, z + b) for (x, z) in track for a in (-1, 0, 1) for b in (-1, 0, 1)} - track   # сплошное кольцо
    return ice, kerb, run, barrier, near


class Terr:
    """Грунт до этапа 1 (для сноса) и сейчас; стволы каучуковых деревьев (id ≥ 256) — по соседям."""
    def __init__(self, W):
        self.W, self.c = W, {}

    def __call__(self, x, z):
        k = (x, z)
        if k not in self.c:
            W = self.W
            g, b = W.ground(x, z), W.ground_block(x, z)
            if b is not None and b >= 256:
                nb = [W.ground(x + a, z + c) for a in range(-2, 3) for c in range(-2, 3) if W.ground_block(x + a, z + c) < 256]
                g = min(nb) if nb else g
            built = [y for (xx, y, zz), bb in [] ]
            s = W.surf(x, z)
            self.c[k] = s if s is not None and s < g + 30 and any((x, y, z) in W.pre for y in range(40, 130)) else g
        return self.c[k]


def walk_net():
    """Пешеходная сеть {(x, z): h}: площадь (79), проход, лестница, павильон и трибуна (ряды через 1 бл.)."""
    n = {}
    for x in range(-609, -593):
        for z in range(1761, 1775):
            if not (z == 1774 and x < -606): n[(x, z)] = SAD
    for c in LINK: n[c] = SAD
    for xs, z, h in STAIRS:
        for x in xs: n[(x, z)] = h
    for x in range(PAV[0], PAV[1] + 1):
        for z in range(PAV[2], PAV[3] + 1): n[(x, z)] = float(ICE)
    for x in range(STAND[0], STAND[1] + 1):
        for z in range(STAND[2], STAND[3] + 1): n[(x, z)] = float(ICE + (z - STAND[2]))   # ряд на 1 выше предыдущего
    return n


def reach(net, start, skip=()):
    seen, q = {start}, deque([start])
    stair = {(x, z) for xs, z, h in STAIRS for x in xs} | {c for c in net if STAND[0] <= c[0] <= STAND[1] and STAND[2] <= c[1] <= STAND[3]}
    while q:
        c = q.popleft()
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            m = (c[0] + a, c[1] + b)
            if m not in net or m in skip or m in seen: continue
            lim = 1.0 if (c in stair or m in stair) else 0.5
            if abs(net[m] - net[c]) <= lim: seen.add(m); q.append(m)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'mount-plan-r2.png'))
    args = ap.parse_args()
    W = World(ext=True)
    W0 = World(built_before(M1[0]), ext=True)
    T = Terr(W0)                                     # рельеф без этапа 1 (его сносим)
    pts, lap = centerline()
    ice, kerb, run, barrier, near = raster(pts)
    foot = ice | kerb | run | barrier
    print('== проверки плана ==')
    closed = math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1
    print(f'трасса: круг {lap:.0f} бл. по оси, замкнута: {closed}, лёд {len(ice)} кл., поребрик {len(kerb)}, зона вылета {len(run)}, '
          f'ограждение {len(barrier)}; уровень один — лёд Y {ICE} (плотный лёд на Y {ICE - 1}), поребрик и снег вровень')

    def width_at(p):
        x, z, ss, tx, tz, ext, osg = p
        nx, nz = -tz, tx
        return sum(1 for d in range(-8, 9) if (round(x + nx * d), round(z + nz * d)) in ice)
    straight = [width_at(p) for p in pts[::16] if p[5] == 0]
    apex = [width_at(p) for p in pts[::4] if p[5] >= EXT - 0.01]
    print(f'ширина льда: на прямых мин. {min(straight)} бл. (норма ≥ 5), в вершинах поворотов мин. {min(apex)} бл. (норма ≥ 8) | '
          f'радиус по оси {R}', 'OK' if min(straight) >= 5 and min(apex) >= 8 else 'ОШИБКА')
    # поребрик: в поворотах лёд не касается ни зоны вылета, ни ограждения; зона вылета в вершине каждого поворота ≥ 3 бл.
    N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
    def touches(ic, kb, rn):
        tk = ic | kb | rn
        return [c for c in ic if c in near and near[c][3] > 0.5 and any((c[0] + a, c[1] + b) in rn or (c[0] + a, c[1] + b) not in tk for a, b in N4)]
    touch = touches(ice, kerb, run)
    thin_run = []
    for i, p in enumerate(pts[::4]):
        x, z, ss, tx, tz, ext, osg = p
        if ext < EXT - 0.01: continue
        nx, nz = -tz * osg, tx * osg
        if sum(1 for c in {(round(x + nx * d / 2), round(z + nz * d / 2)) for d in range(24)} if c in run) < 2: thin_run.append((round(x), round(z)))
    print('в поворотах лёд касается зоны вылета или ограждения без поребрика:', len(touch), touch[:3],
          '| вершин поворотов без зоны вылета:', len(thin_run))
    k0 = next(c for c in sorted(kerb) if any((c[0] + a, c[1] + b) in run for a, b in N4) and any((c[0] + a, c[1] + b) in ice for a, b in N4))
    print('НЕГАТИВ: клетка поребрика между льдом и снегом стала льдом — касание найдено:', len(touches(ice | {k0}, kerb - {k0}, run)) > 0)
    track = ice | kerb | run
    leak = [(x + a, z + b) for (x, z) in track for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (x + a, z + b) not in foot]
    print('лодке некуда выйти (сосед льда, поребрика, снега — они же или ограждение):', 'да' if not leak else f'НЕТ {len(leak)} {leak[:3]}')
    edge = sorted(c for c in barrier if any((c[0] + a, c[1] + b) in track for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))))
    neg = set(barrier); c0 = edge[len(edge) // 3]; neg.discard(c0)
    print('НЕГАТИВ: без одного блока ограждения — выход найден:',
          any((x + a, z + b) not in track | neg for (x, z) in track for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))))
    # разные участки трассы не сливаются: соседние клетки полосы с далёкими точками оси
    sof = {c: v[1] for c, v in near.items() if c in foot}
    merge = [(c, m) for c in foot for m in ((c[0] + 1, c[1]), (c[0], c[1] + 1)) if m in foot
             and min(abs(sof[c] - sof[m]), lap - abs(sof[c] - sof[m])) > 40]
    print('участки трассы соприкасаются (полосы разных мест круга рядом):', len(merge), merge[:2])
    # участки по длине круга: тоннель / ущелье / по грунту / насыпь / виадук
    prof, segs, cur = [], [], None
    for (x, z, ss, tx_, tz_, ext_, o_) in pts[::4]:
        g = T(round(x), round(z))
        k = 'тоннель' if g >= TUN and ext_ < 0.5 else 'ущелье' if g >= ICE + 1 else 'по грунту' if g >= ICE - 3 else 'насыпь' if g >= ICE - 6 else 'виадук'
        prof.append((ss, g, k))
        if cur and cur[0] == k: cur[2] = ss; cur[3] = max(cur[3], abs(g - (ICE - 1)))
        else:
            if cur: segs.append(cur)
            cur = [k, ss, ss, abs(g - (ICE - 1))]
    segs.append(cur)
    tot = {}
    for k, a0, a1, m in segs: tot[k] = tot.get(k, 0) + a1 - a0
    print('  по длине круга:', ', '.join(f'{k} {v:.0f} бл.' for k, v in tot.items()))
    print('  участки:', '; '.join(f'{k} {b - a:.0f} бл. ({"глубина" if k in ("ущелье", "тоннель") else "высота"} до {m})'
                                 for k, a, b, m in segs if b - a >= 5))
    tun = [c for c in ice | kerb if T(*c) >= TUN and near[c][3] < 0.5]          # в поворотах — открытое ущелье, свод только на прямых
    thin = [c for c in tun if T(*c) - (ICE + 4) < 3]
    print(f'тоннели: {len(tun)} кл. льда под сводом Y {ICE + 4}; порода над сводом < 3 бл. — {len(thin)} кл. (там — ущелье, не свод)')
    south = max(z for x, z in foot)
    print(f'на юг — до Z {south} (предел Z 1760, дальше телебашня):', 'OK' if south <= 1760 else 'ОШИБКА')
    zoo_hit = sorted({k for k, (a0, b0, c0_, d0) in ZOO.items() for x, z in foot if a0 <= x <= b0 and c0_ <= z <= d0})
    zh = {k: max(ICE - 1 - T(x, z) for x, z in foot if ZOO[k][0] <= x <= ZOO[k][1] and ZOO[k][2] <= z <= ZOO[k][3]) for k in zoo_hit}
    print('над вольерами зоопарка (виадук, опоры — вне вольеров):', {k: f'высота {v}' for k, v in zh.items()} or 'нет')
    print('Северная лестница холма E и Башенная площадь не задеты:', 'да' if not [c for c in foot if c[1] >= 1773] else 'НЕТ')
    xs = [c[0] for c in foot]; zs = [c[1] for c in foot]
    print(f'трасса X {min(xs)}…{max(xs)}, Z {min(zs)}…{max(zs)}; вне участка site.json — {sum(1 for c in foot if not W.inside(*c))} кл. '
          f'(север и восток, рельеф — docs/terrain/mount.json, X −704…−529, Z 1632…1791)')
    net = walk_net()
    on = [c for c in net if c in foot]
    print('пешеходная сеть на трассе:', len(on), on[:3])
    gate = [(x, PAV[2] - 1) for x in range(PAV[0] + 1, PAV[1])]
    print('калитка на лёд из павильона (клетки ограждения → нижние полублоки):', all(g in barrier for g in gate), f'{len(gate)} кл.')
    fl, run_, prev = [], 0, None
    for xs_, z, h in STAIRS:
        if prev is not None and h - prev == 1: run_ += 1
        else:
            if run_: fl.append(run_)
            run_ = 0
        prev = h
    if run_: fl.append(run_)
    print(f'лестница к старту: {SAD} → {ICE}.0, марши {fl} ступ. (норма ≤ 7), площадка 85:', 'OK' if max(fl) <= 7 else 'ОШИБКА',
          f'| трибуна: {STAND[3] - STAND[2] + 1} рядов по {STAND[1] - STAND[0] + 1} мест, ряды через 1 бл. (как ступени)')
    seen = reach(net, (-606, 1774))
    print('путь пешехода с Башенной площади (−606,1774) до павильона и верхнего ряда трибуны без прыжков:',
          (PAV[0] + 2, PAV[2] + 2) in seen and (STAND[0] + 3, STAND[3]) in seen)
    print('НЕГАТИВ: без лестницы павильон недостижим:',
          (PAV[0] + 2, PAV[2] + 2) not in reach(net, (-606, 1774), skip={(x, z) for xs_, z, h in STAIRS for x in xs_}))
    print('НЕГАТИВ: без прохода в парапете площади павильон недостижим:', (PAV[0] + 2, PAV[2] + 2) not in reach(net, (-606, 1774), skip=set(LINK)))
    roofs, pock = [], 0
    for c in foot:
        g = T(*c)
        if g < ICE - 3: continue
        ct = W0.cave_top(*c)
        if ct is None or ct >= g: continue
        if ct >= ICE - 4: pock += 1
        else: roofs.append(ICE - 2 - ct)
    print(f'кровля каньона под льдом в выемках и тоннелях: мин. {min(roofs) if roofs else "—"} (норма ≥ 3); карманов у льда — {pock} кл., '
          f'заделать камнем')
    chunks = {(x >> 4, z >> 4) for x, z in foot}
    print('чанки трассы:', len(chunks), '| в 25 чанках загрузчика:', sorted(chunks & LOADER) or 'нет — только декор')
    keep = set(net) | {(x, 1772) for x in range(-610, -593)} | {(-593, z) for z in range(1761, 1775)} | {(-610, 1772), (-609, 1773)}
    orig = {'mount-1-ground.json': (-624, 70, 1728), 'mount-1-tower.json': (-624, 63, 1758), 'mount-1-build.json': (-624, 60, 1735)}
    tot_d = sum(1 for fn in M1 for e in json.load(open(os.path.join(REPO, 'schemas', fn))) if (e['x'] + orig[fn][0], e['z'] + orig[fn][2]) not in keep)
    print(f'снос этапа 1: {tot_d} записей схем → рельеф как до этапа 1; остаётся Горная площадь с проездом; забор лам X −626, '
          f'Z 1749…1755 выше Y 89 — снять')
    draw(args.out, W, T, pts, lap, ice, kerb, run, barrier, net, segs, prof, near)


def draw(out, W, T, pts, lap, ice, kerb, run, barrier, net, segs, prof, near_):
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    fb = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf') if os.path.exists(f)), None)
    F = lambda n, b=False: ImageFont.truetype(fb if b and fb else fp, n) if fp else ImageFont.load_default()
    S = 6
    ML, MT = 46, 30
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    PH = 170
    img = Image.new('RGB', (ML + mw + 400, MT + mh + PH + 80), (250, 250, 247))
    dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: ML + (x - X0) * S
    pz = lambda z: MT + (z - Z0) * S
    cell = lambda x, z, c: dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            g = T(x, z); w = W.water(x, z)
            if w is not None and w >= g: cell(x, z, (150, 190, 230)); continue
            k = (max(62, min(g, 118)) - 62) / 56
            cell(x, z, (int(215 - 110 * k), int(215 - 80 * k), int(150 - 85 * k)))
            for a, b in ((1, 0), (0, 1)):
                if x + a <= X1 and z + b <= Z1 and T(x, z) // 4 != T(x + a, z + b) // 4:
                    if a: dr.line([px(x + 1), pz(z), px(x + 1), pz(z + 1)], fill=(110, 80, 40, 70))
                    else: dr.line([px(x), pz(z + 1), px(x + 1), pz(z + 1)], fill=(110, 80, 40, 70))
    dr.line([ML, pz(1728), px(-593 + 1), pz(1728)], fill=(0, 0, 0, 200), width=2)
    dr.line([px(-593 + 1), pz(1728), px(-593 + 1), MT + mh], fill=(0, 0, 0, 200), width=2)
    dr.rectangle([px(-624), pz(1728), px(-593 + 1), pz(1775 + 1)], outline=(0, 0, 0, 120), width=1)
    for k, (a, b, c, d) in ZOO.items():
        dr.rectangle([px(a), pz(c), px(b + 1), pz(d + 1)], outline=(160, 60, 20, 220), width=2)
    for x in range(-660, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(10))
    for z in range(1640, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    kind = {}
    for c in ice | kerb:
        g = T(*c)
        kind[c] = 'tun' if g >= TUN and near_[c][3] < 0.5 else 'cut' if g >= ICE + 1 else 'via' if g < ICE - 6 else 'gr'
    for c in barrier: cell(*c, (70, 70, 80, 255) if T(*c) < ICE - 6 else (110, 110, 115, 255))
    for c in run: cell(*c, (250, 252, 255, 255))
    for c in kerb: cell(*c, (210, 40, 40, 255) if (c[0] + c[1]) % 2 else (255, 255, 255, 255))
    for c in ice:
        col = {'tun': (95, 120, 170, 255), 'cut': (130, 170, 235, 255), 'via': (115, 160, 230, 255), 'gr': (155, 195, 245, 255)}[kind[c]]
        cell(*c, col)
    for c in ice:
        if kind[c] == 'tun' and (c[0] + c[1]) % 3 == 0: cell(*c, (70, 90, 140, 255))
    for i in range(60, len(pts) - 40, 200):
        x, z = pts[i][:2]; x2, z2 = pts[i + 30][:2]
        ax, az = px(x) + S / 2, pz(z) + S / 2; bx, bz = px(x2) + S / 2, pz(z2) + S / 2
        dx, dz = bx - ax, bz - az; n = math.hypot(dx, dz) or 1; dx, dz = dx / n, dz / n
        dr.line([ax, az, bx, bz], fill=(200, 30, 30), width=3)
        dr.polygon([(bx + dx * 7, bz + dz * 7), (bx - dz * 5, bz + dx * 5), (bx + dz * 5, bz - dx * 5)], fill=(200, 30, 30))
    sx, sz = START
    for z in range(sz - 3, sz + 4): cell(sx, z, (30, 30, 30, 255) if z % 2 else (255, 255, 255, 255))
    for (x, z), h in net.items():
        st = STAND[0] <= x <= STAND[1] and STAND[2] <= z <= STAND[3]
        cell(x, z, (190, 150, 110, 255) if st else (232, 222, 200, 255) if h == 79.0 else (205, 190, 160, 255) if h < 90 else (240, 235, 215, 255))
    for x in range(STAND[0], STAND[1] + 1): dr.line([px(x), pz(STAND[2]), px(x), pz(STAND[3] + 1)], fill=(120, 80, 50, 120))
    L = lambda x, z, s, sz=10, fill='black': dr.text((px(x), pz(z)), s, fill=fill, font=F(sz), stroke_width=3, stroke_fill=(255, 255, 255))
    L(-586, 1749.5, 'СТАРТ', 10, (40, 90, 160)); L(-606, 1751, 'трибуна', 9, (120, 70, 30))
    L(-606, 1767, 'Горная\nплощадь 79', 9)
    L(-662, 1758, 'ЗООПАРК', 10, (150, 60, 20))
    L(-620, 1776, 'холм E, телебашня →', 9, (60, 60, 60))
    L(-622, 1728, 'тоннель под\nвершиной', 9, (40, 50, 110))
    L(-540, 1676, 'ТОННЕЛЬ\nсквозь\nмассив', 9, (40, 50, 110))
    L(-575, 1690, 'ущелье', 9, (40, 50, 110))
    L(-600, 1692, 'шпилька', 9, (150, 30, 30))
    L(-662, 1639, 'граница участка — Z 1728, X −593 (чёрная рамка)', 9, (40, 40, 40))
    oy = MT + mh + 38
    dr.text((ML, oy - 24), f'Профиль по длине круга ({lap:.0f} бл., от X −642 по южной прямой на восток, по ходу): синяя линия — лёд '
            f'Y {ICE}; штриховка — виадук, тёмное — тоннель', fill='black', font=F(12, True))
    base = oy + PH
    sy = lambda y: base - (y - 56) * 2.6
    sxp = lambda s_: ML + s_ * (mw + 360) / lap
    for y in range(60, 121, 10):
        dr.line([ML, sy(y), ML + mw + 360, sy(y)], fill=(225, 225, 225)); dr.text((8, sy(y) - 6), str(y), fill='black', font=F(9))
    for (s_, g, k), (s2, _, _) in zip(prof, prof[1:]):
        dr.rectangle([sxp(s_), sy(g + 1), sxp(s2) + 1, base], fill=(205, 195, 170))
        if k == 'виадук':
            for yy in range(g + 1, ICE - 1, 3): dr.line([sxp(s_), sy(yy), sxp(s2), sy(yy)], fill=(90, 120, 200))
        if k == 'тоннель': dr.rectangle([sxp(s_), sy(ICE + 4), sxp(s2) + 1, sy(ICE)], fill=(70, 80, 110))
    dr.line([sxp(0), sy(ICE), sxp(lap), sy(ICE)], fill=(40, 100, 220), width=3)
    lx = ML + mw + 20
    dr.text((lx, 10), 'ГОРА F — план, редакция 2', fill='black', font=F(16, True))
    tot = {}
    for k, a0, a1, m in segs: tot[k] = tot.get(k, 0) + a1 - a0
    lines = [('Ледовая трасса для лодок', True), (f' круг {lap:.0f} бл., всё на уровне Y {ICE}', False),
             ('   (лодка вверх не едет — трасса ровная)', False), (' лёд 5 бл. на прямых, 8 — в поворотах;', False),
             (f' повороты радиусом {R}: поребрики красно-', False), ('   белые вровень, снаружи — зона вылета', False),
             ('   3 бл. (снег — тормозит), ограждение', False), ('   с шинами отодвинуто', False),
             (' ' + ', '.join(f'{k} {v:.0f}' for k, v in list(tot.items())[:3]) + ',', False),
             ('   ' + ', '.join(f'{k} {v:.0f}' for k, v in list(tot.items())[3:]) + ' бл.', False), ('', False),
             ('Тоннели и ущелья', True), (' тоннель сквозь восточный массив', False),
             ('   (свод Y 94, свет), ущелья у порталов;', False), (' в поворотах — только открытое ущелье;', False), (' тоннель под вершиной горы F', False),
             ('   с ущельями по сторонам', False), (' шпилька и «змейка» на плато', False),
             (' виадук над низиной к северу от зоопарка', False), ('', False),
             ('Старт', True), (' арка старта со светофором над прямой;', False),
             ('   павильон (навес, судейская будка,', False), ('   калитка на лёд — нижние полублоки);', False),
             ('   трибуна у старта — ряды на склоне;', False), ('   лестница с Горной площади 79 → 90', False),
             (' флаги, рекламные щиты на ограждении', False), ('', False),
             ('Снос этапа 1', True), (' всё, кроме Горной площади; забор лам', False), ('   снять выше Y 89', False), ('', False),
             ('Вне 25 чанков — только декор', True), ('', False),
             ('Обозначения', True), (' голубое — лёд (тёмное — тоннель)', False), (' красно-белое — поребрики', False),
             (' белое — зона вылета, серое — ограждение', False), (' оранжевые рамки — вольеры', False),
             (' красные стрелки — направление', False)]
    for i, (t, b) in enumerate(lines):
        dr.text((lx, 40 + i * 17), t, fill='black', font=F(12, b))
    img.save(out)
    print('план', out, img.size)


if __name__ == '__main__':
    main()
