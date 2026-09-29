"""План района «Сити» v1 (CITY.md §7.4): рельеф + всё построенное (world_model.py),
каньон (caves.json), улицы, площадь, Каньон-парк, башни разной формы и этапы,
резерв трасс метро 1 и коллектора (CITY.md §2.4), силуэты с моря и с запада.

Формы башен заданы объёмами occ(x, y, z) — черновики для генераторов этапов 4–7.

Запуск: plan_city_v1.py [--out docs/districts/city-plan-v1.png]
Печатает сводку проверок плана: границы района, пересечения объектов, здания вне
полосы каньона, кровля каньона под зданиями (норма >= 3), резерв трасс, стык улиц
со Старым городом.
"""
import argparse
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO  # noqa: E402

X0, X1, Z0, Z1 = -806, -700, 1768, 1868      # окно картинки
DX0, DX1, DZ0, DZ1 = -800, -725, 1776, 1848  # район (CITY.md §2.3; юг — до улицы-набережной Z 1849)
S = 9
ML, MT = 46, 30
G0 = 67                                      # уровень площадок

AV = (95, 95, 95, 225)
ST = (150, 150, 150, 225)
WALK = (205, 200, 190, 230)
SQ = (232, 222, 196, 235)

# ---- улицы: (ключ, подпись, X0, X1, Z0, Z1, этап, заливка) ----
STREETS = [
    ('av', 'главный проспект', -800, -725, 1814, 1818, 2, AV),
    ('av_n', 'тротуар', -800, -725, 1812, 1813, 2, WALK),
    ('av_s', 'тротуар', -800, -725, 1819, 1820, 2, WALK),
    ('pr', 'проспект Сити', -771, -767, 1776, 1848, 2, AV),       # ось дороги мыса X −771…−767
    ('st_n', 'Северная ул.', -784, -730, 1788, 1792, 2, ST),       # продолжение переулка Z 1789…1791
    ('st_s', 'Южная ул.', -800, -730, 1838, 1842, 2, ST),          # продолжение переулка Z 1839…1841
    ('st_b', 'Пограничная ул.', -729, -725, 1776, 1848, 2, ST),    # стык со Старым городом
    ('al', 'аллея', -747, -740, 1793, 1811, 3, WALK),              # пешеходная: Северная ул. — проспект, вход в Биржу
]


# ---- формы башен: occ(x, y, z) -> bool ----
def t_opener(x, y, z):
    """«Открывашка»: квадрат 13×13, углы СЗ и ЮВ срезаются к верху до лезвия по диагонали;
    вверху — трапециевидный сквозной проём (Шанхайский ВФЦ)."""
    cx, cz, top = -758, 1803, 190
    dx, dz = x - cx, z - cz
    if not (abs(dx) <= 6 and abs(dz) <= 6 and G0 <= y <= top): return False
    t = (y - G0) / (top - G0)
    if abs(dx - dz) > 12 * (1 - t ** 1.3) + 1.5: return False
    if 166 <= y <= 182 and abs(dx + dz) <= 3 + (y - 166) * 0.25: return False
    return True


def t_gate(x, y, z):
    """«Ворота»: две ноги с общим подиумом внизу и консолью-перемычкой вверху (петля, CCTV)."""
    if not (1831 <= z <= 1837 and G0 <= y <= 150): return False
    sh = (y - G0) // 24                                            # ноги наклонены друг к другу
    leg1 = -756 + sh <= x <= -750 + sh
    leg2 = -739 - sh <= x <= -733 - sh
    base = -756 <= x <= -733 and y <= 74
    top = -756 <= x <= -733 and 136 <= y
    return leg1 or leg2 or base or top


def t_bridge(x, y, z):
    """«Мост» (Биржа): два корпуса-опоры, над проездом Z 1800…1804 — этажи на мосту,
    вверху этажи шире (как ToHA)."""
    if not (-739 <= x <= -730 and 1795 <= z <= 1809 and G0 <= y <= 100): return False
    if y < 81 and 1800 <= z <= 1804: return False
    if y >= 88: return True
    return -738 <= x <= -731 and (1796 <= z <= 1808)


def t_sail(x, y, z):
    """«Парус»: мачта по западной стороне, парус выгнут к морю (восток/юго-восток),
    к верху сужается в мачту."""
    if not (-797 <= x <= -786 and 1822 <= z <= 1833 and G0 <= y <= 175): return False
    t = min(1, (y - G0) / (165 - G0))
    u = (z - 1827.5) / 5.8
    if abs(u) > 1: return False
    w = 11 * (1 - t ** 1.8) * math.sqrt(max(0, 1 - u * u))
    if y > 165: return x <= -796 and 1827 <= z <= 1828      # шпиль-мачта
    return x - (-797) <= max(1.2, w)


def pebble(cx, cz, rx, rz, top):
    def f(x, y, z):
        if not (G0 - 13 <= y <= top): return False
        t = max(0, (y - G0) / (top - G0))
        k = math.sqrt(max(0, 1 - t ** 4))
        return ((x - cx) / (rx * k + 0.01)) ** 2 + ((z - cz) / (rz * k + 0.01)) ** 2 <= 1
    return f


def t_spiral(x, y, z):
    """«Спираль»: квадрат 8×8, этажи поворачиваются, к верху на 135° (как «Эволюция»)."""
    cx, cz, top = -780, 1782, 150
    if not (G0 <= y <= top): return False
    a = math.radians(135 * (y - G0) / (top - G0))
    dx, dz = x - cx, z - cz
    u, v = dx * math.cos(a) + dz * math.sin(a), -dx * math.sin(a) + dz * math.cos(a)
    return abs(u) <= 4 and abs(v) <= 4


def t_deck(x, y, z):
    """«Три башни»: три корпуса 7×9 и палуба-парк на крыше Y 129…132 (как Marina Bay Sands)."""
    if not (1777 <= z <= 1785 and G0 <= y <= 132): return False
    if y >= 129: return -766 <= x <= -734 and 1778 <= z <= 1784
    return any(a <= x <= a + 6 for a in (-764, -754, -744))


def t_ring(x, y, z):
    """«Подкова»: кольцо-отель плоскостью к морю, наружный Ø 25, проём Ø 13."""
    if not (1843 <= z <= 1847 and G0 <= y): return False
    r = math.hypot(x - (-750), y - 79)
    return 6.5 <= r <= 12.5


TW = (150, 185, 215, 250)
# (ключ, подпись, X0, X1, Z0, Z1, этап, occ, заливка, верх Y)
TOWERS = [
    ('t1', '«Открывашка»', -764, -752, 1797, 1809, 4, t_opener, (120, 170, 215, 250), 190),
    ('t2', '«Ворота»', -756, -733, 1831, 1837, 5, t_gate, (150, 200, 230, 250), 150),
    ('t3', '«Мост» (Биржа)', -739, -730, 1795, 1809, 5, t_bridge, (205, 215, 225, 250), 100),
    ('t4', '«Парус»', -797, -786, 1822, 1833, 6, t_sail, (235, 240, 245, 250), 175),
    ('t5a', '«Галька» 1', -800, -790, 1794, 1804, 6, pebble(-795, 1799, 5.5, 5.0, 160), (245, 245, 240, 250), 160),
    ('t5b', '«Галька» 2', -788, -780, 1795, 1803, 6, pebble(-784, 1799, 4.5, 4.0, 135), (245, 245, 240, 250), 135),
    ('t5c', '«Галька» 3', -797, -789, 1806, 1811, 6, pebble(-793, 1808.5, 4.0, 2.8, 115), (245, 245, 240, 250), 115),
    ('t6', '«Спираль»', -786, -774, 1776, 1788, 7, t_spiral, (110, 160, 150, 250), 150),
    ('t7', '«Три башни»', -766, -734, 1777, 1785, 7, t_deck, (130, 150, 190, 250), 132),
    ('t8', '«Подкова»', -762, -738, 1843, 1847, 7, t_ring, (90, 120, 220, 250), 91),
]
OTHER = [('sq', 'Площадь Сити', -766, -744, 1821, 1829, 3), ('sq2', 'сквер с фонтаном', -743, -730, 1821, 1829, 3),
         ('look', 'смотровая «Провал»', -788, -777, 1844, 1855, 3), ('top', 'площадка «Вершина»', -800, -792, 1784, 1793, 6)]
# дорожки (мощение) к каждому объекту: (ключ, X0, X1, Z0, Z1, этап)
PATHS = [('p_t1', -764, -752, 1810, 1811, 4), ('p_t1w', -766, -765, 1797, 1811, 4), ('p_vn', -751, -748, 1811, 1811, 3),
         ('p_ex', -739, -730, 1800, 1804, 5), ('p_t7', -766, -734, 1786, 1787, 7), ('p_t6', -785, -775, 1787, 1787, 7),
         ('p_hill', -788, -781, 1804, 1811, 6), ('p_hill_n', -791, -780, 1793, 1793, 6), ('p_hill_c', -789, -789, 1794, 1803, 6),
         ('p_t4', -786, -785, 1821, 1837, 6), ('p_t2', -756, -730, 1830, 1830, 5), ('p_sea', -766, -730, 1848, 1848, 7),
         ('p_look', -783, -781, 1843, 1843, 3), ('p_pond', -781, -772, 1803, 1803, 3),
         ('p_park', -784, -772, 1830, 1830, 3), ('p_top', -791, -786, 1786, 1787, 6)]   # подъём на «Вершину» ступенями   # аллея Каньон-парка: «Парус» — «Шар» — проспект Сити
POND = (-780, -773, 1804, 1811)          # пруд в естественной ложбине (−778, 1810), вода вровень с берегом (§6)
FOUNTAIN = (-741, -733, 1821, 1829)      # фонтан «Сити» 9×9 (DECOR §5.3)
INSTALL = [('«Кристалл»', -766, -763, 1821, 1824), ('«Шар»', -779, -777, 1833, 1835)]   # арт-объекты: стекло + морской фонарь
WALL_PASS = [(-771, -767), (-738, -736)]  # проходы в подпорной стенке Z 1849 (Y 67 → 64 ступенями) к улице-набережной


def balloon(x, y, z):
    """Воздушный шар над «Вершиной» — висит статично, без тросов, выше «Гальки» (иначе с моря
    его не видно): оболочка-капля Ø 11 (Y 172…187), корзина 3×3 на Y 167…168, стропы по углам (забор)."""
    cx, cz = -795, 1787.5
    r = math.hypot(x - cx, z - cz)
    if 172 <= y <= 187:
        R_ = 5.5 * math.sqrt(max(0, 1 - ((y - 181) / 6.5) ** 2)) if y >= 175 else 2 + (y - 172) * 1.1
        return r <= R_
    if 167 <= y <= 168: return abs(x - cx) <= 1 and abs(z - cz) <= 1.5
    if 169 <= y <= 171: return abs(x - cx) == 1 and abs(z - cz) == 1.5
    return False


BALLOON = {(x, y, z) for x in range(-802, -787) for z in range(1779, 1797) for y in range(166, 189) if balloon(x, y, z)}
# вертолётная площадка на крыше «Ворот» (Y 151, над восточной ногой) и вертолёт в воздухе рядом
HELIPAD = (-742, -734, 1830, 1838, 151)   # 9×9, края по Z — консоли на 1 бл.; разметка «H» в круге, огни по краю


def heli(x, y, z):
    """Вертолёт (статично висит): корпус 5×3×3 вдоль X носом на запад, стекло кабины, хвостовая балка,
    хвостовой винт, полозья; несущий винт — крест 9 бл. на Y 165."""
    cx, cy, cz = -744, 161, 1843
    dx, dy, dz = x - cx, y - cy, z - cz
    body = -2 <= dx <= 2 and 0 <= dy <= 2 and abs(dz) <= 1
    tail = 3 <= dx <= 7 and dy == 2 and dz == 0
    fin = dx == 7 and 3 <= dy <= 4 and dz == 0
    skid = -2 <= dx <= 2 and dy == -1 and abs(dz) == 1
    mast = dx == 0 and dy == 3 and dz == 0
    rotor = dy == 4 and ((dz == 0 and abs(dx) <= 4) or (dx == 0 and abs(dz) <= 4))
    return body or tail or fin or skid or mast or rotor


HELI = {(x, y, z) for x in range(-750, -735) for z in range(1837, 1850) for y in range(158, 167) if heli(x, y, z)}
VEST = ('вестибюль «Каньон» Ю', -747, -744, 1822, 1826)   # после схемы тоннеля (как в Старом городе)
VEST_N = ('вестибюль «Каньон» С', -751, -748, 1806, 1810)
# резерв трасс (CITY.md §2.4): без фундаментов ниже Y 60; отвод коллектора на север — под проспектом Сити
RESERVE = [('общий тоннель метро 1 + коллектор', -800, -725, 1812, 1820),
           ('отвод коллектора на север (под проспектом Сити)', -771, -767, 1776, 1811)]
STATION = ('Каньон (л. 1)', -756, -744, 1814, 1818)     # зал на мосту в пустоте каньона


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'city-plan-v1.png'))
    args = ap.parse_args()
    W = World()
    cv = W._cv
    air = lambda x, z: cv['air'][(z - cv['z0']) * cv['w'] + x - cv['x0']] or 0

    canyon = {(x, z) for x in range(X0, X1 + 1) for z in range(Z0, Z1 + 1)
              if air(x, z) >= 8 and (W.cave_top(x, z) or 0) >= 50}
    park = {(x + dx, z + dz) for (x, z) in canyon for dx in range(-2, 3) for dz in range(-2, 3)
            if DZ0 + 20 <= z + dz <= DZ1 and DX0 <= x + dx <= DX1}
    sink = {(x, z) for x in range(DX0, DX1 + 1) for z in range(DZ0, 1856) if W.surf(x, z) < 50}

    # объёмы башен: foot — след на земле (y <= G0 + 2), plan — проекция сверху
    vol = {}
    for k, _, x0, x1, z0, z1, st, occ, *_r in TOWERS:
        vol[k] = {(x, y, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) for y in range(G0 - 13, 200) if occ(x, y, z)}
    plan = {k: {(x, z) for x, y, z in v} for k, v in vol.items()}
    foot = {k: {(x, z) for x, y, z in v if y <= G0 + 2} for k, v in vol.items()}

    print('== проверки плана ==')
    area = {}
    for k, _, x0, x1, z0, z1, *_ in STREETS + OTHER:
        zmax = 1855 if k == 'look' else DZ1
        assert DX0 <= x0 <= x1 <= DX1 and DZ0 <= z0 <= z1 <= zmax, ('вне района', k)
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                area.setdefault((x, z), []).append(k)
    for k, x0, x1, z0, z1, st in PATHS:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1): area.setdefault((x, z), []).append(k)
    for k, (_, x0, x1, z0, z1) in (('vs', VEST), ('vn', VEST_N)):
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1): area.setdefault((x, z), []).append(k)
    for x in range(POND[0], POND[1] + 1):
        for z in range(POND[2], POND[3] + 1): area.setdefault((x, z), []).append('pond')
    ppark = set()                              # дорожки Каньон-парка — в PATHS (p_park)
    for k, c in foot.items():
        assert all(DX0 <= x <= DX1 and DZ0 <= z <= DZ1 for x, z in plan[k]), ('вне района', k)
        for xz in c: area.setdefault(xz, []).append(k)
    ok = {frozenset(p) for p in (('sq', 'vs'), ('p_hill', 'pond'), ('av', 'pr'), ('st_n', 'pr'), ('st_s', 'pr'), ('st_b', 'av'), ('st_b', 'st_n'),
                                  ('st_b', 'st_s'), ('av_n', 'pr'), ('av_s', 'pr'), ('av_n', 'st_b'), ('av_s', 'st_b'))}
    bad = sorted({tuple(sorted(v)) for v in area.values() if len(v) > 1 and frozenset(v) not in ok})
    print('пересечения объектов (следы на земле):', 'нет' if not bad else bad)
    over = {}
    for k, c in plan.items():                 # верхние части над улицами — консоли, допустимо
        s = {n for xz in c - foot[k] for n in area.get(xz, []) if n in ('pr', 'st_n', 'st_s', 'av', 'al')}
        if s: over[k] = sorted(s)
    print('консоли над улицами:', over or 'нет')
    print('здания в полосе каньона (+2 бл.):', {k: len(c & park) for k, c in foot.items() if c & park} or 'нет')
    for k, name, x0, x1, z0, z1, st, occ, fill, top in TOWERS:
        ys = [W.surf(x, z) for x, z in foot[k]]
        roofs = [W.surf(x, z) - W.cave_top(x, z) for x, z in foot[k] if W.cave_top(x, z) is not None and air(x, z) >= 3]
        print(f'{k:4s} {name:15s} этап {st}: след {len(foot[k])} кл., рельеф Y {min(ys)}…{max(ys)}, верх Y {top} '
              f'(≈{(top - G0) // 4} эт.), объём {len(vol[k])} бл., кровля каньона мин. {min(roofs) if roofs else "—"}')
    rv = sorted({(k, n) for n, x0, x1, z0, z1 in RESERVE for k, c in foot.items()
                 for x, z in c if x0 <= x <= x1 and z0 <= z <= z1})
    print('здания над резервом трасс:', rv or 'нет')
    # связность: от проспекта по мощению (улицы, тротуары, дорожки, площади) до каждого здания и вестибюля
    def lonely(skip=()):
        names = set([s_[0] for s_ in STREETS] + [p_[0] for p_ in PATHS] + ['sq', 'sq2', 'look']) - set(skip)
        paved = {c for c, v in area.items() if any(n in names for n in v)}
        seen, st_ = set(), [(-760, 1816)]
        while st_:
            c = st_.pop()
            if c in seen or c not in paved: continue
            seen.add(c); st_ += [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]
        touch = lambda cells: any((x + a_, z + b_) in seen for x, z in cells for a_, b_ in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        out = [k for k, c in foot.items() if not touch(c)]
        for nm, x0, x1, z0, z1 in (VEST, VEST_N, ('пруд', *POND), ('«Вершина»', -800, -792, 1784, 1793)):
            if not touch({(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}): out.append(nm)
        return out, len(seen)
    lone, nseen = lonely()
    print('объекты без мощёной дорожки от проспекта:', lone or 'нет', f'| мощёных клеток в сети {nseen}')
    print('НЕГАТИВ: без дорожки к «Парусу» он отрезан:', 't4' in lonely(('p_t4',))[0])
    print('окно в каньон (площадь, над пустотой):',
          len({(x, z) for x in range(-766, -743) for z in range(1821, 1830)} & canyon), 'кл.')
    print('естественный провал до каньона: клеток', len(sink), '| дно Y', min(W.surf(x, z) for x, z in sink))
    for nm, z in (('проспект', 1816), ('переулок С', 1790), ('переулок Ю', 1840)):
        print(f'стык Старый город X −724/−725, {nm} Z {z}: Y {W.surf(-724, z)} / {W.surf(-725, z)}')
    hx0, hx1, hz0, hz1, hy = HELIPAD
    above = [(x, y, z) for k, v in vol.items() for (x, y, z) in v if hx0 <= x <= hx1 and hz0 <= z <= hz1 and y >= hy]
    under = sum(1 for x in range(hx0, hx1 + 1) for z in range(hz0, hz1 + 1) if (x, hy - 1, z) in vol['t2'])
    hit = [k for k, v in vol.items() if v & HELI] + (['шар'] if BALLOON & HELI else [])
    print(f'вертолётная площадка «Ворота» Y {hy}: 9×9, над ней препятствий {len(above)}, опора крышей {under}/81 кл. '
          f'(остальное — консоли); вертолёт {len(HELI)} бл., пересечений {hit or "нет"}')
    built = [k for k, c in plan.items() if any((x, y, z) in W.pre for x, z in c for y in range(55, 200))]
    print('объекты поверх построенного:', built or 'нет')

    # ---------- картинка ----------
    def colr(x, z):
        y = 120
        while y > 20 and W.block(x, y, z) in ('air', 'plant'): y -= 1
        b = W.block(x, y, z)
        if b == 'water' or b.startswith('flowing_water'):
            yb = y
            while yb > 30 and W.block(x, yb, z) == 'water': yb -= 1
            d = min(y - yb, 16)
            return (int(150 - 7 * d), int(195 - 7 * d), int(235 - 3 * d))
        if b != 'ground': return (185, 180, 172)
        if y < 55: return (40, 30, 30)
        k = (max(62, min(y, 80)) - 62) / 18
        return (int(215 - 85 * k), int(212 - 60 * k), int(150 - 70 * k))

    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    fb = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf') if os.path.exists(f)), None)
    F = lambda n, b=False: ImageFont.truetype(fb if b and fb else fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    SK = 3
    YS0, YS1 = 60, 200
    skh = (YS1 - YS0) * SK
    wv = (1860 - 1772) * SK                               # силуэт с запада
    img = Image.new('RGB', (ML + mw + 470, MT + mh + 60 + skh + 40), (250, 250, 247))
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

    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            rect(x, x, z, z, colr(x, z))
    for (x, z) in park: rect(x, x, z, z, (120, 175, 95, 200))
    for (x, z) in canyon:
        if (x + z) % 2 == 0:
            dr.line([px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z)], fill=(200, 30, 30, 230), width=2)
    for x in range(X0, X1 + 2):
        if x % 16 == 0: dr.line([px(x), MT, px(x), MT + mh], fill=(90, 90, 90, 110), width=1)
    for z in range(Z0, Z1 + 2):
        if z % 16 == 0: dr.line([ML, pz(z), ML + mw, pz(z)], fill=(90, 90, 90, 110), width=1)
    for x in range(-800, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1770, Z1 + 1, 10): dr.text((4, pz(z) - 6), str(z), fill='black', font=F(11))
    dashed(DX0, DX1, DZ0, DZ1, (0, 0, 0, 200), 2, 8)
    for k, _, x0, x1, z0, z1, st, fill in STREETS:
        rect(x0, x1, z0, z1, fill)
    for k, name, x0, x1, z0, z1, st in OTHER:
        rect(x0, x1, z0, z1, SQ, (140, 120, 90))
    wx = {(x, z) for x in range(-766, -743) for z in range(1821, 1830)} & canyon
    PATH_C = (225, 215, 195, 255)
    for k, x0, x1, z0, z1, st in PATHS: rect(x0, x1, z0, z1, PATH_C)
    bplan = {(x, z) for x, y, z in BALLOON}
    for (x, z) in bplan:
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, z + dz) not in bplan:
                a = {(1, 0): (px(x + 1) - 1, pz(z), px(x + 1) - 1, pz(z + 1) - 1), (-1, 0): (px(x), pz(z), px(x), pz(z + 1) - 1),
                     (0, 1): (px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z + 1) - 1), (0, -1): (px(x), pz(z), px(x + 1) - 1, pz(z))}[(dx, dz)]
                dr.line(a, fill=(200, 60, 40), width=2)
    for (x, z) in ppark: rect(x, x, z, z, PATH_C)
    x0, x1, z0, z1 = POND
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if (x in (x0, x1)) and (z in (z0, z1)): continue          # углы срезаны
            rect(x, x, z, z, (70, 130, 215, 255))
    x0, x1, z0, z1 = FOUNTAIN
    cx, cz = px(x0), pz(z0)
    dr.ellipse([cx, cz, px(x1 + 1), pz(z1 + 1)], fill=(110, 170, 230), outline=(40, 90, 150), width=2)
    dr.ellipse([cx + 3 * S, cz + 3 * S, px(x1 + 1) - 3 * S, pz(z1 + 1) - 3 * S], fill=(230, 230, 225), outline=(90, 90, 90))
    for nm, x0, x1, z0, z1 in INSTALL:
        dr.polygon([(px(x0), pz(z1 + 1)), ((px(x0) + px(x1 + 1)) / 2, pz(z0)), (px(x1 + 1), pz(z1 + 1))],
                   fill=(180, 240, 250), outline=(0, 110, 140))
    for x0, x1 in WALL_PASS: rect(x0, x1, 1849, 1849, PATH_C, (120, 90, 50), 1)
    # озеленение: деревья (зелёный круг), клумбы (розовые), скамейки (коричневые)
    occupied = set(area) | set(canyon & {c for c in area})
    trees, beds, benches = [], [], []
    for x in range(-792, -726, 8):                                     # вдоль проспекта, между фонарями
        for z in (1812, 1820):
            if not (-772 <= x <= -766) and all(n in ('av_n', 'av_s') for n in area.get((x, z), ['av_n'])): trees.append((x, z))
    for (x, z) in park:                                                # Каньон-парк
        if (x, z) in area or (x, z) in wx: continue
        if (x * 3 + z * 5) % 11 == 0 and not any((x + a, z + b) in ppark for a in (-1, 0, 1) for b in (-1, 0, 1)):
            trees.append((x, z))
    for x in range(-799, -725):                                        # газоны вне объектов: редкие деревья
        for z in range(1793, 1848):
            if (x, z) in area or (x, z) in park or (x, z) in sink: continue
            if (x * 7 + z * 3) % 29 == 0 and all((x + a, z + b) not in area for a in (-1, 0, 1) for b in (-1, 0, 1)):
                trees.append((x, z))
    beds = [(-764, 1810), (-752, 1810), (-743, 1823), (-743, 1827), (-731, 1823), (-731, 1827), (-782, 1804), (-782, 1811),
            (-765, 1825), (-784, 1836), (-784, 1822)]
    benches = [(-742, 1825, 'v'), (-732, 1825, 'v'), (-737, 1829, 'h'), (-782, 1807, 'v'), (-772, 1807, 'v'),
               (-786, 1843, 'h'), (-778, 1843, 'h'), (-762, 1828, 'h'), (-748, 1828, 'h')]
    benches += [(-782, 1831, 'h'), (-775, 1831, 'h')]
    for (x, z) in trees:
        dr.ellipse([px(x) - 3, pz(z) - 3, px(x) + S + 2, pz(z) + S + 2], fill=(40, 130, 50), outline=(20, 70, 20))
    for (x, z) in beds:
        dr.rectangle([px(x) + 1, pz(z) + 1, px(x) + S - 2, pz(z) + S - 2], fill=(235, 110, 170), outline=(140, 40, 90))
    for (x, z, o) in benches:
        if o == 'h': dr.rectangle([px(x) - S // 2, pz(z) + 3, px(x) + S + S // 2, pz(z) + S - 3], fill=(140, 90, 40))
        else: dr.rectangle([px(x) + 3, pz(z) - S // 2, px(x) + S - 3, pz(z) + S + S // 2], fill=(140, 90, 40))
    print(f'озеленение: деревьев {len(trees)}, клумб {len(beds)}, скамеек {len(benches)}')
    for (x, z) in canyon:
        if (x + z) % 4 == 0 and (x, z) not in {c for f in plan.values() for c in f}:
            dr.line([px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z)], fill=(200, 30, 30, 200), width=2)
    wx = {(x, z) for x in range(-766, -743) for z in range(1821, 1830)} & canyon
    for (x, z) in wx: rect(x, x, z, z, (170, 225, 245, 255), (40, 120, 160), 1)
    for (x, z) in sink: rect(x, x, z, z, (30, 20, 20, 255))
    for k, name, x0, x1, z0, z1, st, occ, fill, top in TOWERS:
        for (x, z) in plan[k] - foot[k]: rect(x, x, z, z, fill[:3] + (140,))      # консоли и верх — светлее
        for (x, z) in foot[k]: rect(x, x, z, z, fill)
        for (x, z) in plan[k]:                                                  # контур
            for dx, dz, e in ((1, 0, 'r'), (-1, 0, 'l'), (0, 1, 'b'), (0, -1, 't')):
                if (x + dx, z + dz) not in plan[k]:
                    a = {'r': (px(x + 1) - 1, pz(z), px(x + 1) - 1, pz(z + 1) - 1), 'l': (px(x), pz(z), px(x), pz(z + 1) - 1),
                         'b': (px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z + 1) - 1), 't': (px(x), pz(z), px(x + 1) - 1, pz(z))}[e]
                    dr.line(a, fill=(20, 50, 100), width=2)
    hx0, hx1, hz0, hz1, hy = HELIPAD
    dr.ellipse([px(hx0), pz(hz0), px(hx1 + 1), pz(hz1 + 1)], fill=(80, 80, 85, 235), outline=(240, 200, 40), width=2)
    dr.text((px(hx0) + 2.6 * S, pz(hz0) + 1.8 * S), 'H', fill='white', font=F(30, True))
    hplan = {(x, z) for x, y, z in HELI}
    for (x, z) in hplan: rect(x, x, z, z, (35, 70, 160, 230), (20, 30, 80), 1)
    for _, x0, x1, z0, z1 in (VEST, VEST_N):
        rect(x0, x1, z0, z1, (120, 40, 160, 255), (60, 10, 90)); dr.text((px(x0) + 10, pz(z0) + 12), 'M', fill='white', font=F(14, True))
    for n, x0, x1, z0, z1 in RESERVE:
        dashed(x0, x1, z0, z1, (120, 40, 160, 230), 2, 5)
    dashed(*STATION[1:], (120, 40, 160, 255), 3, 4)
    dr.line([px(-800), pz(1816) + S // 2, px(-700), pz(1816) + S // 2], fill=(120, 40, 160, 150), width=3)
    for x in range(-796, -725, 8):
        for z in (1812, 1820):
            if not (-772 <= x <= -766):
                dr.ellipse([px(x) + 2, pz(z) + 2, px(x) + S - 3, pz(z) + S - 3], fill=(240, 200, 40), outline=(120, 90, 0))

    L = lambda x, z, s, sz=12, fill='black': dr.text((px(x), pz(z)), s, fill=fill, font=F(sz), stroke_width=3, stroke_fill=(255, 255, 255))
    L(-760, 1815, 'ГЛАВНЫЙ ПРОСПЕКТ', 11)
    L(-770, 1850, 'к дороге мыса ↓', 9)
    L(-770, 1790, 'П\nР\nО\nС\nП\nЕ\nК\nТ\n\nС\nИ\nТ\nИ', 10)
    L(-783, 1789, 'Северная ул.', 10); L(-800, 1839, 'Южная ул.', 10)
    L(-729, 1846, 'Погранич-\nная ул.', 8)
    L(-762, 1822, 'ПЛОЩАДЬ СИТИ', 11)
    L(-758, 1826, 'стекл. окно', 9, (10, 70, 110))
    L(-746, 1796, 'аллея', 9)
    L(-779, 1806, 'пруд', 9, (20, 40, 120))
    L(-742, 1830, 'сквер, фонтан', 9)
    L(-768, 1819, '«Кристалл»', 8, (0, 90, 120)); L(-783, 1836, '«Шар»', 8, (0, 90, 120))
    L(-756, 1851, 'проходы в стенке к набережной', 8, (120, 90, 50))
    lab = {'t1': (-763, 1810), 't2': (-755, 1830), 't3': (-739, 1810), 't4': (-797, 1834), 't5a': (-800, 1792),
           't5b': (-788, 1804), 't5c': (-800, 1809), 't6': (-786, 1774), 't7': (-750, 1774), 't8': (-736, 1843)}
    for k, name, x0, x1, z0, z1, st, occ, fill, top in TOWERS:
        L(*lab[k], f'{name} Y{top}', 9, (20, 40, 90))
    L(-788, 1844, '«ПРОВАЛ»', 10)
    L(-736, 1840, 'вертолёт Y 160…165', 8, (160, 20, 20))
    L(-799, 1785, '«ВЕРШИНА»\nшар над ней\nY 167…187', 8, (160, 40, 20))
    L(-785, 1822, 'КАНЬОН-\nПАРК', 11, (30, 90, 20))
    L(-790, 1856, 'провал до Y 32', 9, (180, 20, 20))
    L(-722, 1783, 'СТАРЫЙ\nГОРОД', 11, (90, 90, 90))
    L(-752, 1856, 'УЛИЦА-НАБЕРЕЖНАЯ (построено)', 10)
    L(-738, 1812, 'М «Каньон»: зал на мосту\nв каньоне, Y≈49', 8, (60, 10, 90))
    marks = [(k, x1, z0, st) for k, n, x0, x1, z0, z1, st, *_ in TOWERS if k not in ('t5b', 't5c')] + \
            [(k, x1, z0, st) for k, n, x0, x1, z0, z1, st in OTHER] + [('pr', -767, 1776, 2)]
    for k, x1, z0, st in marks:
        cx, cz = px(x1 + 1) - 16, pz(z0) + 2
        dr.ellipse([cx, cz, cx + 14, cz + 14], fill=(255, 255, 255), outline=(200, 30, 30), width=2)
        dr.text((cx + 4, cz), str(st), fill=(200, 30, 30), font=F(11, True))

    # силуэты: с моря (вид с юга, по X) и с запада (по Z)
    oy = MT + mh + 50
    base = oy + skh
    dr.text((ML, oy - 18), 'Силуэт с моря (вид с юга)', fill='black', font=F(12, True))
    sx = lambda x: ML + (x - X0) * SK * 3 // 3 * 1 if False else ML + int((x - X0) * mw / (X1 - X0 + 1))
    bw = mw / (X1 - X0 + 1)
    sy = lambda y: base - (y - YS0) * SK
    for y in range(YS0, YS1 + 1, 20):
        dr.line([ML, sy(y), ML + mw, sy(y)], fill=(210, 210, 210), width=1)
        dr.text((6, sy(y) - 6), str(y), fill='black', font=F(10))
    for x in range(X0, X1 + 1):
        g = W.surf(x, 1800)
        dr.rectangle([sx(x), sy(g), sx(x) + bw - 1, base], fill=(190, 180, 150))
    dr.rectangle([sx(-724), sy(80), sx(-700) - 1, sy(67)], fill=(214, 150, 110))

    def draw_side(ax0, proj, pos, order_key):
        for k, name, x0, x1, z0, z1, st, occ, fill, top in sorted(TOWERS, key=order_key):
            cells = {(proj(p), p[1]) for p in vol[k] if p[1] >= YS0}
            d = tuple(int(c * 0.8) for c in fill[:3])
            for u, y in cells:
                dr.rectangle([pos(u), sy(y + 1) + 1, pos(u) + bw - 1, sy(y)], fill=fill[:3])
            for u, y in cells:
                if (u, y + 1) not in cells: dr.line([pos(u), sy(y + 1) + 1, pos(u) + bw - 1, sy(y + 1) + 1], fill=d, width=1)
                if (u - 1, y) not in cells: dr.line([pos(u), sy(y + 1), pos(u), sy(y)], fill=d, width=1)
                if (u + 1, y) not in cells: dr.line([pos(u) + bw - 1, sy(y + 1), pos(u) + bw - 1, sy(y)], fill=d, width=1)
            u0 = min(u for u, _ in cells)
            dr.text((pos(u0), sy(top) - 14), name, fill=(20, 40, 90), font=F(10, True))
    BC = [(220, 60, 50), (245, 200, 40)]                         # шерсть полосами
    for (x, y, z) in BALLOON:
        c = (140, 90, 40) if y <= 100 else BC[(x // 2) % 2]
        dr.rectangle([sx(x), sy(y + 1) + 1, sx(x) + bw - 1, sy(y)], fill=c)
    dr.text((sx(-800), sy(189) - 12), 'шар', fill=(160, 40, 20), font=F(10, True))
    draw_side(0, lambda p: p[0], sx, lambda o: o[5])             # ближние к морю рисуются последними
    HC = lambda x, y, z: (40, 40, 45) if y >= 164 or y == 160 else ((150, 210, 240) if x <= -745 and y in (162, 163) else (35, 70, 160))
    for (x, y, z) in sorted(HELI, key=lambda p: -p[2]):
        dr.rectangle([sx(x), sy(y + 1) + 1, sx(x) + bw - 1, sy(y)], fill=HC(x, y, z))
    dr.rectangle([sx(-742), sy(152) + 1, sx(-733) - 1, sy(151)], fill=(80, 80, 85))
    dr.text((sx(-752), sy(170) - 12), 'вертолёт', fill=(160, 20, 20), font=F(10, True))
    # с запада
    wx0 = ML + mw + 20
    dr.text((wx0, oy - 18), 'Силуэт с запада (Z 1772…1860)', fill='black', font=F(12, True))
    szp = lambda z: wx0 + int((z - 1772) * 450 / (1860 - 1772))
    bw2 = 450 / (1860 - 1772)
    for y in range(YS0, YS1 + 1, 20): dr.line([wx0, sy(y), wx0 + 450, sy(y)], fill=(210, 210, 210), width=1)
    for z in range(1772, 1860):
        g = W.surf(-790, z)
        dr.rectangle([szp(z), sy(g), szp(z) + bw2, base], fill=(190, 180, 150))
    bw_save = bw
    bw = bw2
    for k, name, x0, x1, z0, z1, st, occ, fill, top in sorted(TOWERS, key=lambda o: o[3], reverse=True):
        cells = {(p[2], p[1]) for p in vol[k] if p[1] >= YS0}
        d = tuple(int(c * 0.8) for c in fill[:3])
        for u, y in cells:
            dr.rectangle([szp(u), sy(y + 1) + 1, szp(u) + bw2, sy(y)], fill=fill[:3])
        for u, y in cells:
            if (u, y + 1) not in cells: dr.line([szp(u), sy(y + 1) + 1, szp(u) + bw2, sy(y + 1) + 1], fill=d, width=1)
    for (x, y, z) in HELI:
        dr.rectangle([szp(z), sy(y + 1) + 1, szp(z) + bw2, sy(y)], fill=HC(x, y, z))
    for (x, y, z) in BALLOON:
        c = (140, 90, 40) if y <= 100 else BC[(z // 2) % 2]
        dr.rectangle([szp(z), sy(y + 1) + 1, szp(z) + bw2, sy(y)], fill=c)
    bw = bw_save
    dr.text((ML, base + 8), 'Сити: X −800…−725, Z 1776…1848 (пунктир). Клетка = блок, сетка — чанки, серое — построено, '
            'кружок — этап; башни: тёмное — след на земле, светлое — консоли и верх.', fill='black', font=F(12))

    lx = ML + mw + 20
    dr.text((lx, 12), 'СИТИ — план v1', fill='black', font=F(20, True))
    items = [((95, 95, 95), 'проспекты (5 бл.)'), ((150, 150, 150), 'улицы (5 бл.)'), ((205, 200, 190), 'тротуары, аллея'),
             ((232, 222, 196), 'площадь, смотровая'), ((120, 175, 95), 'Каньон-парк (полоса каньона +2)'),
             ((170, 40, 40), 'пустота каньона ≥ 8 бл.'), ((170, 225, 245), 'стеклянное окно в каньон'),
             ((30, 20, 20), 'естественный провал до Y 32'), ((120, 40, 160), 'резерв трасс; метро: зал, M — вестибюль'),
             ((225, 215, 195), 'дорожки к объектам'), ((70, 130, 215), 'пруд, фонтан'), ((180, 240, 250), 'арт-объекты'),
             ((40, 130, 50), 'деревья'), ((235, 110, 170), 'клумбы'), ((140, 90, 40), 'скамейки')]
    for i, (cc, t) in enumerate(items):
        y = 42 + i * 17
        dr.rectangle([lx, y, lx + 22, y + 13], fill=cc, outline=(60, 60, 60))
        dr.text((lx + 30, y), t, fill='black', font=F(12))
    notes = [
        'Башни (все разной формы): Т1 «Открывашка»',
        ' Y 190 (ВФЦ Шанхай), Т2 «Ворота» Y 150 (CCTV),',
        ' Т3 «Мост» Y 100 — Биржа (ToHA), Т4 «Парус»',
        ' Y 175, Т5 «Галька» Y 160/135/115 (SOHO),',
        ' Т6 «Спираль» Y 150 («Эволюция»), Т7 «Три',
        ' башни» Y 132 с палубой (Marina Bay), Т8',
        ' «Подкова» Y 91 — кольцо к морю (Хучжоу).',
        '',
        'Метро 1, станция «Каньон»: зал на мосту в',
        ' пустоте каньона под проспектом (X −756…−744,',
        ' пол ≈Y 49, виден каньон); вестибюли: Ю — на',
        ' Площади Сити, С — у «Открывашки» и аллеи.',
        ' Строятся со схемой тоннеля.',
        '',
        'Дорожки — к каждому зданию, вестибюлю, пруду',
        ' (проверка связности от проспекта); к улице-',
        ' набережной — проходы в подпорной стенке',
        ' Z 1849 (Y 67 → 64 ступенями).',
        'Вода: пруд в ложбине у «Гальки», фонтан 9×9',
        ' (DECOR §5.3) в сквере у «Ворот».',
        'Арт-объекты: «Кристалл» у окна, «Шар» в парке.',
        'Вертолётная площадка на крыше «Ворот» (Y 151,',
        ' 9×9, «H», огни); вертолёт (синий) висит рядом,',
        ' Y 160…165, статично.',
        'СЗ угол: площадка «Вершина» на плато Y 80,',
        ' над ней статично висит воздушный шар',
        ' (Y 167…187, без тросов); подъём ступенями',
        ' от «Спирали» и тропой от «Гальки».',
        'Деревья вдоль проспекта и в парке, клумбы,',
        ' скамейки, фонари (DECOR §3).',
        '',
        'Этапы: 1 — земля, площадки, окно; 2 — улицы,',
        ' фонари, деревья проспекта; 3 — Площадь Сити,',
        ' сквер с фонтаном, пруд, Каньон-парк, «Провал»,',
        ' «Кристалл», «Шар»; 4 — Т1; 5 — Т2, Т3;',
        ' 6 — Т4, Т5, «Вершина», шар; 7 — Т6–Т8 (дорожки —',
        ' в этапе здания). Позже — метро, спуск в каньон.',
    ]
    for i, t in enumerate(notes):
        dr.text((lx, 330 + i * 17), t, fill='black', font=F(12))
    img.save(args.out)
    print('план', args.out, img.size)


if __name__ == '__main__':
    main()
