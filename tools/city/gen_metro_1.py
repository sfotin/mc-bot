"""Метро и коллектор, этап 1 (CITY.md §7.10, геометрия — tools/city/plan_metro_v1.py): пересадочный узел «Центр»
и вся линия 2. Две схемы — строить по порядку, каждую отдельным .cmd и только после итога «ошибок 0»:

- metro-1-build.json — коробки: участок общего тоннеля X −708…−669 (пассажирская часть линии 1 с залом станции
  «Центр»: остров 8 бл. — стенка, марш на мезонин, ограждение, проход 3; «впадины» остановок в полу; галерея
  коллектора — пол 59, внутри 60…62, под прудами сдвинута на север; отводы-заглушки на север X −673…−669 и на юг
  X −688…−684; торцы участка — временные стенки), мезонин (ноги 59), вестибюль «Центр» (павильон на углу рынка,
  лестница в мезонин), пересадочный марш на линию 2; линия 2 — тоннель X −694…−690 (пути X −693 и −691 через
  промежуток), станции «Вокзал» (конечная, боковая платформа, лестница на восток и временный павильон, дорожка
  до Проспекта С–Ю), «Центр» (остров 7 бл. под Соборной площадью), «Набережная» (конечная, платформа рядом с
  залом ветки купола, проём в его восточной стене); облицовка каменным кирпичом, полы платформ — полированный
  андезит, край платформы — жёлтый бетон, свет — морские фонари; природные пустоты (съёмка
  docs/terrain/metro-voids.json), открытые в постройку, заделываются;
- metro-1-rails.json — путь линии 2 (кольцо: на юг по X −693, петля у «Набережной», на север по X −691, петля у
  «Вокзала»): рельсы, ускоряющие на блоках редстоуна (подъёмы по ходу — все, по ровному — через 24), остановки
  «на гребне» (подъём на 1, гребень, два спуска — ускоряющие без питания, низ на блок ниже рельсов, подъём —
  ускоряющий на редстоуне), кнопки на верху блока пола платформы у нижнего спуска. Строить после проверки стенда metro-0-test (gen_metro_0.py).
Линия 1 в этом этапе — без рельсов (коробка станции «Центр» готова, пути — с этапами 2–3).

Запуск: gen_metro_1.py [--outdir schemas] [--preview docs/districts/metro-1-preview.png]
Мир — World(built_before('metro-1-build.json')) + съёмка пустот (plan_metro_v1.Survey).
Проверки: опоры/вода/порядок (decor_lib, порядок бота) для каждой схемы; протечки (природные пустоты рядом с
воздухом постройки); задетое построенное; проходимость без прыжков (рынок → мезонин → остров линии 1 → остров
линии 2; улица → вестибюль «Вокзал» → платформа; променад → зал «Набережной» → платформа линии 2); просвет над
маршами 4; ширина проходов ≥ 3; свет ≥ 8; рельсы (опоры, редстоун, цепи ускоряющих у остановок, кнопки, петли);
негативные прогоны.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import World, REPO, built_before, save_schema, dl, path_heights, pave_cells  # noqa: E402
import plan_metro_v1 as PM  # noqa: E402

NAMES = ['metro-1-build.json', 'metro-1-rails.json']
WALL, FLOOR, EDGE, LAMP = 'stonebrick', 'stone:6', 'concrete:4', 'sea_lantern'
QZ, QZP, PANE, PANE_B = 'quartz_block', 'quartz_block:2', 'stained_glass_pane:0', 'stained_glass_pane:3'
STAIR = 'stone_brick_stairs'
STAIR_META = {'E': 0, 'W': 1, 'S': 2, 'N': 3}          # подъём в сторону
N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
F1, F2 = PM.L1F, None
S1X = (-708, -669)                                      # участок общего тоннеля этапа 1
ALLOW_OPEN = set()                                      # построенное, которое разбирается (проёмы)
for z in range(1851, 1858):
    for y in range(57, 61): ALLOW_OPEN.add((-698, y, z))   # восточная стена зала «Набережной» (ветка купола)


def man(a, b): return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


class Plan:
    def __init__(self, W):
        self.W, self.SV = W, PM.Survey(W)
        self.S, self.A, self.X = {}, set(), {}           # оболочка, воздух, наполнение (поверх воздуха)
        self.targets, self.lamp_c, self.flights, self.walk_rows = {}, [], [], []
        self.keep_built = set()                          # клетки, где стоит построенное и мы его оставляем
        self.zones = []                                  # (x0, x1, z0, z1, ymin): здесь построенное заменяется (павильоны)
        self.zone_cells = set()                          # колонны дорожек

    def shell(self, x, y, z, b=WALL): self.S[(x, y, z)] = b

    def box_shell(self, x0, x1, y0, y1, z0, z1, b=WALL):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1): self.S[(x, y, z)] = b

    def air(self, x0, x1, y0, y1, z0, z1):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1): self.A.add((x, y, z))

    def room(self, x0, x1, z0, z1, floor, top, roof=True):
        """Коробка: стены по периметру (x0/x1, z0/z1), пол floor, внутри floor+1…top, свод top+1."""
        self.box_shell(x0, x1, floor, top + (1 if roof else 0), z0, z1)
        self.air(x0 + 1, x1 - 1, floor + 1, top, z0 + 1, z1 - 1)

    def tgt(self, name, cells): self.targets.setdefault(name, []).extend(cells)

    def compose(self):
        D = dict(self.S)
        for k in self.A: D[k] = 'air'
        D.update(self.X)
        return D


# ============================================================================== линия 1: зал «Центр», тоннель, коллектор
def build_common(P):
    st = next(s for s in PM.STATIONS_1 if s['name'] == 'Центр')
    hx0, hx1 = st['x0'] - 4, st['x1'] + 4                # X −693…−672
    # бегущий тоннель (Z 1812…1816): пол 54, внутри 55…57, свод 58; торцы участка — временные стенки
    for x in list(range(S1X[0], hx0 + 1)) + list(range(hx1, S1X[1] + 1)):
        P.box_shell(x, x, F1 - 1, F1 + 3, 1812, 1816)
        P.air(x, x, F1, F1 + 2, 1813, 1815)
    P.box_shell(S1X[0] - 1, S1X[0] - 1, F1 - 1, F1 + 3, 1812, 1816)
    P.box_shell(S1X[1] + 1, S1X[1] + 1, F1 - 1, F1 + 3, 1812, 1816)
    # зал «Центр»: X −693…−672, Z 1809…1820
    P.room(hx0, hx1, 1809, 1820, F1 - 1, F1 + 2)
    P.air(hx0, hx0, F1, F1 + 2, 1813, 1815); P.air(hx1, hx1, F1, F1 + 2, 1813, 1815)
    for x in range(st['x0'], st['x1'] + 1):                # остров Z 1811…1818: андезит, край — жёлтый
        for z in range(1811, 1819): P.shell(x, F1 - 1, z, EDGE if z in (1811, 1818) else FLOOR)
    # впадины остановок (пол на блок ниже) — по треку плана
    P.stops1 = []
    for w in ('N', 'S'):
        for (x, z, f, k) in PM.line1_track(w):
            if hx0 <= x <= hx1 and f < F1:
                P.shell(x, f - 1, z)
                for y in range(f, F1): P.A.add((x, y, z)); P.S.pop((x, y, z), None)
            if hx0 <= x <= hx1 and f > F1:                       # гребень остановки — опора
                for y in range(F1, f): P.X[(x, y, z)] = WALL; P.A.discard((x, y, z))
            if hx0 <= x <= hx1 and k in ('stop', 'stop2') and f == F1 - 1: P.stops1.append((x, f, z, w))
    # марш остров → мезонин: подъём на запад, X −677 (ноги 56) … −680 (ноги 59), Z 1812…1814; стенка Z 1811,
    # ограждение Z 1815 (стекло-панели), свод зала над маршем снят
    fl = {-676: 55, -677: 56, -678: 57, -679: 58, -680: 59}
    for x, f in fl.items():
        for z in (1812, 1813, 1814):
            if x != -676: P.X[(x, f - 1, z)] = f'{STAIR}:{STAIR_META["W"]}'
            P.air(x, x, f, max(f, fl.get(x - 1, f)) + 3, z, z)
            if x != -676: P.A.discard((x, f - 1, z))
        if x != -676:
            for y in range(F1, F1 + 3): P.shell(x, y, 1811); P.X[(x, y, 1815)] = PANE
    for x in (-677, -678, -679): P.X[(x, F1 - 1, 1811)] = EDGE
    P.flights.append(('марш остров → мезонин', [(x, f, z) for x, f in fl.items() for z in (1812, 1813, 1814)]))
    P.tgt('остров линии 1', [(x, F1, z) for x in range(st['x0'], st['x1'] + 1) for z in range(1816, 1819)] +
          [(x, F1, z) for x in range(st['x0'], -680) for z in range(1811, 1815)])
    P.lamp_c += [(x, F1 + 3, z) for x in range(hx0 + 1, hx1) for z in (1811, 1816, 1817, 1818)]
    P.walk_rows.append(('проход острова', [[(x, F1, z) for z in range(1816, 1819)] for x in range(st['x0'], st['x1'] + 1)]))
    # коллектор X −708…−669: пол 59, внутри 60…62, свод 63 (построенное на 63 — остаётся сводом)
    cf, ct = PM.COL_FLOOR, PM.COL_TOP
    px0, px1 = PM.POND_X
    for x in range(S1X[0], S1X[1] + 1):
        if px0 <= x <= px1: zw = (1813, 1818)
        elif x in (px0 - 1, px1 + 1): zw = (1813, 1821)
        else: zw = PM.COL_Z
        P.box_shell(x, x, cf, ct + 1, zw[0], zw[1])
        P.air(x, x, cf + 1, ct, zw[0] + 1, zw[1] - 1)
        cab = zw[0] + 1
        P.tgt('коллектор', [(x, cf + 1, z) for z in range(cab + 1, zw[1])])
        P.lamp_c += [(x, cf + 2, zw[1]), (x, cf + 2, zw[0])]
    P.box_shell(S1X[0] - 1, S1X[0] - 1, cf, ct + 1, 1813, 1821)
    P.box_shell(S1X[1] + 1, S1X[1] + 1, cf, ct + 1, *PM.COL_Z)
    P.walk_rows.append(('коллектор', [[(x, cf + 1, z) for z in range(1813, 1822)] for x in range(S1X[0], S1X[1] + 1)]))
    # отводы-заглушки
    for name, x0, x1, z0, z1 in PM.BRANCHES:
        if not (S1X[0] <= x0 and x1 <= S1X[1]): continue
        P.box_shell(x0, x1, cf, ct + 1, z0, z1)
        if z0 >= 1821: P.air(x0 + 1, x1 - 1, cf + 1, ct, z0, z1 - 1)                # на юг: проём в стене 1821
        else: P.air(x0 + 1, x1 - 1, cf + 1, ct, z0 + 1, z1)                          # на север: проём в стене 1816
        P.tgt('отводы', [(x, cf + 1, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)])
        P.lamp_c += [(x0, cf + 2, z) for z in range(z0 + 1, z1)]


def build_mezz_and_vestibule(P):
    mx0, mx1, mz0, mz1 = PM.MEZZ['Центр']                 # X −691…−675, Z 1808…1815
    mf = PM.MEZ_F - 1
    P.room(mx0, mx1, mz0, mz1, mf, 62)
    for x in range(mx0 + 1, mx1):
        for z in range(mz0 + 1, mz1): P.shell(x, mf, z, FLOOR)
    for x in range(-680, -675):                           # проём над маршем острова (с первой ступени)
        for z in (1812, 1813, 1814): P.A.add((x, mf, z)); P.S.pop((x, mf, z), None)
    for x in range(-679, -675): P.X[(x, mf + 1, 1811)] = PANE   # ограждение проёма
    P.tgt('мезонин', [(x, mf + 1, z) for x in range(mx0 + 1, mx1) for z in range(mz0 + 1, mz1)
                      if not (-680 < x < -675 and 1811 <= z <= 1814)])
    P.lamp_c += [(x, 63, z) for x in range(mx0 + 1, mx1) for z in range(mz0 + 1, mz1)]
    P.lamp_c += [(x, 61, z) for x in (mx0, mx1) for z in range(mz0 + 1, mz1)] + [(x, 61, z) for x in range(mx0 + 1, mx1) for z in (mz0, mz1)]
    # вестибюль «Центр»: павильон X −687…−683, Z 1804…1812 (угол рынка), вход с запада (Z 1805…1807, ноги 65:
    # с севера в 2 бл. — прилавок); площадка Z 1805…1806, лестница на юг вниз Z 1807…1812, низ — мезонин Z 1813
    vx0, vx1, vz0, vz1 = PM.VEST_CENTER
    G = 65
    prof = {1805: G, 1806: G, 1807: 65, 1808: 64, 1809: 63, 1810: 62, 1811: 61, 1812: 60, 1813: 59}
    for x in range(vx0 + 1, vx1):
        for z, f in prof.items():
            if z in (1805, 1806): P.shell(x, f - 1, z, FLOOR)
            elif z < 1813:
                P.X[(x, f - 1, z)] = f'{STAIR}:{STAIR_META["N"]}'
                for y in range(PM.MEZ_F, f - 1): P.X[(x, y, z)] = WALL          # под лестницей — сплошное
            P.air(x, x, f, max(f, prof.get(z - 1, f)) + 3, z, z)
            P.X.pop((x, f, z), None)
    P.flights.append(('лестница вестибюля «Центр»', [(x, f, z) for x in range(vx0 + 1, vx1) for z, f in prof.items()]))
    pavilion(P, vx0, vx1, vz0, vz1, G, [(vx0, z) for z in (1805, 1806, 1807)])
    P.tgt('вестибюль «Центр»', [(x, f, z) for x in range(vx0 + 1, vx1) for z, f in prof.items()])
    # пересадочный марш мезонин → остров линии 2: вниз на север, X −690…−688, ступени Z 1808 (59) … 1800 (51),
    # низ — остров Z 1799 (50)
    tprof = {1809: 59, 1808: 59, 1807: 58, 1806: 57, 1805: 56, 1804: 55, 1803: 54, 1802: 53, 1801: 52, 1800: 51, 1799: 50}
    for x in (-690, -689, -688):
        for z, f in tprof.items():
            if 1800 <= z <= 1808:
                P.X[(x, f - 1, z)] = f'{STAIR}:{STAIR_META["S"]}'
                for y in range(PM.L2_LOW - 1, f - 1): P.X[(x, y, z)] = WALL       # под маршем — сплошное
            P.air(x, x, f, max(f, tprof.get(z + 1, f)) + 3, z, z)
    P.flights.append(('пересадочный марш', [(x, f, z) for x in (-690, -689, -688) for z, f in tprof.items()]))
    P.tgt('пересадочный марш', [(x, f, z) for x in (-690, -689, -688) for z, f in tprof.items()])
    P.lamp_c += [(-691, f + 2, z) for z, f in tprof.items()] + [(-687, f + 2, z) for z, f in tprof.items() if f >= 53]


def pavilion(P, x0, x1, z0, z1, G, doors):
    """Павильон вестибюля: пол G−1 (андезит), стены кварц с витражами (белые/голубые панели), колонны по углам,
    свод G+3 (кварц) с фонарём, вход — проём высотой 3 в стене по клеткам doors [(x, z)]."""
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge = x in (x0, x1) or z in (z0, z1)
            corner = x in (x0, x1) and z in (z0, z1)
            P.shell(x, G - 1, z, FLOOR if not edge else QZ)
            P.shell(x, G + 4, z, QZ)
            for y in range(G, G + 4):
                if not edge: P.A.add((x, y, z)); continue
                if corner: P.shell(x, y, z, QZP)
                elif y in (G + 1, G + 2): P.X[(x, y, z)] = PANE_B if (x + z) % 2 else PANE
                else: P.shell(x, y, z, QZ)
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if (x, z) in doors:
                for y in range(G, G + 3): P.A.add((x, y, z)); P.S.pop((x, y, z), None); P.X.pop((x, y, z), None)
                P.shell(x, G - 1, z, FLOOR)
    P.X[((x0 + x1) // 2, G + 4, (z0 + z1) // 2)] = LAMP
    P.lamp_c += [(x, G + 4, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)]
    P.pavilions = getattr(P, 'pavilions', []) + [(x0, x1, z0, z1, G, doors)]
    P.zones.append((x0, x1, z0, z1, 63))


# ============================================================================== линия 2
def l2_feet(z): return PM.lerp_profile(PM.L2_PROFILE, min(max(z, PM.L2_Z[0]), PM.L2_Z[1]))


def build_line2(P):
    XW, XE = PM.XW, PM.XE
    stz = {s['name']: s for s in PM.STATIONS_2}
    v, c, nb = stz['Вокзал'], stz['Центр'], stz['Набережная']
    halls = [(v['z0'] - 3, v['z1'] + 1), (c['z0'] - 4, c['z1'] + 4), (nb['z0'] - 1, nb['z1'] + 3)]   # Z стен залов
    # тоннель: стены X −694/−690, пол f−1, внутри f…max(f±1)+2, свод +1; фонарь в своде через 8
    for z in range(PM.L2_Z[0] - 1, PM.L2_Z[1] + 2):
        if any(a <= z <= b for a, b in halls): continue
        f = l2_feet(z); top = max(l2_feet(z - 1), f, l2_feet(z + 1)) + 2
        P.box_shell(XW - 1, XE + 1, f - 1, top + 1, z, z)
        P.air(XW, XE, f, top, z, z)
        if z % 8 == 0: P.X[(XW + 1, top + 1, z)] = LAMP
    # «Вокзал»: зал X −694…−686, Z 1747…1762, пол 54; платформа X −690…−687
    za, zb = halls[0]
    f = l2_feet(v['z0'])
    P.room(XW - 1, XE + 5, za, zb, f - 1, f + 2)
    P.air(XW, XE, f, f + 2, zb, zb)                                   # выход тоннеля на юг
    for x in range(XE + 1, XE + 5):
        for z in range(v['z0'], v['z1'] + 1): P.shell(x, f - 1, z, EDGE if x == XE + 1 else FLOOR)
    P.tgt('платформа «Вокзал»', [(x, f, z) for x in range(XE + 1, XE + 5) for z in range(v['z0'], v['z1'] + 1)])
    P.lamp_c += [(x, f + 3, z) for x in range(XW, XE + 5) for z in range(za + 1, zb)]
    P.walk_rows.append(('платформа «Вокзал»', [[(x, f, z) for x in range(XE + 2, XE + 5)] for z in range(v['z0'], v['z1'] + 1)]))
    # лестница на восток: Z 1754…1756 от X −686 вверх, площадка после 5 ступеней, павильон над выходом
    G = vokzal_exit_level(P)
    fz = (1754, 1756)
    prof, x, ff = {}, XE + 5, f
    prof[x] = f                                                      # проём в стене зала
    seq = []
    while ff < G:
        x += 1
        if len(seq) == 5: seq.append('L'); prof[x] = ff; x += 1; prof[x] = ff; x += 1; prof[x] = ff; x += 1
        ff += 1; prof[x] = ff; seq.append('S')
    for k in range(1, 4): prof[x + k] = G
    for xx, fv in prof.items():
        for z in range(fz[0], fz[1] + 1):
            up = prof.get(xx - 1, fv) < fv
            if up: P.X[(xx, fv - 1, z)] = f'{STAIR}:{STAIR_META["E"]}'
            else: P.shell(xx, fv - 1, z, FLOOR)
            P.air(xx, xx, fv, max(fv, prof.get(xx + 1, fv)) + 3, z, z)
        P.box_shell(xx, xx, fv - 1, max(fv, prof.get(xx + 1, fv)) + 4, fz[0] - 1, fz[0] - 1)
        P.box_shell(xx, xx, fv - 1, max(fv, prof.get(xx + 1, fv)) + 4, fz[1] + 1, fz[1] + 1)
        P.box_shell(xx, xx, max(fv, prof.get(xx + 1, fv)) + 4, max(fv, prof.get(xx + 1, fv)) + 4, fz[0], fz[1])
    xs = sorted(prof)
    P.flights.append(('лестница «Вокзал»', [(xx, prof[xx], z) for xx in xs for z in range(fz[0], fz[1] + 1)]))
    P.tgt('лестница «Вокзал»', [(xx, prof[xx], z) for xx in xs for z in range(fz[0], fz[1] + 1)])
    P.lamp_c += [(xx, max(prof[xx], prof.get(xx + 1, prof[xx])) + 4, (fz[0] + fz[1]) // 2) for xx in xs]
    # павильон: от первой клетки, где просвет выходит выше грунта, до верхней площадки; вход с востока
    first = next(xx for xx in xs if max(prof[xx], prof.get(xx + 1, prof[xx])) + 3 >= min(P.W.surf(xx, z) for z in range(fz[0], fz[1] + 1)))
    px0, px1 = first - 1, xs[-1] + 1
    for xx in range(px0, px1 + 1):                                  # павильон заменяет отделку лестницы над землёй
        for z in range(fz[0] - 1, fz[1] + 2):
            for y in range(G - 1, G + 6): P.S.pop((xx, y, z), None)
    pavilion_stair(P, px0, px1, fz[0] - 1, fz[1] + 1, G, prof)
    P.vokzal_exit = (px1 + 1, G, (fz[0] + fz[1]) // 2)
    vokzal_path(P, px1 + 1, G, fz)
    # «Центр» линии 2: зал X −695…−685, Z 1788…1810, пол 49; остров X −693…−687
    za, zb = halls[1]
    f = l2_feet(c['z0'])
    P.room(PM.JOG_W - 1, PM.JOG_E + 1, za, zb, f - 1, f + 2)
    P.air(XW, XE, f, f + 2, za, za); P.air(XW, XE, f, f + 2, zb, zb)
    for x in range(PM.JOG_W + 1, PM.JOG_E):
        for z in range(c['z0'], c['z1'] + 1):
            P.shell(x, f - 1, z, EDGE if x in (PM.JOG_W + 1, PM.JOG_E - 1) else FLOOR)
    for z in range(1799, 1808):                                     # стенка между маршем и путём E
        for y in range(f, f + 3): P.shell(PM.JOG_E - 1, y, z)
    P.tgt('остров линии 2', [(x, f, z) for x in range(PM.JOG_W + 1, PM.JOG_W + 4) for z in range(c['z0'], c['z1'] + 1)] +
          [(x, f, z) for x in range(PM.JOG_W + 4, PM.JOG_E) for z in range(c['z0'], 1800)])
    P.lamp_c += [(x, f + 3, z) for x in range(PM.JOG_W, PM.JOG_E + 1) for z in range(za + 1, zb)]
    P.walk_rows.append(('остров линии 2', [[(x, f, z) for x in range(PM.JOG_W + 1, PM.JOG_W + 4)] for z in range(c['z0'], c['z1'] + 1)]))
    # «Набережная»: зал X −698…−690, Z 1845…1861, пол 56; платформа X −697…−694 у зала ветки купола
    za, zb = halls[2]
    f = l2_feet(nb['z0'])
    P.room(XW - 5, XE + 1, za, zb, f - 1, f + 3)
    P.air(XW, XE, l2_feet(za), l2_feet(za) + 2, za, za)
    for x in range(XW - 4, XW):
        for z in range(nb['z0'], nb['z1'] + 3): P.shell(x, f - 1, z, EDGE if x == XW - 1 else FLOOR)
    for z in range(1851, 1858):                                     # проём в зал ветки купола
        P.air(XW - 5, XW - 5, f, f + 3, z, z)
    P.tgt('платформа «Набережная»', [(x, f, z) for x in range(XW - 4, XW) for z in range(nb['z0'], nb['z1'] + 3)])
    P.lamp_c += [(x, f + 4, z) for x in range(XW - 4, XE + 1) for z in range(za + 1, zb)]
    P.walk_rows.append(('платформа «Набережная»', [[(x, f, z) for x in range(XW - 4, XW)] for z in range(nb['z0'], nb['z1'] + 3)]))
    # впадины остановок линии 2 (пол на блок ниже) и петли
    P.stops2 = []
    for w in ('W', 'E'):
        for (x, z, ff, k) in PM.line2_track(w):
            if ff < l2_feet(z):
                P.shell(x, ff - 1, z)
                for y in range(ff, l2_feet(z)): P.A.add((x, y, z)); P.S.pop((x, y, z), None)
            if ff > l2_feet(z):                                     # гребень остановки — опора
                for y in range(l2_feet(z), ff): P.X[(x, y, z)] = WALL; P.A.discard((x, y, z))
            if k in ('stop', 'stop2') and ff == l2_feet(z) - 1: P.stops2.append((x, ff, z, w))


def vokzal_exit_level(P):
    xs = [x for x in range(-675, -669)]
    return max(P.W.surf(x, z) for x in xs for z in range(1754, 1757)) + 1


def pavilion_stair(P, x0, x1, z0, z1, G, prof):
    """Павильон над выходом лестницы «Вокзал»: стены кварц с витражами, свод — над верхней ступенью + 4; вход с востока."""
    top = G + 4
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge = x in (x0, x1) or z in (z0, z1)
            corner = x in (x0, x1) and z in (z0, z1)
            low = min(prof.get(x, G), G) - 1 if not edge else min(P.W.surf(x, z), G - 1)
            P.shell(x, top, z, QZ)
            if edge:
                for y in range(low, top):
                    if corner: P.shell(x, y, z, QZP)
                    elif y == G + 1 and x != x1: P.X[(x, y, z)] = PANE_B if (x + z) % 2 else PANE
                    else: P.shell(x, y, z, QZ)
    for z in range(z0 + 1, z1):                                     # вход — проём в восточной стене
        for y in range(G, G + 3): P.A.add((x1, y, z)); P.S.pop((x1, y, z), None); P.X.pop((x1, y, z), None)
        P.shell(x1, G - 1, z, FLOOR)
    for x in range(x0 + 1, x1):
        for z in range(z0 + 1, z1):
            for y in range(max(prof.get(x, G), 0), top): P.A.add((x, y, z))
    P.X[((x0 + x1) // 2, top, (z0 + z1) // 2)] = LAMP
    P.lamp_c += [(x, top, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)] + [(x, G + 2, z) for x in range(x0 + 1, x1) for z in (z0, z1)]
    P.pavilions = getattr(P, 'pavilions', []) + [(x0, x1, z0, z1, G, ('E', x1))]
    P.zones.append((x0, x1, z0, z1, 60))


def vokzal_path(P, xs, G, fz):
    """Дорожка 3 бл. от павильона «Вокзал»: на восток 2, на юг до Z 1782, на запад до улицы (X −687)."""
    cells = set()
    for x in range(xs, xs + 3):
        for z in range(fz[0], 1783): cells.add((x, z))
    for x in range(-687, xs):
        for z in range(1780, 1783): cells.add((x, z))
    fixed = {(xs, z): float(G) for z in range(fz[0], fz[1] + 1)}
    H, anchors, bad = path_heights(P.W, cells, fixed)
    P.path_bad = bad
    P.paved = H
    out = pave_cells(P.W, cells, H)
    for k, b in out.items():
        if b == 'air': P.A.add(k)
        else: P.S[k] = b
    P.path_cells = cells
    P.zone_cells |= cells
    P.path_water = [c for c in cells if any(P.W.block(c[0], y, c[1]).startswith('water') for y in range(int(H[c]) - 2, int(H[c]) + 1))]


# ============================================================================== рельсы линии 2 (общая часть — и для стенда)
DIRS = {(1, 0): 'E', (-1, 0): 'W', (0, 1): 'S', (0, -1): 'N'}
SLOPE = {'E': 2, 'W': 3, 'N': 4, 'S': 5}
CURVE = {frozenset('SE'): 6, frozenset('SW'): 7, frozenset('NW'): 8, frozenset('NE'): 9}


def circuit_rails(cells, flat_every=24):
    """cells — кольцо (x, z, ноги, вид) в направлении движения. → {(x, y, z): блок}, редстоун, кнопки-кандидаты.
    Ускоряющие: стоянка (без питания), подъём впадины и подъёмы по ходу (на редстоуне), по ровному через flat_every
    (не ближе 3 клеток к стоянке — иначе цепь ускоряющих передаст питание)."""
    n = len(cells)
    R, RED = {}, set()
    near_stop = set()
    for i, c in enumerate(cells):
        if c[3] in ('rise', 'crest', 'stop', 'stop2', 'low', 'boost_up'):
            for d in range(-3, 4): near_stop.add((i + d) % n)
    run = 0
    for i, (x, z, f, k) in enumerate(cells):
        p, q = cells[i - 1], cells[(i + 1) % n]
        dp = DIRS[(p[0] - x, p[1] - z)]; dq = DIRS[(q[0] - x, q[1] - z)]
        straight = {dp, dq} in ({'E', 'W'}, {'N', 'S'})
        up = None
        if p[2] == f + 1: up = dp
        if q[2] == f + 1: up = dq
        if not straight: meta = CURVE[frozenset(dp + dq)]
        elif up: meta = SLOPE[up]
        else: meta = 1 if dp in 'EW' else 0
        gold, red = False, False
        if k in ('stop', 'stop2'): gold = True
        elif k == 'boost_up' or (straight and up == dq): gold, red = True, True
        elif straight and not up and k != 'low' and i not in near_stop:
            run += 1
            if run >= flat_every: gold, red, run = True, True, 0
        if not straight: run = 0
        R[(x, f, z)] = (f'golden_rail:{meta}' if gold else f'rail:{meta}')
        if red: RED.add((x, f - 1, z))
    return R, RED


# ============================================================================== сборка
def finalize(P):
    D = P.compose()
    W = P.W
    hits, keep = [], []
    for k, b in list(D.items()):
        pre = W.pre.get(k)
        if pre is None or pre == 'air' or pre == b: continue
        if k in ALLOW_OPEN: continue
        if (k[0], k[2]) in P.zone_cells or any(x0 <= k[0] <= x1 and z0 <= k[2] <= z1 and k[1] >= ym for x0, x1, z0, z1, ym in P.zones):
            continue
        fz = PM.FILL_ZONE[0] <= k[0] <= PM.FILL_ZONE[1] and PM.FILL_ZONE[2] <= k[2] <= PM.FILL_ZONE[3]
        if fz and pre in PM.FILL_OK: continue
        if b == 'air' or (k in P.X and pre.startswith('water')):
            hits.append((k, pre, b))
        else:
            keep.append(k); del D[k]
    # мощение и подоснова улиц над сводом: построенное на Y ≥ 63 над постройкой — не трогается
    P.hits, P.kept = hits, keep
    # заделка природных пустот рядом с воздухом постройки
    seal = []
    for k, b in list(D.items()):
        if b != 'air': continue
        for a, bb, c in N6:
            n = (k[0] + a, k[1] + bb, k[2] + c)
            if n in D: continue
            if P.SV.natural(*n): D[n] = WALL; seal.append(n)
    P.sealed = seal
    return D


def base_of(W, SV):
    def base(x, y, z):
        if (x, y, z) in W.pre: return W.pre[(x, y, z)]
        t = SV.natural(x, y, z)
        if t: return {'a': 'air', 'w': 'water', 'l': 'lava'}[t]
        b = W.block(x, y, z)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
    return base


def place_lamps(D, cands, targets, existing):
    lit = lambda t, L: any(man(l, t) <= 7 for l in L)
    need = [t for t in targets if not lit(t, existing)]
    cset = [c for c in dict.fromkeys(cands) if D.get(c) not in (None, 'air') and not str(D.get(c)).startswith(('stone_brick_stairs', 'stained', 'quartz_block:'))]
    lamps = []
    while need:
        best, cov = None, []
        for c in cset:
            cv = [t for t in need if man(c, t) <= 7]
            if len(cv) > len(cov): best, cov = c, cv
        if not best: break
        lamps.append(best); D[best] = LAMP
        s = set(cov); need = [t for t in need if t not in s]; cset.remove(best)
    return lamps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    ap.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'metro-1-preview.png'))
    a = ap.parse_args()
    W = World(built_before(NAMES[0]))
    P = Plan(W)
    build_common(P)
    build_mezz_and_vestibule(P)
    build_line2(P)
    D = finalize(P)
    tl = [(x, math.floor(h), z) for ts in P.targets.values() for (x, h, z) in ts]
    ex = [k for k, b in W.pre.items() if b == LAMP and -720 <= k[0] <= -660 and 1740 <= k[2] <= 1870]
    P.lamps = place_lamps(D, P.lamp_c, tl, ex + [k for k, b in D.items() if b == LAMP])
    # рельсы линии 2
    ring = PM.line2_track('W') + PM.line2_track('E')
    R, RED = circuit_rails(ring)
    RS = dict(R)
    for k in RED: RS[k] = 'redstone_block'
    buttons = []
    for (x, f, z, w) in P.stops2:
        side = None
        for cand in ((x + 1, f, z), (x - 1, f, z)):
            if D.get(cand) in (FLOOR, EDGE): side = cand; break
        RS[(side[0], f + 1, side[2])] = 'stone_button:5'
        buttons.append((side[0], f + 1, side[2]))
    P.buttons = buttons
    outs = {}
    for nm, DD in zip(NAMES, (D, RS)):
        os.makedirs(a.outdir, exist_ok=True)
        o, rel, order, dims = save_schema(dict(DD), os.path.join(a.outdir, nm))
        outs[nm] = (o, rel, order)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(DD)}')
    checks(W, P, D, RS, ring, R, RED, outs, a)


# ============================================================================== проверки
def stair_clear_issues(final, flights):
    out = []
    for name, cells in flights:
        fm = {(x, z): f for x, f, z in cells}
        for (x, z), f in fm.items():
            hi = max([f] + [fm[(x + a, z + b)] for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (x + a, z + b) in fm])
            for y in range(f, hi + 4):
                if final(x, y, z) not in ('air',) and not final(x, y, z).startswith(('rail', 'golden_rail', 'stone_button')):
                    out.append((name, (x, y, z), final(x, y, z))); break
    return out


def rail_issues(final, R, RED, ring, buttons):
    out = []
    solid_ok = lambda b: b not in ('air', 'water', 'lava') and not b.startswith(('stained_glass', 'glass', 'rail', 'golden'))
    for (x, y, z), b in R.items():
        if not solid_ok(final(x, y - 1, z)): out.append(('нет опоры', (x, y, z)))
        if b.startswith('golden'):
            k = next(c[3] for c in ring if (c[0], c[2], c[1]) == (x, y, z))
            if k not in ('stop', 'stop2') and final(x, y - 1, z) != 'redstone_block': out.append(('без питания', (x, y, z)))
    for i, c in enumerate(ring):
        if c[3] != 'stop': continue
        x, z, f = c[0], c[1], c[2]
        grp = [c]
        while ring[(i + len(grp)) % len(ring)][3] == 'stop2': grp.append(ring[(i + len(grp)) % len(ring)])
        for j in (i - 1, (i + len(grp)) % len(ring)):
            p = ring[j]
            if final(p[0], p[2], p[1]).startswith('golden'): out.append(('ускоряющий рядом со стоянкой — питание цепью', (x, f, z)))
        for g in grp:
            for a, b, cc in N6:
                if final(g[0] + a, g[2] + b, g[1] + cc) == 'redstone_block': out.append(('редстоун у стоянки', (g[0], g[2], g[1])))
        if not any(abs(bx - g[0]) + abs(bz - g[1]) == 1 and by == g[2] + 1 for bx, by, bz in buttons for g in grp):
            out.append(('нет кнопки', (x, f, z)))
    for bx, by, bz in buttons:
        if not solid_ok(final(bx, by - 1, bz)) or final(bx, by - 1, bz) == 'redstone_block': out.append(('кнопка не на сплошном блоке', (bx, by, bz)))
        for a, b, cc in N6:
            n = (bx + a, by - 1 + b, bz + cc)
            if final(*n).startswith('golden') and n not in [(c[0], c[2], c[1]) for c in ring if c[3] in ('stop', 'stop2')]:
                out.append(('кнопка питает не стоянку', n))
    return out


def checks(W, P, D, RS, ring, R, RED, outs, a):
    print('== ПРОВЕРКИ ==')
    base = base_of(W, P.SV)
    prevs = {NAMES[0]: {}, NAMES[1]: D}
    for nm in NAMES:
        o, rel, order = outs[nm]
        prev = prevs[nm]

        def terr(x, y, z, o=o, prev=prev):
            k = (x + o[0], y + o[1], z + o[2])
            b = prev.get(k)
            return b if b is not None else base(*k)
        errs = dl.check_water(rel, terr)
        se, wr = dl.check_supports(rel, order, terr)
        print(f'{nm}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
        for m in (errs + se + wr)[:6]: print('   ', m)
    ALL = {**D, **RS}

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z))
            return b if b is not None else base(x, y, z)
        return f
    final = fin_of(ALL)
    print(f'задеты построенные (воздух на месте построенного): {len(P.hits)}', P.hits[:4],
          f'| оставлено построенное в стенах/своде: {len(P.kept)}')
    opn = lambda b: b == 'air' or b.startswith(('rail', 'golden_rail', 'stone_button'))
    opened = [n for k, b in ALL.items() if opn(b) for a_, b_, c_ in N6
              for n in [(k[0] + a_, k[1] + b_, k[2] + c_)] if n not in ALL and P.SV.natural(*n)]
    print(f'протечки (природные пустоты, открытые в постройку): {len(opened)}', opened[:3], f'| заделано клеток: {len(P.sealed)}')
    wo = [k for k, b in ALL.items() if b == 'air' and any(base(k[0] + x, k[1] + y, k[2] + z).startswith('water') and (k[0] + x, k[1] + y, k[2] + z) not in ALL
                                                          for x, y, z in N6)]
    print(f'вода, открытая в воздух (сбоку или снизу): {len(wo)}', wo[:3])
    # проходимость
    box = ((-712, -660), (1744, 1870), (47, 72))
    routes = [
        ('рынок → вестибюль «Центр» → мезонин → остров линии 1', (-689, 65.0, 1806), [(-683, 55.0, 1817), (-687, 55.0, 1811), (-678, 55.0, 1818)]),
        ('рынок → пересадочный марш → остров линии 2', (-689, 65.0, 1806), [(-692, 50.0, 1795), (-693, 50.0, 1804), (-687, 50.0, 1794)]),
        ('улица → дорожка → павильон «Вокзал» → платформа', (-689, 65.0, 1781), [(-688, 55.0, 1752), (-690, 55.0, 1760)]),
        ('променад → зал ветки купола → платформа «Набережная»', (-708, 65.0, 1868), [(-695, 57.0, 1856), (-694, 57.0, 1846)]),
    ]
    bad = 0
    seen_all = {}
    for name, st, tg in routes:
        s = dl.walk_reachable(final, st, *box)
        seen_all[name] = s
        ok = all(dl.reached(s, *t) for t in tg)
        bad += 0 if ok else 1
        print(f'  маршрут {name}: {ok}' + ('' if ok else ' ' + str([t for t in tg if not dl.reached(s, *t)])))
    print('ИТОГО недостижимых точек:', bad)
    gaps = [c for c, h in P.paved.items() if not dl.reached(seen_all['улица → дорожка → павильон «Вокзал» → платформа'], c[0], h, c[1])]
    print('разрывов дорожки', len(gaps), gaps[:4], '| перепадов дорожки > 0.5 —', len(P.path_bad), '| дорожка по воде —', len(P.path_water))
    sc = stair_clear_issues(final, P.flights)
    print(f'просвет над маршами меньше 4 (не свободно 3 бл.: над ступенью и следующей): {len(sc)}', sc[:3])
    narrow = []
    for name, rows in P.walk_rows:
        for row in rows:
            if sum(1 for (x, f, z) in row if final(x, f, z) in ('air', 'stone_button:5') and final(x, f + 1, z) == 'air') < 3: narrow.append((name, row[0]))
    print(f'узких рядов (уже 3 бл.): {len(narrow)}', narrow[:4])
    lamps = [k for k, b in ALL.items() if b == LAMP] + [k for k, b in W.pre.items() if b == LAMP]
    tl = [(x, math.floor(h), z) for ts in P.targets.values() for (x, h, z) in ts]
    dark = [t for t in tl if not any(man(l, t) <= 7 for l in lamps)]
    print(f'клетки без света (фонарь дальше 7 бл. по сумме осей, свет меньше 8): {len(dark)}', dark[:5], f'| фонарей {len(P.lamps)}')
    ri = rail_issues(final, R, RED, ring, P.buttons)
    print(f'рельсы: ошибок {len(ri)}', ri[:3], f'| путь {len(ring)} бл., ускоряющих {sum(1 for b in R.values() if b.startswith("golden"))}, '
          f'остановок {sum(1 for c in ring if c[3] == "stop")}, кнопок {len(P.buttons)}')
    ti = PM.track_issues(ring + ring[:1])
    print(f'рельсы: ошибок {len(ti)} (непрерывность кольца)', ti[:2])
    # негативы
    neg = dict(ALL)
    k = next(iter(RED)); neg[k] = WALL
    print('НЕГАТИВ: под ускоряющим нет редстоуна — найдено:', len(rail_issues(fin_of(neg), R, RED, ring, P.buttons)) > 0)
    neg = dict(ALL); st = next(i for i, c in enumerate(ring) if c[3] == 'stop'); p = ring[st - 1]
    neg[(p[0], p[2], p[1])] = 'golden_rail:0'
    print('НЕГАТИВ: ускоряющий перед стоянкой — найдено:', len(rail_issues(fin_of(neg), R, RED, ring, P.buttons)) > 0)
    neg = dict(ALL)
    for z in (1812, 1813, 1814): neg[(-680, 59, z)] = WALL
    sN = dl.walk_reachable(fin_of(neg), (-689, 65.0, 1806), *box)
    print('НЕГАТИВ: верх марша заложен — остров линии 1 недостижим:', not dl.reached(sN, -683, 55.0, 1817))
    neg = dict(ALL)
    for x in (-686, -685, -684): neg[(x, 63, 1810)] = WALL
    print('НЕГАТИВ: низкий свод над лестницей вестибюля — найдено:', len(stair_clear_issues(fin_of(neg), P.flights)) > 0)
    some = P.lamps[0]
    dk = [t for t in tl if not any(man(l, t) <= 7 for l in lamps if l != some)]
    print('НЕГАТИВ: убран фонарь — тёмные клетки найдены:', len(dk) > 0)
    if P.sealed:
        neg = dict(ALL); del neg[P.sealed[0]]
        op = [1 for k, b in neg.items() if opn(b) for a_, b_, c_ in N6
              if (k[0] + a_, k[1] + b_, k[2] + c_) not in neg and P.SV.natural(k[0] + a_, k[1] + b_, k[2] + c_)]
        print('НЕГАТИВ: убрана заделка пустоты — протечка найдена:', len(op) > 0)
    if a.preview: preview(a.preview, final, W, P, D, RS)


def preview(path, final, W, P, D, RS):
    from PIL import Image, ImageDraw, ImageFont
    X0, X1, Z0, Z1, S = -712, -655, 1744, 1866, 6
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    PW = 520
    img = Image.new('RGB', (mw + 60 + PW, mh + 60), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 40 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    cols = {}
    for (x, y, z), b in {**D, **RS}.items():
        if not (X0 <= x <= X1 and Z0 <= z <= Z1): continue
        cols.setdefault((x, z), []).append((y, b))
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            c = (225, 228, 200) if not W.water(x, z) else (170, 205, 230)
            if any((x, y, z) in W.pre and W.pre[(x, y, z)] != 'air' for y in (63, 64, 65)): c = (205, 200, 190)
            if (x, z) in cols:
                ys = cols[(x, z)]
                airs = [y for y, b in ys if b == 'air']
                lo = min(airs) if airs else None
                if any(b.startswith(('rail', 'golden')) for _, b in ys): c = (40, 40, 40)
                elif lo is not None:
                    l1 = 1809 <= z <= 1820 and x <= -669
                    if lo >= 64 or (x > -687 and z < 1800): c = (240, 240, 240)
                    elif lo >= 59: c = (240, 170, 70) if 1813 <= z <= 1826 and not (-691 <= x <= -675 and z <= 1815) else (190, 150, 220)
                    elif lo >= 54 and l1: c = (120, 150, 230)
                    else: c = (90, 190, 120)
                    if any(b == FLOOR for _, b in ys): c = tuple(min(255, v + 25) for v in c)
                else: c = (150, 140, 130)
                if any(b == LAMP for _, b in ys): c = (255, 240, 120)
                if any(b.startswith('golden') for _, b in ys): c = (220, 160, 30)
                if any(b.startswith('stone_button') for _, b in ys): c = (220, 30, 30)
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    lab = [(-711, 1752, '«Вокзал»\nконечная'), (-672, 1749, 'павильон'), (-711, 1796, 'линия 2\n«Центр»'),
           (-681, 1798, 'вестибюль\n«Центр»'), (-711, 1828, 'общий тоннель:\nпути + коллектор'), (-711, 1852, '«Набережная»\n+ зал купола')]
    for x, z, t in lab: dr.text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    for x in range(X0, X1 + 1, 10): dr.text((px(x) - 10, 12), str(x), fill='black', font=F(10))
    for z in range(1750, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    # разрез по X −689 (пересадка): Z 1795…1822, Y 47…70
    ox, oy, sc = mw + 70, 40, 14
    dr.text((ox, 12), 'Разрез по X −689 (пересадочный марш, мезонин, вестибюль), Z 1795…1822', fill='black', font=F(11))
    for z in range(1795, 1823):
        for y in range(47, 71):
            b = final(-689 if z < 1806 else -685, y, z)
            c = (250, 250, 247) if b == 'air' else (140, 120, 95) if b == 'stone' else (120, 120, 125) if b == WALL else \
                (200, 190, 175) if b in (FLOOR, EDGE) else (90, 90, 95) if b.startswith('stone_brick_stairs') else (255, 240, 120) if b == LAMP else (235, 235, 230)
            dr.rectangle([ox + (z - 1795) * sc, oy + (70 - y) * sc, ox + (z - 1794) * sc - 1, oy + (71 - y) * sc - 1], fill=c)
    for y in range(48, 71, 4): dr.text((ox - 22, oy + (70 - y) * sc + 1), str(y), fill='black', font=F(9))
    for z in range(1795, 1823, 3): dr.text((ox + (z - 1795) * sc, oy + 24 * sc + 2), str(z % 100), fill='black', font=F(9))
    leg = [((90, 190, 120), 'линия 2'), ((120, 150, 230), 'линия 1 (зал «Центр»)'), ((240, 170, 70), 'коллектор'),
           ((190, 150, 220), 'мезонин, переходы'), ((240, 240, 240), 'павильоны'), ((40, 40, 40), 'рельсы'),
           ((220, 160, 30), 'ускоряющие'), ((220, 30, 30), 'кнопки'), ((255, 240, 120), 'фонари')]
    for i, (c, t) in enumerate(leg):
        dr.rectangle([ox, oy + 26 * sc + 10 + i * 16, ox + 12, oy + 26 * sc + 20 + i * 16], fill=c)
        dr.text((ox + 18, oy + 26 * sc + 8 + i * 16), t, fill='black', font=F(10))
    os.makedirs(os.path.dirname(path), exist_ok=True); img.save(path)


if __name__ == '__main__':
    main()
