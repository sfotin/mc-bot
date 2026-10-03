"""План района 10 «Метро и коллектор» v1 (CITY.md §2.4, §7.10): вид сверху, сечения, профили линий.

Решения владельца (2026-10-02): станции линии 1 «Сити» (запад) — «Каньон» — «Центр» — «Парк» — «Промзона»
(восток), линии 2 «Вокзал» (станция-резерв, временный павильон) — «Центр» (пересадка) — «Набережная» (стык
с веткой к куполу); поезда — вагонетки с ускоряющими рельсами, путей два (туда и обратно, правостороннее
движение); коллектор строится вместе с тоннелем.

Общий тоннель под проспектом — ступенчатое сечение: пассажирская часть внизу (Z 1812…1815, пол Y 54, рельсы
55, свод 58), кабельная галерея коллектора рядом и выше (Z 1815…1820, пол 59, внутри 60…62, свод — подоснова
мостовой Y 63), общая стена Z 1815. Галерея на уровне техгалерей промзоны (пол 60) — стык полублоком; отводы
коллектора переходят над пассажирским тоннелем без лестниц. Под прудами Старого города (X −703…−691) галерея
сдвинута на север (Z 1813…1818). Линия 2 под линией 1 и коллектором — на ногах 50, к «Набережной» поднимается
до 57 (зал станции купола), к «Вокзалу» — до 55.

Остановка (одинаковая на всех станциях, проверяется на стенде): по ходу — «впадина» из двух рельсов на блок ниже:
спуск — ускоряющий без питания (вагонетка встаёт на склоне), подъём — ускоряющий на блоке редстоуна; кнопка
на верху блока платформы рядом со спуском даёт питание — вагонетка скатывается и разгоняется. Конечные —
разворот петлёй, остановка одна, на пути прибытия у боковой платформы. Промежуточные «Центр», «Парк» —
островная платформа 6 бл. (марш 3 + проход 3) между разведёнными путями, мезонин (ноги 59) над одним путём,
вестибюль над мезонином; «Каньон» — две боковые платформы, у каждой свой вестибюль, южный проход — под
галереей коллектора.

Пустоты — съёмка по колоннам трасс docs/terrain/metro-voids.json (r.-2.3.mca 2026-10-02, tools/terrain/
terrain_voids.py); там, где пустота задевает трассу, — мост в пустоте (каньон, видовые окна) или закладка камнем.
Между путями двух направлений — промежуток в 1 бл. (линия 1 — Z 1814, линия 2 — X −692): рельсы двух путей не
соседствуют и не «сцепляются» при постановке.

Проверки (печатает; «ОШИБКА» — план не годится): непрерывность путей (шаг 1, перепад ≤ 1, склоны только на
прямых, повороты ровные), пересечения с построенным (BUILT) ниже мостовой (разрешена только засыпка набережной),
свод галереи — под мостовой, разнесение уровней линий и коллектора, резерв трасс, остановки на каждой станции,
ширина платформ ≥ 3, вестибюли не ближе 30 бл., контакт с пустотами (сводка), — и негативы.
Запуск: plan_metro_v1.py [--out docs/districts/metro-plan-v1.png]
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, REPO  # noqa: E402

# ------------------------------------------------------------------ уровни
L1F = 55                       # линия 1: ноги (рельс), пол 54, свод 58
COL_FLOOR, COL_TOP = 59, 62    # коллектор: пол 59, внутри 60…62, свод 63 (подоснова мостовой)
MEZ_F = 59                     # мезонин: пол 58 (= свод путей), ноги 59, внутри 59…62
L2_LOW = 50                    # линия 2 под линией 1
# ------------------------------------------------------------------ линия 1 (оси по X, путь N — на запад, S — на восток)
ZN, ZS = 1813, 1815                # между путями — промежуток Z 1814 (рельсы двух путей не соседствуют)
L1_X = (-793, -595)            # петли разворота на концах
STATIONS_1 = [   # имя, тип, платформа X0…X1, сторона(ы)
    dict(name='Сити', kind='term', x0=-791, x1=-780, side='N'),
    dict(name='Каньон', kind='side', x0=-757, x1=-744),
    dict(name='Центр', kind='island', x0=-689, x1=-676),
    dict(name='Парк', kind='island', x0=-648, x1=-635),
    dict(name='Промзона', kind='term', x0=-608, x1=-597, side='S'),
]
JOG_N, JOG_S = 1810, 1819      # разведение путей у островной платформы: остров Z 1811…1818 (стенка марша 1811,
                               # марш на мезонин 1812…1814, ограждение 1815, проход 1816…1818)
# ------------------------------------------------------------------ линия 2 (оси по Z, путь W — на юг, E — на север)
XW, XE = -693, -691                # промежуток X −692
L2_Z = (1748, 1860)
L2_PROFILE = [(1748, 55), (1779, 55), (1784, 50), (1839, 50), (1846, 57), (1860, 57)]   # (Z, ноги), линейно
STATIONS_2 = [
    dict(name='Вокзал', kind='term', z0=1750, z1=1761, side='E'),
    dict(name='Центр', kind='island', z0=1792, z1=1806),
    dict(name='Набережная', kind='term', z0=1846, z1=1858, side='W'),
]
JOG_W, JOG_E = -694, -686      # остров X −693…−687 (проход 3, марш 3, стенка у пути E)
# ------------------------------------------------------------------ коллектор
COL_X = (-800, -622)
COL_Z = (1816, 1821)           # стены; кабельный ряд 1817, проход 1818…1820
POND_X = (-707, -693)          # под прудами Старого города — сдвиг на север
COL_Z_POND = (1813, 1818)
JUNCTION = (-626, -623, 1821, 1821)       # торцевая стена галереи Заводской (Z 1821, X −626…−623, Y 60…63) — проём;
                                          # галерея: пол 60, внутри 61…63 → коллектор: пол 59 — ступень полублоком
BRANCHES = [  # отводы-заглушки: (имя, x0, x1, z0, z1)
    ('отвод Сити на север', -771, -767, 1809, 1814),
    ('отвод Старого города на север', -673, -669, 1809, 1814),
    ('отвод к набережной на юг', -688, -684, 1821, 1826),
]
MEZZ = {'Центр': (-691, -675, 1808, 1815), 'Парк': (-649, -634, 1808, 1815)}
VESTIBULES = [   # (станция, X0, X1, Z0, Z1) — наземные павильоны
    ('Сити', -784, -781, 1807, 1811),
    ('Каньон, северный', -751, -748, 1806, 1810),
    ('Каньон, южный', -747, -744, 1822, 1826),
    ('Центр', -687, -683, 1804, 1812),
    ('Парк', -643, -640, 1809, 1812),
    ('Промзона', -606, -603, 1821, 1825),
    ('Вокзал (временный)', -689, -686, 1752, 1756),
]
VEST_CENTER = (-687, -683, 1804, 1812)    # павильон «Центр»: вход с запада, лестница в мезонин
KANYON_S_PASS = (-747, -744, 1819, 1822)   # проход от южного вестибюля под галереей коллектора, ноги 55
FILL_OK = {'stone', 'dirt', 'sand', 'gravel'}   # засыпка набережной (embankment-1) — разбирается
FILL_ZONE = (-699, -686, 1845, 1862)


class Survey:
    """Съёмка пустот по трассам (docs/terrain/metro-voids.json, r.-2.3.mca 2026-10-02). Природная пустота —
    воздух/вода/лава съёмки не выше грунта участка и не в построенном (залы и галереи построенного — не она)."""

    def __init__(self, W, path=os.path.join(REPO, 'docs', 'terrain', 'metro-voids.json')):
        self.W, self.parts = W, json.load(open(path))['parts']

    def col(self, x, z):
        for p in self.parts:
            if 0 <= x - p['x0'] < p['w'] and 0 <= z - p['z0'] < p['h']:
                i = (z - p['z0']) * p['w'] + x - p['x0']; return p['ground'][i], p['voids'][i]
        return None

    def covered(self, x, z): return self.col(x, z) is not None

    def natural(self, x, y, z):
        """'a'/'w'/'l' — природная пустота, иначе None."""
        c = self.col(x, z)
        if c is None or (x, y, z) in self.W.pre: return None
        g = self.W.ground(x, z) if self.W.inside(x, z) else c[0]
        if g is None or y > g: return None
        for a, b, t in c[1]:
            if a <= y <= b: return t
        return None

    def ranges(self, x, z):
        c = self.col(x, z)
        if c is None: return []
        return [(a, b, t) for a, b, t in c[1] if any(self.natural(x, y, z) for y in (a, b, (a + b) // 2))]


def lerp_profile(prof, z):
    for (za, fa), (zb, fb) in zip(prof, prof[1:]):
        if za <= z <= zb: return fa + round((fb - fa) * (z - za) / (zb - za)) if zb > za else fa
    raise ValueError(z)


def _stop(cells, i_stop, depth=3):
    """«Впадина» остановки глубиной depth: depth спусков (стоянка — ускоряющие без питания; кнопка питает первый,
    остальные — по цепи), низ (обычный рельс: разрывает цепь, иначе стоянка получит питание от подъёма), depth подъёмов
    (ускоряющие на блоках редстоуна). Стенд 2026-10-02: после горки вагонетка проскакивала впадину глубиной 1 и 2 —
    глубина 3 и ускоряющие по ровному реже (через 24), чтобы вагонетка не копила разгон."""
    seq = [('stop', 1)] + [('stop2', d) for d in range(2, depth + 1)] + [('low', depth)] + \
          [('boost_up', d) for d in range(depth, 0, -1)]
    for k, (kind, d) in zip(range(i_stop, i_stop + len(seq)), seq):
        x, z, f, _ = cells[k]; cells[k] = (x, z, f - d, kind)


STOP_OFF = {'N': 8, 'S': -6, 'W': -6, 'E': 6}            # стоянка от края платформы (x0, x1, z1, z0)


def line1_track(which, stations=STATIONS_1, f0=L1F):
    """Путь линии 1 в направлении движения: N — с востока на запад, S — с запада на восток. (x, z, ноги, вид)."""
    xs = range(L1_X[1] - 1, L1_X[0], -1) if which == 'N' else range(L1_X[0] + 1, L1_X[1])
    home = ZN if which == 'N' else ZS
    zjog = JOG_N if which == 'N' else JOG_S
    cells = []
    isl = [s for s in stations if s['kind'] == 'island']
    for x in xs:
        st = next((s for s in isl if s['x0'] - (2 if which == 'N' else 3) <= x <= s['x1'] + (2 if which == 'N' else 3)), None)
        if st is None: cells.append((x, home, f0, 'rail')); continue
        jw, je = st['x0'] - (2 if which == 'N' else 3), st['x1'] + (2 if which == 'N' else 3)
        if x in (jw, je):                                   # колонна отвода: поворот, прямые по Z, поворот
            zs = range(home, zjog - 1, -1) if which == 'N' else range(home, zjog + 1)
            zs = list(zs)
            first = (which == 'N' and x == je) or (which == 'S' and x == jw)
            seq = zs if first else zs[::-1]
            for j, z in enumerate(seq): cells.append((x, z, f0, 'curve' if j in (0, len(seq) - 1) else 'railz'))
        else:
            cells.append((x, zjog, f0, 'rail'))
    # петли на концах (только путь прибытия ведёт к петле; в списке — концевые клетки разворота)
    loop = [(ZN, 'curve'), (ZN + 1, 'railz'), (ZS, 'curve')]
    if which == 'N': cells += [(L1_X[0], z, f0, k) for z, k in loop]
    else: cells += [(L1_X[1], z, f0, k) for z, k in loop[::-1]]
    # остановки
    for s in stations:
        if s['kind'] == 'term' and s['side'] != which: continue
        if which == 'N':          # на запад: стоянка у западного конца платформы
            i = next(k for k, c in enumerate(cells) if c[0] == s['x0'] + STOP_OFF['N'] and c[3] == 'rail')
        else:
            i = next(k for k, c in enumerate(cells) if c[0] == s['x1'] + STOP_OFF['S'] and c[3] == 'rail')
        _stop(cells, i)
    return cells


def line2_track(which, prof=L2_PROFILE, stations=STATIONS_2):
    """Путь линии 2: W — на юг (Z растёт), E — на север."""
    zs = range(L2_Z[0] + 1, L2_Z[1]) if which == 'W' else range(L2_Z[1] - 1, L2_Z[0], -1)
    home = XW if which == 'W' else XE
    xjog = JOG_W if which == 'W' else JOG_E
    cells = []
    isl = [s for s in stations if s['kind'] == 'island']
    for z in zs:
        f = lerp_profile(prof, z)
        st = next((s for s in isl if s['z0'] - (2 if which == 'W' else 3) <= z <= s['z1'] + (2 if which == 'W' else 3)), None)
        if st is None:
            prev = cells[-1][2] if cells else f
            cells.append((home, z, f, 'slope' if f != prev else 'rail')); continue
        jn, js = st['z0'] - (2 if which == 'W' else 3), st['z1'] + (2 if which == 'W' else 3)
        if z in (jn, js):
            xs = list(range(home, xjog - 1, -1)) if which == 'W' else list(range(home, xjog + 1))
            first = (which == 'W' and z == jn) or (which == 'E' and z == js)
            seq = xs if first else xs[::-1]
            for j, x in enumerate(seq): cells.append((x, z, f, 'curve' if j in (0, len(seq) - 1) else 'rail'))
        else:
            cells.append((xjog, z, f, 'rail'))
    loop = [(XW, 'curve'), (XW + 1, 'rail'), (XE, 'curve')]
    if which == 'W': cells += [(x, L2_Z[1], prof[-1][1], k) for x, k in loop]
    else: cells += [(x, L2_Z[0], prof[0][1], k) for x, k in loop[::-1]]
    for s in stations:
        if s['kind'] == 'term' and s['side'] != which: continue
        if which == 'W': i = next(k for k, c in enumerate(cells) if c[1] == s['z1'] + STOP_OFF['W'] and c[3] == 'rail')
        else: i = next(k for k, c in enumerate(cells) if c[1] == s['z0'] + STOP_OFF['E'] and c[3] == 'rail')
        _stop(cells, i)
    return cells


# ------------------------------------------------------------------ объёмы (коробки X0,X1,Z0,Z1,Y0,Y1, роль)
def boxes(cfg):
    B = []
    st1 = {s['name']: s for s in cfg['st1']}
    xs_station = set()
    for s in cfg['st1']:
        if s['kind'] == 'island':
            x0, x1, z0, z1 = s['x0'] - 4, s['x1'] + 4, 1809, 1820
        elif s['kind'] == 'side':
            x0, x1, z0, z1 = s['x0'] - 1, s['x1'] + 1, 1809, 1819
        elif s['side'] == 'N':
            x0, x1, z0, z1 = min(s['x0'] - 1, L1_X[0] - 1), s['x1'] + 1, 1809, 1816
        else:
            x0, x1, z0, z1 = s['x0'] - 1, max(s['x1'] + 1, L1_X[1] + 1), 1812, 1819
        B.append((x0, x1, z0, z1, L1F - 1, L1F + 3, 'станция ' + s['name']))
        xs_station |= set(range(x0, x1 + 1))
    runs, cur = [], None
    for x in range(L1_X[0] - 1, L1_X[1] + 2):
        if x in xs_station:
            if cur: runs.append(cur); cur = None
        else: cur = [x, x] if cur is None else [cur[0], x]
    if cur: runs.append(cur)
    for a, b in runs: B.append((a, b, 1812, 1816, L1F - 1, L1F + 3, 'тоннель линии 1'))
    for w in ('N', 'S'):                                   # «впадины» остановок: пол на блок ниже
        for x, z, f, k in line1_track(w, cfg['st1']):
            if k in ('stop', 'stop2', 'low', 'boost_up'): B.append((x, x, z, z, f - 1, f - 1, 'впадина остановки линии 1'))
    # коллектор
    px0, px1 = cfg['pond']
    for a, b, z0, z1 in ((cfg['col_x'][0], px0 - 1, *COL_Z), (px0, px1, *COL_Z_POND), (px1 + 1, cfg['col_x'][1], *COL_Z)):
        B.append((a, b, z0, z1, COL_FLOOR, COL_TOP, 'коллектор'))
    B.append((JUNCTION[0], JUNCTION[1], JUNCTION[2], JUNCTION[3], COL_FLOOR + 1, COL_TOP + 1, 'стык с галереей Заводской'))
    for name, x0, x1, z0, z1 in BRANCHES: B.append((x0, x1, z0, z1, COL_FLOOR, COL_TOP, name))
    for name, (x0, x1, z0, z1) in MEZZ.items(): B.append((x0, x1, z0, z1, MEZ_F - 1, cfg['mez_top'], 'мезонин ' + name))
    a, b, c, d = KANYON_S_PASS; B.append((a, b, c, d, L1F - 1, L1F + 3, 'проход «Каньон» юг'))
    # линия 2: по Z — тоннель X −693…−690 по профилю, станции
    st2 = cfg['st2']
    for z in range(L2_Z[0] - 1, L2_Z[1] + 2):
        f = lerp_profile(cfg['prof2'], min(max(z, L2_Z[0]), L2_Z[1]))
        s = next((s for s in st2 if s['z0'] - 3 <= z <= s['z1'] + 3), None)
        if s is None: B.append((XW - 1, XE + 1, z, z, f - 1, f + 3, 'тоннель линии 2'))
        elif s['kind'] == 'island': B.append((JOG_W - 1, JOG_E + 1, z, z, f - 1, f + 3, 'станция ' + s['name'] + ' (л.2)'))
        elif s['side'] == 'E': B.append((XW - 1, XE + 5, z, z, f - 1, f + 3, 'станция ' + s['name']))
        else: B.append((XW - 5, XE + 1, z, z, f - 1, f + 4, 'станция ' + s['name']))
    B.append((-690, -688, 1799, 1807, L2_LOW, MEZ_F + 3, 'пересадочный марш «Центр»'))
    return B


def cfg_default():
    return dict(st1=STATIONS_1, st2=STATIONS_2, prof2=L2_PROFILE, pond=POND_X, col_x=COL_X, mez_top=62,
                vest=VESTIBULES)


# ------------------------------------------------------------------ проверки
def track_issues(cells):
    out = []
    for i, (a, b) in enumerate(zip(cells, cells[1:])):
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1: out.append(('разрыв пути', a[:3], b[:3]))
        if abs(a[2] - b[2]) > 1: out.append(('перепад > 1', a[:3], b[:3]))
        if a[2] != b[2]:
            if b[3] == 'curve' or a[3] == 'curve': out.append(('склон на повороте', a[:3], b[:3]))
            if i + 2 < len(cells):
                c = cells[i + 2]
                if (c[0] - b[0], c[1] - b[1]) != (b[0] - a[0], b[1] - a[1]) and c[3] != 'curve':
                    out.append(('склон не на прямой', b[:3]))
    return out


def built_hits(W, B):
    """Построенное внутри объёмов ниже мостовой (Y ≤ 62). Засыпка набережной в зоне FILL_ZONE — разрешена; твёрдое
    построенное на месте стены или пола (фонари каньона, низ кабельных шахт) остаётся и служит стеной."""
    hits = []
    for x0, x1, z0, z1, y0, y1, role in B:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                for y in range(y0, min(y1, 63) + 1):
                    b = W.pre.get((x, y, z))
                    if b is None or b == 'air': continue
                    fz = FILL_ZONE[0] <= x <= FILL_ZONE[1] and FILL_ZONE[2] <= z <= FILL_ZONE[3]
                    if fz and (b in FILL_OK or (b == 'stonebrick' and x == -698)): continue   # стена зала купола — проём
                    if role.startswith('стык') and b == 'stonebrick': continue                 # торец галереи — проём
                    wall = x in (x0, x1) or z in (z0, z1) or y == y0
                    if wall and not b.startswith('water') and b != 'sand': continue   # построенное в стене остаётся стеной
                    hits.append((role, (x, y, z), b))
    return hits


def roof_issues(W, B):
    """Свод должен быть под землёй/мостовой: над верхом коробки (y1+1) — твёрдое (своё или мира)."""
    out = []
    for x0, x1, z0, z1, y0, y1, role in B:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                s = W.surf(x, z, ymax=130, ymin=20)
                if s is None or s < y1 + 1: out.append((role, (x, z), s))
    return out


def separation_issues(B):
    """Объёмы разных систем не пересекаются (кроме стыков, которые задуманы)."""
    out = []
    groups = {}
    for bx in B:
        role = bx[6]
        g = 'L1' if ('линии 1' in role or (role.startswith('станция') and '(л.2)' not in role and role.split()[-1] in
                                          ('Сити', 'Каньон', 'Центр', 'Парк', 'Промзона'))) else \
            'L2' if ('линии 2' in role or '(л.2)' in role or role in ('станция Вокзал', 'станция Набережная')) else \
            'COL' if ('коллектор' in role or 'отвод' in role or 'стык' in role) else 'PAX'
        groups.setdefault(g, []).append(bx)
    vox = {}
    for g in ('L1', 'L2', 'COL'):
        for x0, x1, z0, z1, y0, y1, role in groups.get(g, []):
            for x in range(x0, x1 + 1):
                for z in range(z0, z1 + 1):
                    for y in range(y0 + (1 if g == 'COL' else 0), y1 + 1):    # пол галереи = свод путей — общий
                        k = (x, y, z)
                        if k in vox and vox[k][0] != g: out.append((vox[k][1], role, k))
                        vox.setdefault(k, (g, role))
    return out


def void_contacts(W, B, SV):
    """Колонны объёмов, где природная пустота (съёмка) — в объёме или в 2 бл. под полом / 1 бл. над сводом."""
    seg = {}
    for x0, x1, z0, z1, y0, y1, role in B:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if any(SV.natural(x, y, z) for y in range(y0 - 2, y1 + 2)): seg.setdefault(role, set()).add((x, z))
    return seg


def checks(cfg, W, verbose=True):
    errs = []
    tracks = {'линия 1 N': line1_track('N', cfg['st1']), 'линия 1 S': line1_track('S', cfg['st1']),
              'линия 2 W': line2_track('W', cfg['prof2'], cfg['st2']), 'линия 2 E': line2_track('E', cfg['prof2'], cfg['st2'])}
    for k, t in tracks.items():
        ti = track_issues(t)
        if verbose: print(f'{k}: {len(t)} рельсов, остановок {sum(1 for c in t if c[3] == "stop")}, ошибок {len(ti)}', ti[:2])
        if ti: errs.append(f'{k}: {ti[0]}')
    # остановки: каждая станция обслужена в своих направлениях
    for s in cfg['st1']:
        need = [s['side']] if s['kind'] == 'term' else ['N', 'S']
        for w in need:
            if not any(c[3] == 'stop' and s['x0'] <= c[0] <= s['x1'] for c in tracks['линия 1 ' + w]):
                errs.append(f'нет остановки «{s["name"]}» на пути {w}')
    for s in cfg['st2']:
        need = [s['side']] if s['kind'] == 'term' else ['W', 'E']
        for w in need:
            if not any(c[3] == 'stop' and s['z0'] <= c[1] <= s['z1'] for c in tracks['линия 2 ' + w]):
                errs.append(f'нет остановки «{s["name"]}» на пути {w}')
    # ширина островных платформ
    isl_w = JOG_S - JOG_N - 1
    if isl_w < 8: errs.append(f'остров линии 1 {isl_w} < 8')
    if JOG_E - JOG_W - 1 < 7: errs.append('остров линии 2 < 7')
    B = boxes(cfg)
    bh = built_hits(W, B)
    if verbose: print(f'пересечения с построенным ниже мостовой: {len(bh)}', bh[:3])
    if bh: errs.append(f'пересечение с построенным: {bh[0]}')
    ri = roof_issues(W, B)
    ri_out = [r for r in ri if r[0] not in ('станция Каньон',)]          # «Каньон» — мост в пустоте, свод виден из каньона
    if verbose: print(f'свод выше поверхности: {len(ri_out)}', ri_out[:3])
    if ri_out: errs.append(f'свод выше поверхности: {ri_out[0]}')
    si = separation_issues(B)
    if verbose: print(f'пересечения систем (линия 1 / линия 2 / коллектор): {len(si)}', si[:2])
    if si: errs.append(f'пересечение систем: {si[0]}')
    # резерв трасс
    for x0, x1, z0, z1, y0, y1, role in B:
        if role == 'тоннель линии 1' and not (1812 <= z0 and z1 <= 1816): errs.append(f'{role} вне резерва')
        if role == 'тоннель линии 2' and not (-698 <= x0 and x1 <= -686): errs.append(f'{role} вне резерва')
    # вестибюли ≥ 30 (разные станции)
    vv = cfg['vest']
    for i in range(len(vv)):
        for j in range(i + 1, len(vv)):
            a, b = vv[i], vv[j]
            if a[0].split(',')[0] == b[0].split(',')[0]: continue
            d = abs((a[1] + a[2]) / 2 - (b[1] + b[2]) / 2) + abs((a[3] + a[4]) / 2 - (b[3] + b[4]) / 2)
            if d < 30: errs.append(f'вестибюли «{a[0]}» и «{b[0]}» ближе 30 ({d:.0f})')
    vc = void_contacts(W, B, Survey(W))
    if verbose:
        print('контакт с природными пустотами (съёмка metro-voids.json): закладка камнем или мост в пустоте')
        for role, cells in sorted(vc.items(), key=lambda kv: -len(kv[1])):
            xs = sorted({c[0] for c in cells}); zs = sorted({c[1] for c in cells})
            print(f'  {role}: {len(cells)} кол., X {xs[0]}…{xs[-1]}, Z {zs[0]}…{zs[-1]}')
    return errs, tracks, B, vc


def negatives(W):
    out = []
    c = cfg_default(); c['prof2'] = [(z, f + 3 if f == L2_LOW else f) for z, f in L2_PROFILE]
    e, *_ = checks(c, W, False); out.append(('линия 2 на 53 — упирается в линию 1', any('систем' in x or 'построен' in x for x in e)))
    c = cfg_default(); c['vest'] = VESTIBULES[:1] + [('Сити-2', -776, -773, 1806, 1810)] + VESTIBULES[1:]
    c['vest'] = [('Каньон, северный', -751, -748, 1806, 1810), ('Сити', -778, -775, 1806, 1810)]
    e, *_ = checks(c, W, False); out.append(('вестибюль «Сити» у X −776', any('ближе 30' in x for x in e)))
    t = line1_track('N'); t[40] = (t[40][0], t[40][1], t[40][2] + 2, 'rail')
    out.append(('перепад пути 2', any('перепад' in x[0] for x in track_issues(t))))
    c = cfg_default(); c['pond'] = (-700, -700)
    e, *_ = checks(c, W, False); out.append(('коллектор без сдвига у прудов', any('построен' in x for x in e)))
    c = cfg_default(); c['mez_top'] = 63
    e, *_ = checks(c, W, False); out.append(('мезонин до Y 63 под мостовой', any('построен' in x for x in e)))
    return out


# ------------------------------------------------------------------ рисунок
def draw(W, out, tracks, B, vc):
    SV = Survey(W)
    X0, X1, Z0, Z1, S = -800, -593, 1744, 1864, 6
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    SEC_H, PR_H = 300, 240
    img = Image.new('RGB', (mw + 70, mh + 60 + SEC_H + 2 * PR_H + 40), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 50 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    built = set((x, z) for (x, y, z), b in W.pre.items() if y >= 63 and b != 'air' and not b.startswith('water') and X0 <= x <= X1 and Z0 <= z <= Z1)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            if (x, z) in built: c = (200, 195, 185)
            elif W.water(x, z): c = (170, 205, 230)
            else: c = (215, 220, 175)
            rg = SV.ranges(x, z) if SV.covered(x, z) else None
            hi = max((r[1] for r in rg), default=None) if rg is not None else W.cave_top(x, z)
            if hi is not None and hi >= 45: c = (c[0], int(c[1] * 0.6), int(c[2] * 0.6)) if hi >= 53 else tuple(int(v * 0.8) for v in c)
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    col = {'L1': (30, 80, 200, 110), 'L2': (20, 150, 70, 110), 'COL': (230, 140, 20, 120), 'PAX': (150, 60, 180, 120)}
    for x0, x1, z0, z1, y0, y1, role in B:
        g = 'COL' if ('коллектор' in role or 'отвод' in role or 'стык' in role) else \
            'L2' if ('линии 2' in role or '(л.2)' in role or role in ('станция Вокзал', 'станция Набережная')) else \
            'PAX' if ('мезонин' in role or 'проход' in role or 'марш' in role) else 'L1'
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], fill=col[g])
    for name, t in tracks.items():
        cc = (20, 40, 140) if 'линия 1' in name else (10, 100, 40)
        for a, b in zip(t, t[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
                dr.line([px(a[0]) + S // 2, pz(a[1]) + S // 2, px(b[0]) + S // 2, pz(b[1]) + S // 2], fill=cc, width=2)
        for c in t:
            if c[3] == 'stop': dr.ellipse([px(c[0]), pz(c[1]), px(c[0]) + S, pz(c[1]) + S], fill=(220, 30, 30))
    for name, x0, x1, z0, z1 in VESTIBULES:
        dr.rectangle([px(x0), pz(z0), px(x1 + 1), pz(z1 + 1)], fill=(255, 255, 255, 200), outline=(150, 20, 120), width=3)
    lab = [(-795, 1800, 'ст. «Сити»\nконечная'), (-762, 1834, 'ст. «Каньон»\nмост в пустоте'), (-700, 1789, 'ст. «Центр»\nпересадка'),
           (-655, 1800, 'ст. «Парк»'), (-614, 1830, 'ст. «Промзона»\nконечная'), (-684, 1750, 'ст. «Вокзал»\n(резерв, павильон)'),
           (-686, 1846, 'ст. «Набережная»\n+ ветка к куполу'), (-640, 1836, 'стык с галереей\nЗаводской'),
           (-735, 1790, 'отвод на север'), (-668, 1797, 'отвод на север'), (-681, 1830, 'отвод на юг')]
    for x, z, t in lab: dr.text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    for x in range(X0, X1 + 1, 10): dr.text((px(x) - 10, 12), str(x), fill='black', font=F(10))
    for z in range(1750, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    leg = [((30, 80, 200), 'линия 1: тоннель и станции (ноги 55)'), ((20, 150, 70), 'линия 2 (ноги 50…57)'),
           ((230, 140, 20), 'коллектор (пол 59, внутри 60…62)'), ((150, 60, 180), 'мезонины, переходы'),
           ((220, 30, 30), 'остановка (впадина, кнопка)'), ((150, 20, 120), 'вестибюль'),
           ((200, 110, 100), 'природная пустота (съёмка), верх ≥ 53')]
    for i, (c, t) in enumerate(leg):
        lx, ly = 50 + i * 250 if i < 4 else 50 + (i - 4) * 250, mh + 34 + (0 if i < 4 else 15)
        dr.rectangle([lx, ly, lx + 12, ly + 10], fill=c); dr.text((lx + 16, ly - 2), t, fill='black', font=F(10))
    # ---- сечения
    y0s = mh + 75
    dr.text((50, y0s), 'Сечения ×14 (подписи — две последние цифры координаты)', fill='black', font=F(12))
    y0s += 30
    def section(ox, items, zr, yr, title):
        sc = 14
        zz = lambda z: ox + (z - zr[0]) * sc; yy = lambda y: y0s + 30 + (yr[1] - y) * sc
        dr.rectangle([zz(zr[0]), yy(yr[1]), zz(zr[1] + 1), yy(yr[0] - 1)], fill=(150, 130, 100))
        for (za, zb, ya, yb, c) in items: dr.rectangle([zz(za), yy(yb), zz(zb + 1) - 1, yy(ya - 1) - 1], fill=c)
        for y in range(yr[0], yr[1] + 1, 2): dr.text((zz(zr[0]) - 22, yy(y) + 2), str(y), fill='black', font=F(9))
        for z in range(zr[0], zr[1] + 1, 2): dr.text((zz(z) + 1, yy(yr[0] - 1) + 2), str(abs(z) % 100), fill='black', font=F(9))
        dr.text((zz(zr[0]), yy(yr[1]) - 30), title, fill='black', font=F(11))
    WALL, AIR, RAIL, CAB, PAVE = (120, 120, 125), (240, 240, 235), (60, 60, 60), (240, 170, 60), (90, 90, 90)
    sec1 = [(1812, 1816, 54, 58, WALL), (1813, 1815, 55, 57, AIR), (1813, 1813, 55, 55, RAIL), (1815, 1815, 55, 55, RAIL),
            (1816, 1821, 59, 62, WALL), (1817, 1820, 60, 62, AIR), (1817, 1817, 60, 62, CAB), (1810, 1823, 63, 64, PAVE)]
    section(70, sec1, (1809, 1823), (52, 65), 'Общий тоннель (по Z): пути N, S;\nгалерея: кабели | проход 3')
    sec2 = [(1809, 1820, 54, 58, WALL), (1810, 1819, 55, 57, AIR), (1810, 1810, 55, 55, RAIL), (1819, 1819, 55, 55, RAIL),
            (1811, 1818, 54, 54, (200, 190, 170)), (1811, 1811, 55, 57, WALL), (1815, 1815, 55, 57, (170, 210, 230)),
            (1808, 1815, 58, 62, WALL), (1809, 1814, 59, 62, AIR),
            (1816, 1821, 59, 62, WALL), (1817, 1820, 60, 62, AIR), (1817, 1817, 60, 62, CAB), (1812, 1814, 55, 58, (190, 150, 220)),
            (1806, 1822, 63, 64, PAVE)]
    section(400, sec2, (1806, 1823), (52, 65), '«Центр», «Парк» (по Z): остров 8 —\nстенка, марш на мезонин 59, ограждение, проход 3')
    sec3 = [(1, 4, 49, 53, WALL), (2, 3, 50, 52, AIR), (2, 3, 50, 50, RAIL)]
    sec3 = [(-694, -690, 49, 53, WALL), (-693, -691, 50, 52, AIR), (-693, -693, 50, 50, RAIL), (-691, -691, 50, 50, RAIL),
            (-696, -686, 54, 58, WALL), (-696, -686, 55, 57, AIR)]
    section(760, sec3, (-697, -685), (47, 60), 'Линия 2 под линией 1 (по X)')
    # ---- профили
    def profile(y0, title, pts, ground, voids, ylo=30, yhi=72, sc=3, vs=4):
        dr.text((50, y0), title, fill='black', font=F(12))
        yy = lambda y: y0 + 20 + (yhi - y) * vs
        for i, (g, f) in enumerate(zip(ground, pts)):
            xx = 50 + i * sc
            dr.rectangle([xx, yy(min(g, yhi)), xx + sc - 1, yy(ylo)], fill=(160, 140, 110))
            v = voids[i]
            if v and v[1] >= ylo: dr.rectangle([xx, yy(min(v[1], yhi)), xx + sc - 1, yy(max(v[0], ylo))], fill=(60, 50, 50))
            for (a, b, c) in f: dr.rectangle([xx, yy(b), xx + sc - 1, yy(a) - 1], fill=c)
        for y in range(ylo, yhi + 1, 10):
            dr.line([46, yy(y), 50, yy(y)], fill='black'); dr.text((20, yy(y) - 6), str(y), fill='black', font=F(9))
    def vv(x, z):
        rg = SV.ranges(x, z)
        return (min(r[0] for r in rg), max(r[1] for r in rg)) if rg else None
    t1 = tracks['линия 1 S']
    xs = sorted({c[0] for c in t1})
    fmap = {c[0]: c[2] for c in t1 if c[3] in ('rail', 'stop', 'stop2', 'low', 'boost_up', 'curve')}
    p1 = [[(fmap.get(x, L1F), fmap.get(x, L1F) + 2, (60, 110, 220)), (COL_FLOOR + 1, COL_TOP, (240, 160, 40))] for x in xs]
    profile(y0s + SEC_H - 30, 'Профиль линии 1 по Z 1815 (X −794…−594, ×3): рельеф по оси, природные пустоты (съёмка), путь, коллектор',
            p1, [W.surf(x, 1815, ymax=75) or 60 for x in xs], [vv(x, 1815) for x in xs])
    zs = list(range(L2_Z[0], L2_Z[1] + 1))
    p2 = [[(lerp_profile(L2_PROFILE, z), lerp_profile(L2_PROFILE, z) + 2, (40, 160, 80))] for z in zs]
    profile(y0s + SEC_H - 30 + PR_H - 30, 'Профиль линии 2 по X −693 (Z 1748…1860, ×5): «Вокзал» 55 → «Центр» 50 (под линией 1) → «Набережная» 57',
            p2, [W.surf(-693, z, ymax=75) or 60 for z in zs], [vv(-693, z) for z in zs], sc=5)
    os.makedirs(os.path.dirname(out), exist_ok=True); img.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'metro-plan-v1.png'))
    a = ap.parse_args()
    W = World()
    errs, tracks, B, vc = checks(cfg_default(), W)
    for name, ok in negatives(W):
        print(f'негатив «{name}»: ' + ('ловит' if ok else 'НЕ ЛОВИТ'))
        if not ok: errs.append(f'негатив «{name}» не ловит')
    draw(W, a.out, tracks, B, vc)
    print('ОШИБКИ:\n  ' + '\n  '.join(map(str, errs)) if errs else 'проверки плана чистые')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
