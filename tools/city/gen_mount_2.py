"""Гора F, этап 2 одной порцией (CITY.md §7.7, редакция 2 — геометрия из tools/city/plan_mount_r2.py).

Три схемы (строить по порядку):
- mount-2-demolish.json — снос этапа 1 (всё из mount-1-*, кроме Горной площади с проездом и их парапетов):
  каждая клетка возвращается к рельефу до этапа 1 (грунт — по глубине: трава/земля/камень как в съёмке, выше
  грунта — воздух); забор вольера лам X −626, Z 1749…1755 — снят выше Y 89;
- mount-2-track.json — ледовая трасса 470 бл. на уровне 90: плотный лёд (Y 89), поребрики красно-белые (бетон,
  вровень), зоны вылета (снег, вровень), ограждение — кирпич на Y 89–90 (в поворотах у зоны вылета — шины,
  чёрная шерсть), на виадуке и над обрывами — стекло-панель сверху; ущелья (расчистка до грунта, стены —
  кирпич до верха, поверху еловый забор), тоннели на прямых (свод Y 94, проём Y 90…93), виадук (плита Y 88,
  опоры через 8 бл. по оси — не в вольерах, арки), насыпи; свет — морские фонари в ограждении и в своде;
  карманы пустот у льда заделаны камнем;
- mount-2-start.json — проход с Горной площади (проём в парапете), лестница к старту (марши 6 и 5), павильон
  «Старт» (навес на колоннах кварца, скамейки лицом к трассе, калитка на лёд — нижние полублоки), трибуна на
  7 рядов (ступеньки-сиденья лицом к трассе, задняя стенка со светом), арка старта (клетчатая балка, светофор —
  лампы без питания, флаги), рекламные щиты на ограждении у старта, парапет на западном краю проезда.
Вне 25 чанков загрузчика — только декор.

Запуск: gen_mount_2.py [--outdir schemas] [--preview docs/districts/mount-2-preview.png]
Мир — World(ext=True) (после постройки — built_before('mount-2-demolish.json')); рельеф до этапа 1 —
built_before('mount-1-ground.json').
Проверки: опоры/вода/порядок (decor_lib, порядок бота) для каждой схемы; снос — от этапа 1 не осталось ничего,
кроме Горной площади; трасса в итоговом мире: лёд только плотный и весь на Y 89, над льдом/поребриком/снегом
свободно 3 бл., лодке некуда выйти, поребрик между льдом и снегом, свет ≤ 5 бл.; опоры не в вольерах, пролёт
≤ 16; кровля каньона; проходимость без прыжков с Башенной площади холма E до павильона, верхнего ряда трибуны
и на лёд через калитку; обрывы без ограждения у пешеходной сети; скамейки; негативные прогоны.
"""
import argparse
import math
import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import World, REPO, BUILT, built_before, save_schema, N4, dl, col, CL, floating_over_paving  # noqa: E402
from gen_park_1 import Sch, h32, rect, bench  # noqa: E402
from gen_mount_1 import WG  # noqa: E402
import plan_mount_r2 as PR  # noqa: E402

NAMES = ['mount-2-demolish.json', 'mount-2-track.json', 'mount-2-start.json']
M1 = PR.M1
M1O = {'mount-1-ground.json': (-624, 70, 1728), 'mount-1-tower.json': (-624, 63, 1758), 'mount-1-build.json': (-624, 60, 1735)}
ICE = PR.ICE                                         # верх льда 90, лёд на Y 89
YI = ICE - 1
LAMP = ('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')
LIGHT = {'sea_lantern', 'glowstone'}
NATURAL = {2: 'grass', 3: 'dirt', 1: 'stone', 12: 'sand', 13: 'gravel', 24: 'sandstone', 82: 'clay'}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'mount-2-preview.png'))
    return p.parse_args()


def keep_cols():
    """Колонны этапа 1, которые остаются: Горная площадь с проездом и их парапеты (X −593, Z 1772/1773)."""
    k = set()
    for x in range(-609, -593):
        for z in range(1761, 1775):
            if not (z == 1774 and x < -606): k.add((x, z))
    k -= {(-609, 1773)}
    k -= {(x, z) for x in range(-599, -593) for z in range(1761, 1767)}       # бывшая дорога и стенка у кольца — сносятся
    k |= {(-593, z) for z in range(1761, 1775)} | {(-610, 1772), (-609, 1773)}
    k |= {(x, z) for x in range(-598, -593) for z in range(1764, 1767)}       # стык проезда с дорогой — мощение площади
    return k


# ---------------- снос ----------------
def demolish(W, W0, T0):
    D = Sch(W)
    keep = keep_cols()
    cells = {}
    for fn in M1:
        o = M1O[fn]
        for e in json.load(open(os.path.join(REPO, 'schemas', fn))):
            cells[(e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])] = e['block']
    restored = 0
    for (x, y, z), b in cells.items():
        if (x, z) in keep: continue
        g = T0(x, z)
        pre = W0.pre.get((x, y, z))
        if pre is not None: t = pre
        elif y > g: t = 'air'
        else:
            gb = W0.ground_block(x, z)
            top = NATURAL.get(gb, 'dirt')
            t = top if y == g else ('dirt' if g - y <= 3 and top in ('grass', 'dirt') else 'sand' if g - y <= 3 and top == 'sand' else 'stone')
            if W0.water(x, z) is not None and y > g: t = 'water'
        D.put(x, y, z, t); restored += 1
    # забор вольера лам: снять выше Y 89
    fence = 0
    for z in range(1749, 1756):
        for y in range(90, 106):
            if W.pre.get((-626, y, z), '').endswith('fence'): D.put(-626, y, z, 'air'); fence += 1
    return D, restored, fence, keep


# ---------------- трасса ----------------
def track(W, Wd, T):
    S = Sch(Wd)
    pts, lap = PR.centerline()
    ice, kerb, run, barrier, near = PR.raster(pts)
    trk = ice | kerb | run
    foot = trk | barrier
    sof = {c: near[c][1] for c in foot if c in near}
    for c in foot:
        if c not in sof:                                         # клетки ограждения вне растра — по соседу
            nb = [sof[(c[0] + a, c[1] + b)] for a in (-1, 0, 1) for b in (-1, 0, 1) if (c[0] + a, c[1] + b) in sof]
            sof[c] = nb[0] if nb else 0
    ext_of = lambda c: near[c][3] if c in near else 0
    kind = {}
    for c in foot:
        g = T(*c)
        kind[c] = 'tun' if g >= PR.TUN and ext_of(c) < 0.5 else 'cut' if g >= YI + 1 else 'gr' if g >= YI - 3 else 'emb' if g >= YI - 6 else 'via'
    # тоннель — только если вся клетка и её соседи по полосе выше свода; иначе — ущелье
    tun = {c for c in foot if kind[c] == 'tun'}
    for c in list(tun):
        if any(T(c[0] + a, c[1] + b) < PR.TUN for a, b in N4 if (c[0] + a, c[1] + b) in foot): kind[c] = 'cut'
    zoo = [r for r in PR.ZOO.values()]
    in_zoo = lambda c: any(a <= c[0] <= b and d <= c[1] <= e for a, b, d, e in zoo)
    piers, pier_skip = set(), set()
    for c in foot:
        g = T(*c)
        s = sof[c] % 8
        top = max(Wd.surf(*c) or g, S.plant_top(*c), g)
        # поверхность
        if c in ice: surf = 'packed_ice'
        elif c in kerb: surf = 'concrete:14' if (c[0] + c[1]) % 2 else 'concrete:0'
        elif c in run: surf = 'snow'
        else: surf = 'stonebrick'
        S.put(c[0], YI, c[1], surf)
        if c in barrier: S.put(c[0], YI + 1, c[1], 'stonebrick')
        k = kind[c]
        # под поверхностью
        if k in ('gr', 'emb', 'cut', 'tun'):
            for y in range(g + 1, YI): S.put(c[0], y, c[1], 'stone' if y < YI - 1 else 'stonebrick')
        else:                                                       # виадук: плита Y 88, опоры через 8 бл., арки
            S.put(c[0], YI - 1, c[1], 'stonebrick')
            if s < 1.0:
                if in_zoo(c): pier_skip.add(c)
                else:
                    for y in range(g + 1, YI - 1): S.put(c[0], y, c[1], 'stonebrick')
                    piers.add(c)
            elif s < 2.0 or s >= 7.0: S.put(c[0], YI - 2, c[1], 'stone_brick_stairs:' + ('7' if s < 2.0 else '6'))
        # выше поверхности
        lo = YI + 2 if c in barrier else YI + 1
        if k == 'tun':
            for y in range(lo, ICE + 4): S.put(c[0], y, c[1], 'air')
            S.put(c[0], ICE + 4, c[1], 'stonebrick')                 # свод
            if c in barrier:
                for y in range(YI + 2, ICE + 4): S.put(c[0], y, c[1], 'stonebrick')
        else:
            for y in range(lo, top + 1): S.put(c[0], y, c[1], 'air')
            if c in barrier and k == 'cut':                           # стена ущелья — кирпич до грунта за ней
                hi = max(T(c[0] + a, c[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (c[0] + a, c[1] + b) not in foot) \
                    if any((c[0] + a, c[1] + b) not in foot for a in (-1, 0, 1) for b in (-1, 0, 1)) else g
                for y in range(YI + 2, max(hi, g) + 1): S.put(c[0], y, c[1], 'stonebrick')
                if max(hi, g) >= ICE + 2: S.put(c[0], max(hi, g) + 1, c[1], 'spruce_fence')
    # ограждение: шины у зоны вылета, стекло над обрывом
    tyres, panes = 0, 0
    for c in barrier:
        if kind[c] == 'tun' or S.c.get((c[0], ICE + 1, c[1]), 'air') != 'air' and (c[0], ICE + 1, c[1]) in S.c and S.c[(c[0], ICE + 1, c[1])] != 'air':
            continue
        if any((c[0] + a, c[1] + b) in run for a, b in N4):
            S.put(c[0], YI + 1, c[1], 'wool:15'); tyres += 1
        out_low = [T(c[0] + a, c[1] + b) for a, b in N4 if (c[0] + a, c[1] + b) not in foot]
        if (out_low and min(out_low) < YI - 1) or kind[c] in ('via', 'emb'):
            S.put(c[0], ICE + 1, c[1], 'glass_pane'); panes += 1
    # свет: фонари в ограждении (Y 90) и в своде тоннеля — каждая клетка трассы в пределах 5 бл.
    lights = []
    lit = lambda c: any(abs(c[0] - l[0]) + abs(c[1] - l[2]) + abs(ICE - l[1]) <= 6 for l in lights)   # свет ≥ 9 у льда
    for c in sorted(barrier, key=lambda c: (sof[c], c)):
        if not any((c[0] + a, c[1] + b) in trk for a, b in N4): continue
        if any(not lit(t) for t in ((c[0] + a, c[1] + b) for a in range(-6, 7) for b in range(-6, 7)) if t in trk):
            if S.c.get((c[0], YI + 1, c[1])) in ('stonebrick', 'wool:15') and kind[c] != 'tun':
                S.put(c[0], YI + 1, c[1], 'sea_lantern'); lights.append((c[0], YI + 1, c[1]))
    for c in sorted(tun, key=lambda c: (sof[c], c)):
        if kind[c] == 'tun' and c in ice and not lit(c):
            S.put(c[0], ICE + 4, c[1], 'sea_lantern'); lights.append((c[0], ICE + 4, c[1]))
    for c in sorted(trk, key=lambda c: (sof[c], c)):
        if not lit(c):                                              # остаток — фонарь в ближайшем ограждении
            # в зоне вылета (снег) и поребрике фонарь вровень — лодку там и так тормозит; иначе — в ограждении
            cand = sorted([(abs(b[0] - c[0]) + abs(b[1] - c[1]), 0, b, YI) for b in run | kerb if abs(b[0] - c[0]) + abs(b[1] - c[1]) <= 5] +
                          [(abs(b[0] - c[0]) + abs(b[1] - c[1]), 1, b, YI + 1) for b in barrier
                           if abs(b[0] - c[0]) + abs(b[1] - c[1]) <= 6 and kind[b] != 'tun'])
            if cand:
                _, _, b, y = cand[0]
                S.put(b[0], y, b[1], 'sea_lantern'); lights.append((b[0], y, b[1]))
    # карманы пустот у льда — камнем (от верха пустоты на 4 вниз до плиты)
    plugged = 0
    for c in foot:
        ct = W.cave_top(*c)
        if ct is None or ct >= T(*c) or ct < YI - 6: continue
        for y in range(max(ct - 4, 40), YI - 1):
            if (c[0], y, c[1]) not in S.c: S.put(c[0], y, c[1], 'stone'); plugged += 1
    return dict(S=S, pts=pts, lap=lap, ice=ice, kerb=kerb, run=run, barrier=barrier, foot=foot, kind=kind, piers=piers,
                pier_skip=pier_skip, tyres=tyres, panes=panes, lights=lights, plugged=plugged, sof=sof)


# ---------------- старт: проход, лестница, павильон, трибуна, арка ----------------
def stair_col(S, T, x, z, w, mat, meta, fill='stonebrick'):
    S.put(x, w - 1, z, f'{mat}:{meta}')
    for y in range(T(x, z) + 1, w - 1): S.put(x, y, z, fill)
    for y in range(w, max(S.plant_top(x, z), S.W.surf(x, z) or 0, w) + 2): S.put(x, y, z, 'air')


def flat_col(S, T, x, z, h, b, fill='stonebrick', clear=3):
    top = int(h) - 1
    S.put(x, top, z, b)
    for y in range(T(x, z) + 1, top): S.put(x, y, z, fill)
    for y in range(top + 1, max(S.plant_top(x, z), S.W.surf(x, z) or 0, top + clear) + 1): S.put(x, y, z, 'air')


def start(W, Wt, T, TR):
    S = Sch(Wt)
    H, kind = {}, {}
    # восточная часть площади (бывшая дорога на плато и стенка у кольца) — мощение площади 79.0, по Z 1760 — подпорная стенка
    for x in range(-599, -593):
        for z in range(1761, 1767):
            flat_col(S, T, x, z, PR.SAD, 'quartz_block' if (x + 609) % 4 == 0 else 'sandstone:2'); H[(x, z)] = PR.SAD; kind[(x, z)] = 'plaza'
        g = T(x, 1760)
        for y in range(int(PR.SAD) - 1, max(g, int(PR.SAD)) + 1): S.put(x, y, 1760, 'stonebrick')
        S.put(x, max(g, int(PR.SAD)) + 1, 1760, 'stone_slab:5')
    # проход в парапете площади и лестница
    for (x, z) in PR.LINK:
        flat_col(S, T, x, z, PR.SAD, 'sandstone:2'); H[(x, z)] = PR.SAD; kind[(x, z)] = 'path'
    for xs, z, h in PR.STAIRS:
        for x in xs:
            if h == PR.SAD or z in (1754, 1753):            # площадки: Z 1761 (79) и Z 1754…1753 (85)
                flat_col(S, T, x, z, h, 'sandstone:2'); kind[(x, z)] = 'landing'
            else:
                stair_col(S, T, x, z, int(h), 'sandstone_stairs', 3); kind[(x, z)] = 'st'
            H[(x, z)] = h
    # стенки лестницы: срез грунта — облицовка, обрыв — парапет
    for xs, z, h in PR.STAIRS:
        for n in ((xs[0] - 1, z), (xs[-1] + 1, z)):
            if n in H: continue
            g = T(*n)
            if g + 1 > h:
                for y in range(int(h) - 1, g + 1): S.put(n[0], y, n[1], 'stonebrick')
            for y in range(g + 1, int(h) + 1): S.put(n[0], y, n[1], 'stonebrick')
            S.put(n[0], max(int(h), g) + 1, n[1], 'stone_slab:5')
            for y in range(max(int(h), g) + 2, max(S.plant_top(*n), Wt.surf(*n) or 0) + 1): S.put(n[0], y, n[1], 'air')
            H.setdefault(('wall',) + n, 0)
    # павильон: пол Y 89, навес на 4 колоннах (Y 94), скамейки лицом к трассе, калитка
    x0, x1, z0, z1 = PR.PAV
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            flat_col(S, T, x, z, ICE, 'quartz_block' if (x + z) % 4 == 0 else 'sandstone:2', clear=5)
            H[(x, z)] = float(ICE); kind[(x, z)] = 'pav'
    for (x, z) in ((x0, z0 + 1), (x1, z0 + 1), (x0, z1), (x1, z1)):
        for y in range(ICE, ICE + 4): S.put(x, y, z, 'quartz_block:2')
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge = x in (x0, x1) or z in (z0, z1)
            S.put(x, ICE + 4, z, 'quartz_block' if edge else 'stone_slab:15')
    S.put((x0 + x1) // 2, ICE + 4, (z0 + z1) // 2, 'sea_lantern')
    S.put(x0 + 2, ICE + 4, z0 + 1, 'sea_lantern'); S.put(x1 - 2, ICE + 4, z1 - 1, 'sea_lantern')
    benches = []
    for bx in (x1 - 3,):                                        # у выхода лестницы (X −591…−590) — свободно
        bench(S, bx, ICE, z1, 'n'); benches.append((bx, z1, 'n'))
    gate = []
    for x in range(x0 + 1, x1):
        if x == PR.START[0]: continue
        S.put(x, YI + 1, z0 - 1, 'stone_slab:5'); S.put(x, ICE + 1, z0 - 1, 'air'); gate.append((x, z0 - 1))
    # трибуна: ряды-ступеньки лицом к трассе (север), подъём на юг; задняя стенка со светом
    sx0, sx1, sz0, sz1 = PR.STAND
    for x in range(sx0, sx1 + 1):
        for z in range(sz0, sz1 + 1):
            h = ICE + (z - sz0)
            if z == sz0: flat_col(S, T, x, z, h, 'sandstone:2', clear=3); kind[(x, z)] = 'stand0'
            else: stair_col(S, T, x, z, h, 'sandstone_stairs', 2); kind[(x, z)] = 'stand'
            H[(x, z)] = float(h)
    back = sz1 + 1
    for x in range(sx0 - 1, sx1 + 1):
        g = T(x, back)
        for y in range(g + 1, ICE + (sz1 - sz0) + 2): S.put(x, y, back, 'stonebrick')
        S.put(x, ICE + (sz1 - sz0) + 2, back, 'stone_slab:5')
        if (x - sx0) % 4 == 1: S.put(x, ICE + (sz1 - sz0) + 1, back, 'sea_lantern')
    for z in range(sz0, back + 1):                               # торец трибуны с запада — стенка
        x = sx0 - 1
        g = T(x, z); h = ICE + max(0, min(z, sz1) - sz0)
        for y in range(g + 1, h + 1): S.put(x, y, z, 'stonebrick')
        S.put(x, h + 1, z, 'stone_slab:5')
        for y in range(h + 2, max(S.plant_top(x, z), Wt.surf(x, z) or 0) + 1): S.put(x, y, z, 'air')
    # стык трибуны с павильоном (X −593 | −592): ряды выше пола павильона — торец стенкой
    for z in range(sz0 + 1, sz1 + 1):
        pass
    # арка старта: колонны на ограждении, клетчатая балка Y 96, светофор (лампы без питания), флаги
    ax = PR.START[0]
    bz = sorted(z for (x, z) in TR['barrier'] if x == ax and abs(z - PR.START[1]) <= 6)
    zn, zs = bz[0], bz[-1]
    for z in (zn, zs):
        for y in range(YI + 1, ICE + 7): S.put(ax, y, z, 'quartz_block:2')
    for z in range(zn, zs + 1):
        S.put(ax, ICE + 7, z, 'wool:15' if z % 2 else 'wool:0')
        S.put(ax, ICE + 8, z, 'wool:0' if z % 2 else 'wool:15')
    mid = (zn + zs) // 2
    for dz in (-1, 0, 1): S.put(ax, ICE + 6, mid + dz, 'redstone_lamp')
    for z in (zn, zs):
        for y in range(ICE + 9, ICE + 12): S.put(ax, y, z, 'spruce_fence')
        S.put(ax + 1, ICE + 11, z, 'wool:14'); S.put(ax + 2, ICE + 11, z, 'wool:14')
    # рекламные щиты: на ограждении южной прямой восточнее старта (шерсть, 3 бл., над стенкой)
    boards = 0
    for x0b, colr in ((-578, 'wool:1'), (-570, 'wool:11'), (-562, 'wool:4')):
        for x in range(x0b, x0b + 3):
            c = (x, zs)
            if c in TR['barrier'] and TR['kind'][c] not in ('tun',):
                S.put(x, ICE + 1, zs, colr); boards += 1
    # западный край проезда (после сноса серпантина — склон): парапет X −610, Z 1766…1771
    for z in range(1766, 1772):
        c = (-610, z); g = T(*c)
        for y in range(g + 1, int(PR.SAD)): S.put(-610, y, z, 'stonebrick')
        S.put(-610, int(PR.SAD), z, 'sandstone:2'); S.put(-610, int(PR.SAD) + 1, z, 'stone_slab:1')
        for y in range(int(PR.SAD) + 2, max(S.plant_top(*c), Wt.surf(*c) or 0) + 1): S.put(-610, y, z, 'air')
    # фонари у лестницы и на площадке
    lamps = []
    for (x, z) in ((-592, 1756), (-589, 1750)):
        g = T(x, z); y0 = max(g + 1, int(H.get((-591, z), PR.SAD)))
        for y in range(g + 1, y0): S.put(x, y, z, 'stonebrick')
        for i, b in enumerate(LAMP): S.put(x, y0 + i, z, b)
        lamps.append((x, z, y0))
    return dict(S=S, H=H, kind=kind, benches=benches, gate=gate, boards=boards, lamps=lamps, arch=(ax, zn, zs))


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before(NAMES[0]), ext=True) if NAMES[0] in names else World(ext=True)
    W0 = World(built_before(M1[0]), ext=True)
    T0 = PR.Terr(W0)
    D, restored, fence, keep = demolish(W, W0, T0)
    Wd = WG(W, D)
    TR = track(W, Wd, T0)
    Wt = WG(W, D, TR['S'])
    ST = start(W, Wt, T0, TR)
    print(f'снос: восстановлено {restored} клеток этапа 1, забор лам снят на {fence} бл.; остаются колонны Горной площади: {len(keep)}')
    print(f'трасса: круг {TR["lap"]:.0f} бл., лёд {len(TR["ice"])}, поребрик {len(TR["kerb"])}, зона вылета {len(TR["run"])}, ограждение '
          f'{len(TR["barrier"])} | опор {len(TR["piers"])} кл. (пропущено в вольерах {len(TR["pier_skip"])}) | шины {TR["tyres"]}, '
          f'стекло {TR["panes"]}, фонарей {len(TR["lights"])}, карманов заделано {TR["plugged"]} бл.')
    kk = {}
    for c, k in TR['kind'].items(): kk[k] = kk.get(k, 0) + 1
    print('  клетки полосы по типу:', kk)
    print(f'старт: калитка {len(ST["gate"])} кл., скамейки {len(ST["benches"])}, щиты {ST["boards"]} бл., фонари {len(ST["lamps"])}, арка X {ST["arch"][0]}')
    outs = {}
    for nm, Sx in zip(NAMES, (D, TR['S'], ST['S'])):
        o, rel, order, dims = save_schema(Sx.c, os.path.join(args.outdir, nm))
        outs[nm] = (o, rel, order)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(Sx.c)}')
    checks(W, W0, T0, D, TR, ST, keep, outs, args)


def checks(W, W0, T0, D, TR, ST, keep, outs, args):
    S2, S3 = TR['S'], ST['S']
    print('== ПРОВЕРКИ ==')
    prevs = {NAMES[0]: {}, NAMES[1]: dict(D.c), NAMES[2]: {**D.c, **S2.c}}
    for nm, Sx in zip(NAMES, (D, S2, S3)):
        o, rel, order = outs[nm]
        prev = prevs[nm]

        def terr(x, y, z, o=o, prev=prev):
            k = (x + o[0], y + o[1], z + o[2])
            b = prev.get(k) or W.block(*k)
            return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
        errs = dl.check_water(rel, terr)
        se, wr = dl.check_supports(rel, order, terr)
        print(f'{nm}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
        for m in (errs + se + wr)[:6]: print('   ', m)
        be = dl.check_bench_front(rel, terr)
        print(f'{nm}: скамейки (место для ног): ошибок {len(be)}', be[:3])
    ALL = dict(D.c); ALL.update(S2.c); ALL.update(S3.c)

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z)) or W.block(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(ALL)
    # снос: в колоннах этапа 1 (кроме площади) не осталось блоков этапа 1
    left = []
    for fn in M1:
        o = M1O[fn]
        for e in json.load(open(os.path.join(REPO, 'schemas', fn))):
            k = (e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])
            if (k[0], k[2]) in keep: continue
            b = e['block']
            if b in ('air', 'stone', 'dirt', 'grass') or k in S2.c or k in S3.c: continue
            if final(*k) == b and b not in (W0.pre.get(k), ): left.append((k, b))
    print('снос: блоков этапа 1 осталось вне Горной площади —', len(left), left[:3])
    hi_f = [(z, y) for z in range(1749, 1756) for y in range(90, 106) if final(-626, y, z).endswith('fence')]
    print('забор лам выше Y 89 — блоков', len(hi_f))
    ice, kerb, run, bar = TR['ice'], TR['kerb'], TR['run'], TR['barrier']
    trk = ice | kerb | run

    def track_issues(fin):
        bad_lvl = [c for c in ice if fin(c[0], YI, c[1]) != 'packed_ice']
        plain = [c for c in trk if fin(c[0], YI, c[1]).split(':')[0] == 'ice']
        head = [c for c in trk if any(fin(c[0], y, c[1]) != 'air' for y in (ICE, ICE + 1, ICE + 2))]
        leak = [n for c in trk for n in ((c[0] + a, c[1] + b) for a, b in N4) if n not in trk
                and fin(n[0], ICE, n[1]) in ('air', 'snow_layer') and fin(n[0], YI, n[1]) not in ('air',)]
        drop = [n for c in trk for n in ((c[0] + a, c[1] + b) for a, b in N4) if n not in trk and fin(n[0], YI, n[1]) == 'air'
                and fin(n[0], ICE, n[1]) == 'air']
        return bad_lvl, plain, head, leak, drop
    bad_lvl, plain, head, leak, drop = track_issues(final)
    print(f'лёд не на Y {YI} или не плотный: {len(bad_lvl)} | клеток обычного льда: {len(plain)} | над трассой не свободно 3 бл.: {len(head)}',
          head[:3])
    print(f'выходов для лодки (сосед трассы без ограждения): {len(leak) + len(drop)}', (leak + drop)[:3])
    tk = [c for c in ice if TR['kind'].get(c) != 'tun' and c in TR['foot'] and any((c[0] + a, c[1] + b) in run for a, b in N4)]
    print('лёд касается зоны вылета без поребрика:', len(tk))
    lights = [k for k, b in ALL.items() if b.split(':')[0] in LIGHT]
    dark = [c for c in trk if not any(abs(c[0] - a) + abs(c[1] - cc) + abs(ICE - b) <= 7 for a, b, cc in lights)]
    print('клетки трассы без света (фонарь дальше 7 бл. по сумме осей, свет меньше 8 — мобы спавнятся):', len(dark), dark[:3])
    # опоры виадука: не в вольерах, пролёт ≤ 16 по оси
    piers = TR['piers']
    pz = [c for c in piers if any(a <= c[0] <= b and d <= c[1] <= e for a, b, d, e in PR.ZOO.values())]
    sof = TR['sof']
    via_s = sorted({round(sof[c]) for c in TR['foot'] if TR['kind'][c] == 'via'})
    secs, cur = [], []
    for v in via_s:
        if cur and v - cur[-1] > 2: secs.append(cur); cur = []
        cur.append(v)
    if cur: secs.append(cur)
    span = 0
    for sec in secs:
        ps = sorted({round(sof[c]) for c in piers if sec[0] <= round(sof[c]) <= sec[-1]})
        rows = sorted({p // 8 for p in ps})
        marks = [sec[0]] + [r * 8 for r in rows] + [sec[-1]]
        span = max([span] + [b - a for a, b in zip(marks, marks[1:])])
    print(f'опоры в вольерах зоопарка: {len(pz)} | наибольший пролёт виадука по оси ≈ {span} бл. (норма ≤ 16)')
    roofs = []
    for c in TR['foot']:
        ct = W.cave_top(*c)
        if ct is None or ct >= T0(*c): continue
        air = [y for y in range(max(ct - 8, 40), min(YI, T0(*c) + 1)) if final(c[0], y, c[1]) == 'air']
        if air: roofs.append((YI - max(air) - 1, c))
    print('кровля каньона под льдом (пустоты, оставшиеся под трассой): мин.', min(roofs)[0] if roofs else '—', '(норма ≥ 3)')
    hill = [k for k in ALL if k[2] >= 1773 and k[0] <= -607 and (k[0], k[2]) not in keep]
    print('задеты Северная лестница холма E или Башенная площадь:', len(hill), hill[:3])
    south = max(k[2] for k in S2.c)
    print(f'трасса на юг — до Z {south} (предел 1760):', 'OK' if south <= 1760 else 'ОШИБКА')
    # пешеходы
    H = ST['H']
    net = {c: h for c, h in H.items() if isinstance(c[0], int)}
    plaza = {(x, z) for x in range(-609, -593) for z in range(1761, 1775)}
    walkable = set(net) | plaza | {(x, z) for x in range(-609, -593) for z in range(1761, 1775)} | {(x, z) for x in range(-610, -600) for z in range(1775, 1779)} | set(ST['gate']) | \
        {c for c in ice if -592 <= c[0] <= -584}
    box = ((-612, -582), (1733, 1779), (70, 100))

    def walk(fin):
        f2 = lambda x, y, z: fin(x, y, z) if (x, z) in walkable else ('stone' if y < 60 else 'air')
        return dl.walk_reachable(f2, (-606, 79.0, 1777), *box)
    seen = walk(final)
    tg = {'проход в парапете (−592,1761)': (-592, 79.0, 1761), 'площадка лестницы (−591,1754)': (-591, 85.0, 1754),
          'павильон (−588,1745)': (-588, 90.0, 1745), 'трибуна, нижний ряд (−600,1742)': (-600, 90.0, 1742),
          'трибуна, верхний ряд (−600,1748)': (-600, 96.0, 1748), 'лёд у калитки (−589,1738)': (-589, 90.0, 1738)}
    bad = 0
    for k, (x, y, z) in tg.items():
        ok = dl.reached(seen, x, y, z); bad += 0 if ok else 1
        print(f'  маршрут → {k}: {ok}')
    print('ИТОГО недостижимых точек:', bad)
    fl = floating_over_paving(final, ALL, {c: h for c, h in net.items() if ST['kind'].get(c) not in ('st', 'stand')})
    print('висящие над мощением (под предметом воздух или нижний полублок):', len(fl), fl[:3])

    def drops(fin):
        out = []
        for c, h in net.items():
            if ST['kind'].get(c) in ('stand',): continue
            for a, b in N4:
                n = (c[0] + a, c[1] + b)
                if n in net or n in plaza or n in walkable: continue
                y = math.ceil(h)
                if fin(n[0], y, n[1]) != 'air': continue
                yy = y
                while yy > 50 and fin(n[0], yy, n[1]) == 'air': yy -= 1
                if yy + 1 <= h - 2: out.append((c, n))
        return out
    dr_ = drops(final)
    print('обрыв ≥ 2 у края пешеходной сети без ограждения —', len(dr_), dr_[:4])
    # негативы
    negc = dict(ALL); g0 = ST['gate'][0]; negc[(g0[0], YI + 1, g0[1])] = 'stonebrick'
    for g in ST['gate']: negc[(g[0], YI + 1, g[1])] = 'stonebrick'
    print('НЕГАТИВ: калитка полным блоком — лёд из павильона недостижим:', not dl.reached(walk(fin_of(negc)), -589, 90.0, 1738))
    negc = dict(ALL)
    for x in (-591, -590): negc[(x, 82, 1758)] = 'stonebrick'
    print('НЕГАТИВ: ступенька лестницы полным блоком — павильон недостижим:', not dl.reached(walk(fin_of(negc)), -588, 90.0, 1745))
    negc = dict(ALL); b0 = sorted(c for c in bar if any((c[0] + a, c[1] + b) in ice for a, b in N4) and TR['kind'][c] == 'gr')[0]
    negc[(b0[0], ICE, b0[1])] = 'air'; negc[(b0[0], YI, b0[1])] = 'packed_ice'
    print('НЕГАТИВ: снят блок ограждения — выход для лодки найден:', len(sum(track_issues(fin_of(negc))[3:], [])) > 0)
    negc = dict(ALL); i0 = sorted(ice)[0]; negc[(i0[0], YI, i0[1])] = 'ice'
    print('НЕГАТИВ: обычный лёд — найден:', len(track_issues(fin_of(negc))[1]) > 0)
    negc = dict(ALL); negc[(i0[0], ICE + 1, i0[1])] = 'stonebrick'
    print('НЕГАТИВ: блок над льдом — найден:', len(track_issues(fin_of(negc))[2]) > 0)
    if args.preview: preview(args.preview, final, TR)


def preview(path, final, TR):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    C = dict(CL); C.update({'packed_ice': (150, 190, 245), 'concrete:14': (200, 40, 40), 'concrete:0': (245, 245, 245),
                            'snow': (252, 252, 255), 'stonebrick': (125, 125, 125), 'wool:15': (30, 30, 30), 'glass_pane': (160, 205, 235),
                            'sea_lantern': (200, 235, 235), 'sandstone:2': (225, 212, 160), 'sandstone_stairs': (215, 200, 150),
                            'quartz_block': (240, 238, 232), 'quartz_block:2': (240, 238, 232), 'stone_slab:15': (236, 234, 228),
                            'spruce_fence': (100, 70, 40), 'wool:0': (240, 240, 240), 'wool:14': (180, 40, 40), 'grass': (95, 150, 60)})
    cc = lambda b: C.get(b) or C.get(b.split(':')[0]) or col(b)
    X0, X1, Z0, Z1 = -664, -530, 1638, 1778
    S = 5
    img = Image.new('RGB', ((X1 - X0 + 1) * S + 40, (Z1 - Z0 + 1) * S + 40), 'white')
    dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 125
            while y > 40 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            if b == 'stone':
                k = (max(60, min(y, 115)) - 60) / 55; c = (int(200 - 80 * k), int(210 - 50 * k), int(140 - 60 * k))
            elif b == 'water': c = (90, 140, 210)
            else: c = cc(b)
            if (x, z) in TR['ice'] and TR['kind'].get((x, z)) == 'tun': c = (70, 90, 140)
            dr.rectangle([20 + (x - X0) * S, 30 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 30 + (z - Z0 + 1) * S - 1], fill=c)
    for x in range(-660, X1 + 1, 10): dr.text((20 + (x - X0) * S - 8, 16), str(x), fill='black', font=F(9))
    for z in range(1640, Z1 + 1, 10): dr.text((0, 30 + (z - Z0) * S - 5), str(z), fill='black', font=F(8))
    dr.text((20, 2), 'Гора F, этап 2: трасса (вид сверху; тоннели — тёмно-синие), старт, трибуна; снос этапа 1', fill='black', font=F(11))
    img.save(path)
    print('превью', path, img.size)


if __name__ == '__main__':
    main()
