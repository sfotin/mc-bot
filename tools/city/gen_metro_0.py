"""Метро, этап 0 — стенд механики на поверхности (CITY.md §7.10): ровный луг к западу от города, X −851…−818,
Z 1843…1854, грунт Y 70 (съёмка docs/terrain/metro-stand.json, r.-2.3.mca 2026-10-02). Одна схема metro-0-test.json.

Кольцо из двух путей, как в тоннеле: на запад по Z 1847, на восток по Z 1849, между ними промежуток Z 1848; петли
разворота на концах (X −851 и −818); островная станция X −845…−834 с разведением путей (Z 1844 и 1853, остров
Z 1845…1852) и остановками-«впадинами» на обоих путях (спуск — ускоряющий без питания, низ — обычный, подъём —
ускоряющий на блоке редстоуна; кнопка на верху блока платформы у спуска); «горка» X −830…−823 — подъём и спуск на
2 блока (на подъёмах по ходу — ускоряющие на редстоуне). Пол — каменный кирпич на уровне грунта, остров —
полированный андезит, край — жёлтый бетон.

Что проверить владельцу: (1) рельсы легли как в схеме (повороты, петли, разведение, без «сцепки» путей);
(2) вагонетка, пущенная с остановки, проходит горку, петлю и встаёт на остановке другого пути; (3) встаёт на
спуске «впадины» с любой скорости и стоит; (4) кнопка запускает её дальше (из вагонетки достаётся).
После проверки — снос отдельной схемой (по просьбе владельца).

Запуск: gen_metro_0.py [--outdir schemas] [--preview '']
Проверки: опоры/вода/порядок (decor_lib, порядок бота); рельсы (опоры, редстоун под ускоряющими, нет ускоряющих
рядом со стоянкой, кнопки); непрерывность кольца; проходимость острова от луга; негативы.
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import REPO, save_schema, dl  # noqa: E402
import plan_metro_v1 as PM  # noqa: E402
from gen_metro_1 import circuit_rails, rail_issues, WALL, FLOOR, EDGE, N6  # noqa: E402

NAME = 'metro-0-test.json'
FIXES = ['metro-0-fix-1.json',            # редакция 2: остановка глубиной 2 (с одним спуском вагонетка иногда проскакивала)
         'metro-0-fix-2.json',            # редакция 3: глубина 3, ускоряющие по ровному через 24 (держит, но приямок глубок)
         'metro-0-fix-3.json']            # редакция 4: остановка «на гребне» — приямок 1 бл.
VER = {1: dict(off=(2, -2), depth=1, flat=8), 2: dict(off=(4, -4), depth=2, flat=8), 3: dict(off=(8, -5), depth=3, flat=24),
       4: dict(off=(8, -8), depth='raised', flat=24)}
LAST = 4
F = 71                                   # ноги (рельс) — на блок выше грунта 70
X0, X1 = -851, -818                      # петли
ZN, ZS, ZG = 1847, 1849, 1848
ST = dict(x0=-845, x1=-834)
JN, JS = 1844, 1853
HUMP = {-830: 71, -829: 72, -828: 73, -827: 73, -826: 73, -825: 72, -824: 71}


def stand_ground():
    d = json.load(open(os.path.join(REPO, 'docs', 'terrain', 'metro-stand.json')))['parts'][0]
    return lambda x, z: d['ground'][(z - d['z0']) * d['w'] + x - d['x0']]


def track(which, v=3):
    """Путь в направлении движения: N — на запад по Z 1847, S — на восток по Z 1849; (x, z, ноги, вид)."""
    xs = range(X1 - 1, X0, -1) if which == 'N' else range(X0 + 1, X1)
    home, zj = (ZN, JN) if which == 'N' else (ZS, JS)
    dj = 2 if which == 'N' else 3
    jw, je = ST['x0'] - dj, ST['x1'] + dj
    cells = []
    for x in xs:
        f = HUMP.get(x, F)
        if x in (jw, je):
            zs = list(range(home, zj - 1, -1)) if which == 'N' else list(range(home, zj + 1))
            first = (which == 'N' and x == je) or (which == 'S' and x == jw)
            seq = zs if first else zs[::-1]
            for j, z in enumerate(seq): cells.append((x, z, f, 'curve' if j in (0, len(seq) - 1) else 'railz'))
        elif jw < x < je: cells.append((x, zj, f, 'rail'))
        else: cells.append((x, home, f, 'rail'))
    loop = [(ZN, 'curve'), (ZG, 'railz'), (ZS, 'curve')]
    cells += [(X0, z, F, k) for z, k in loop] if which == 'N' else [(X1, z, F, k) for z, k in loop[::-1]]
    V = VER[v]
    xs_stop = ST['x0'] + V['off'][0] if which == 'N' else ST['x1'] + V['off'][1]
    i = next(k for k, c in enumerate(cells) if c[0] == xs_stop and c[3] == 'rail')
    PM._stop(cells, i, V['depth'])
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    ap.add_argument('--preview', default='')
    a = ap.parse_args()
    gr = stand_ground()
    Ds = {v: build(gr, v)[0] for v in range(1, LAST)}       # построенные редакции
    D, ring, R, RED, buttons = build(gr, LAST)
    Ds[LAST] = D
    os.makedirs(a.outdir, exist_ok=True)
    o0, *_ = save_schema(dict(Ds[1]), os.path.join(a.outdir, NAME))
    print(f'{NAME}: origin {o0[0]} {o0[1]} {o0[2]} (редакция 1, построена) | записей {len(Ds[1])}')
    built = dict(Ds[1])
    for v, name in zip(range(2, LAST + 1), FIXES):
        new = Ds[v]
        fix = {k: b for k, b in new.items() if built.get(k) != b}
        for k, b in built.items():
            if k not in new and b.startswith(('rail', 'golden_rail', 'stone_button', 'redstone_block')):
                fix[k] = 'air' if k[1] > gr(k[0], k[2]) else WALL
            elif v >= 4 and k not in new and b == 'air' and k[1] <= gr(k[0], k[2]):
                fix[k] = WALL                                    # засыпка прежних приямков под полом
        of, relf, orderf, dimsf = save_schema(dict(fix), os.path.join(a.outdir, name))
        print(f'{name}: origin {of[0]} {of[1]} {of[2]} | габарит {dimsf[0]} {dimsf[1]} {dimsf[2]} | записей {len(fix)}'
              + (' (построено)' if v < LAST else ''))
        prev = dict(built)
        built.update(fix)
    checks(gr, D, ring, R, RED, buttons, prev, fix, of, relf, orderf)


def build(gr, v):
    ring = track('N', v) + track('S', v)
    R, RED = circuit_rails(ring, VER[v]['flat'])
    D = {}
    # остров: андезит, край у путей — жёлтый бетон
    for x in range(ST['x0'], ST['x1'] + 1):
        for z in range(JN + 1, JS):
            D[(x, F - 1, z)] = EDGE if z in (JN + 1, JS - 1) else FLOOR
    # пол под рельсами, опоры горки, впадины; над путём — воздух (трава, цветы)
    for (x, f, z), b in R.items():
        D[(x, f - 1, z)] = 'redstone_block' if (x, f - 1, z) in RED else WALL
        for y in range(min(gr(x, z) + 1, f - 1), f - 1): D[(x, y, z)] = WALL
        for y in range(f, F + 3): D.setdefault((x, y, z), 'air')
    for (x, f, z), b in R.items(): D[(x, f, z)] = b
    for x in range(ST['x0'], ST['x1'] + 1):                 # над островом — воздух
        for z in range(JN + 1, JS):
            for y in range(F, F + 3): D.setdefault((x, y, z), 'air')
            for y in range(gr(x, z) + 1, F - 1): D[(x, y, z)] = WALL
    buttons = []
    for i, (x, z, f, k) in enumerate(ring):
        if k not in ('stop', 'stop2') or f != F - 1: continue
        side = (x, f, z + 1) if z == JN else (x, f, z - 1)
        D[(side[0], f + 1, side[2])] = 'stone_button:5'; buttons.append((side[0], f + 1, side[2]))
    return D, ring, R, RED, buttons


def checks(gr, D, ring, R, RED, buttons, D0, fix, o, rel, order):
    print('== ПРОВЕРКИ ==')

    def base(x, y, z):
        b = D0.get((x, y, z))
        return b if b is not None else ('stone' if y <= gr(x, z) else 'air')

    def terr(x, y, z): return base(x + o[0], y + o[1], z + o[2])
    errs = dl.check_water(rel, terr)
    se, wr = dl.check_supports(rel, order, terr)
    print(f'{FIXES[-1]}: опоры/вода/порядок постройки (decor_lib, порядок бота; поверх построенного): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
    for m in (errs + se + wr)[:6]: print('   ', m)

    def fin_of(cells):
        return lambda x, y, z: cells.get((x, y, z)) or ('stone' if y <= gr(x, z) else 'air')
    final = lambda x, y, z: {**D0, **fix}.get((x, y, z)) or ('stone' if y <= gr(x, z) else 'air')
    same = all(final(*k) == b for k, b in D.items())
    print('построенное + исправление = новая редакция:', same)
    ri = rail_issues(final, R, RED, ring, buttons)
    print(f'рельсы: ошибок {len(ri)}', ri[:3], f'| кольцо {len(ring)} бл., ускоряющих {sum(1 for b in R.values() if b.startswith("golden"))}, '
          f'остановок {sum(1 for c in ring if c[3] == "stop")}, кнопок {len(buttons)}')
    ti = PM.track_issues(ring + ring[:1])
    print(f'рельсы: ошибок {len(ti)} (непрерывность кольца)', ti[:2])
    s = dl.walk_reachable(final, (-840, 71.0, 1857), (-856, -812), (1840, 1857), (66, 76))
    ok = all(dl.reached(s, *t) for t in ((-840, 71.0, 1850), (-843, 71.0, 1845), (-836, 71.0, 1852)))
    print('  маршрут луг → остров стенда:', ok)
    print('ИТОГО недостижимых точек:', 0 if ok else 1)
    neg = dict(D); neg[next(iter(RED))] = WALL
    print('НЕГАТИВ: под ускоряющим нет редстоуна — найдено:', len(rail_issues(fin_of(neg), R, RED, ring, buttons)) > 0)
    neg = dict(D); neg.pop(buttons[0])
    print('НЕГАТИВ: убрана кнопка — найдено:', len(rail_issues(fin_of(neg), R, RED, ring, buttons[1:])) > 0)


if __name__ == '__main__':
    main()
