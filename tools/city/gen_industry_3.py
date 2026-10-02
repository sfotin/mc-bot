"""Промзона, этап 3: подвал под оранжереей селекции (CITY.md §7.9; решение владельца 2026-10-01 — некоторым
культурам IC2 нужен определённый блок под пашней). Одна схема industry-3-basement.json:

- подвал под всей оранжереей (внутри X −655…−632, Z 1827…1845, кроме кольца кабельной шахты щитовой):
  пол Y 61 (полированный андезит), ходим 62, проход Y 62…64 (3 бл.);
- слой Y 65 (−1 под грядкой): под пашней — воздух, это гнездо для нужного блока, ставится снизу из подвала
  (высота подвала там 4 бл.: проход 3 + гнездо); под поливочными канавками — камень остаётся (держит воду),
  под проходами и щитовой — каменный кирпич (свод);
- вход — лестница 3 бл. в северной половине главного прохода (X −645…−643): 5 ступеней на север
  с Z 1834 до Z 1830, площадка Z 1827…1829; проём в полу над ступенями, ограждение — железная решётка
  на краях соседних грядок;
- дверь щитовой выходила на пашню — клетка перед ней (−651, 1828) замощена (подход к служебному проходу);
- свет — морские фонари в своде под проходами и в полу подвала (свет ≥ 8 на всех клетках прохода).

Запуск: gen_industry_3.py [--outdir schemas] [--preview docs/districts/industry-3-preview.png]
Мир — World(built_before('industry-3-basement.json')) + docs/terrain/industry-voids.json.
Проверки: опоры/вода/порядок; вода канавок не открыта в подвал; пустоты каньона не открыты в подвал;
проходимость без прыжков от тротуара проспекта — в подвал (углы, под гнездом), щитовая оранжереи;
гнёзда под каждой клеткой пашни (воздух, под ним проход 3 бл.); свет; ширина лестницы; кровля пустот;
задетое построенное (только задуманное); негативные прогоны.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import World, REPO, built_before, save_schema, dl, col  # noqa: E402
import plan_industry_v1 as PI  # noqa: E402
from gen_industry_1 import Terrain, place_lamps, man, rc, obj, TOP, N4, LAMP, FLOOR  # noqa: E402

NAME = 'industry-3-basement.json'
BF = 61                                      # пол подвала; ходим 62; проход 62…64; свод/гнёзда — 65
SLOT = TOP - 1                               # 65
STX = (-645, -643)                           # лестница в главном проходе
STZ = list(range(1834, 1829, -1))            # 1834 … 1830, ступени вниз на север
LAND = (1827, 1829)
SHAFT = (-655, 1827)                         # кабельная шахта щитовой (кольцо ±1 — не трогать)
PATH_FIX = (-651, 1828)                      # перед дверью щитовой — была пашня


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'industry-3-preview.png'))
    return p.parse_args()


def build(W):
    D = {}
    o = obj('gh'); x0, x1, z0, z1 = o[2:6]
    inner = rc(x0 + 1, x1 - 1, z0 + 1, z1 - 1)
    farm = {(x, z) for (x, z) in inner if W.block(x, TOP, z).startswith('farmland')}
    water = {(x, z) for (x, z) in inner if W.block(x, TOP, z) == 'water'}
    sring = {(SHAFT[0] + a, SHAFT[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1)}
    stairs = {(x, z) for x in range(STX[0], STX[1] + 1) for z in STZ}
    base = inner - sring
    farm -= {PATH_FIX}
    farm -= {(x, z) for x in (STX[0] - 1, STX[1] + 1) for z in STZ}        # под ограждение лестницы
    # 1) подвал: пол, проход, свод/гнёзда
    for (x, z) in base:
        D[(x, BF, z)] = FLOOR
        for y in range(BF + 1, SLOT): D[(x, y, z)] = 'air'
        if (x, z) in farm: D[(x, SLOT, z)] = 'air'
        elif (x, z) in water: D[(x, SLOT, z)] = 'stone'
        else: D[(x, SLOT, z)] = 'stonebrick'
    for (x, z) in rc(x0, x1, z0, z1) - inner:                 # стены подвала под стенами оранжереи
        for y in range(BF, SLOT + 1): D[(x, y, z)] = 'stonebrick'
    for (x, z) in sring - {SHAFT}:
        if (x, z) in inner:
            for y in range(BF, SLOT + 1): D[(x, y, z)] = 'stonebrick'
    # 2) лестница: ступени (каменный кирпич), под ними массив, проём в полу над ними
    for i, z in enumerate(STZ):
        t = TOP - i                                             # 66 … 62, ходим 67 … 63
        for x in range(STX[0], STX[1] + 1):
            D[(x, t, z)] = 'stone_brick_stairs:2'
            for y in range(BF, t): D[(x, y, z)] = 'stonebrick'
            for y in range(t + 1, TOP + 1): D[(x, y, z)] = 'air'
    for z in STZ:                                               # ограждение на краях соседних грядок
        for x in (STX[0] - 1, STX[1] + 1):
            D[(x, TOP, z)] = 'stonebrick'; D[(x, TOP + 1, z)] = 'iron_bars'
            for y in range(BF + 1, SLOT + 1): D[(x, y, z)] = 'stonebrick'
    for x in range(STX[0], STX[1] + 1):                         # над площадкой — свод 65 (просвет 3)
        for z in range(LAND[0], LAND[1] + 1): D[(x, SLOT, z)] = 'stonebrick'
    # 3) подход к двери щитовой
    D[(PATH_FIX[0], TOP, PATH_FIX[1])] = FLOOR
    D[(PATH_FIX[0], SLOT, PATH_FIX[1])] = 'stonebrick'
    walk = {(x, z) for (x, z) in base if (x, z) not in stairs and D.get((x, BF + 1, z)) == 'air'}
    rails = {(x, z) for x in (STX[0] - 1, STX[1] + 1) for z in STZ}
    walk -= rails
    cand = [(x, SLOT, z) for (x, z) in base if D.get((x, SLOT, z)) == 'stonebrick' and (x, z) not in rails | stairs] + \
           [(x, BF, z) for (x, z) in walk]
    targets = [(x, BF + 1, z) for (x, z) in walk] + [(x, TOP - i + 1, z) for i, z in enumerate(STZ) for x in range(STX[0], STX[1] + 1)]
    exist = [k for k, b in W.pre.items() if b == LAMP and x0 - 8 <= k[0] <= x1 + 8 and z0 - 8 <= k[2] <= z1 + 8]
    lamps = place_lamps(None, D, cand, targets, exist)
    return D, dict(farm=farm, water=water, base=base, walk=walk, stairs=stairs, targets=targets, lamps=lamps,
                   exist=exist, rect=(x0, x1, z0, z1))


def main():
    a = parse_args()
    W = World(built_before(NAME))
    T = Terrain(W)
    D, I = build(W)
    os.makedirs(a.outdir, exist_ok=True)
    o, rel, order, dims = save_schema(dict(D), os.path.join(a.outdir, NAME))
    print(f'{NAME}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(D)}')
    print('== ПРОВЕРКИ ==')

    def base(x, y, z):
        b = T.block(x, y, z)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)

    def terr(x, y, z):
        return base(x + o[0], y + o[1], z + o[2])
    errs = dl.check_water(rel, terr)
    se, wr = dl.check_supports(rel, order, terr)
    print(f'{NAME}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
    for m in (errs + se + wr)[:6]: print('   ', m)

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z))
            if b is None: b = base(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(D)

    def wet(fin):
        return [(x, y, z) for (x, z) in I['water'] for y in (TOP,) if fin(x, y, z) == 'water'
                for a_, b_, c_ in ((0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1))
                if fin(x + a_, y + b_, z + c_) == 'air']
    print(f'вода, открытая в воздух (канавки над подвалом): {len(wet(final))}', wet(final)[:3])
    opened = [n for k, b in D.items() if b == 'air' for a_, b_, c_ in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
              for n in [(k[0] + a_, k[1] + b_, k[2] + c_)] if n not in D and base(*n) in ('water', 'lava') or
              (n not in D and n[1] < TOP and base(*n) == 'air')]
    print(f'протечки (пустоты каньона и вода, открытые в подвал): {len(opened)}', opened[:3])
    allow = {(x, y, z) for (x, z) in I['farm'] for y in (SLOT,)} | {(x, y, z) for (x, z) in I['stairs'] for y in range(BF, TOP + 1)} | \
        {(x, y, z) for x in (STX[0] - 1, STX[1] + 1) for z in STZ for y in (TOP, TOP + 1)} | {(PATH_FIX[0], TOP, PATH_FIX[1]), (PATH_FIX[0], SLOT, PATH_FIX[1])}
    hit = [k for k, b in D.items() if k in W.pre and W.pre[k] != b and k not in allow and W.pre[k] not in ('dirt', 'stone', 'air')]
    print('задеты построенные (кроме гнёзд под пашней, лестницы, ограждения и подхода к щитовой):', len(hit), hit[:4])
    box = ((-664, -588), (1816, 1940), (58, 100))
    s0 = dl.walk_reachable(final, (-624, 65.0, 1820), *box)
    x0, x1, z0, z1 = I['rect']
    some_farm = sorted(I['farm'] - I['stairs'])[len(I['farm']) // 2]
    tg = {'оранжерея: главный проход': (-644, 67.0, 1836), 'оранжерея: щитовая': (-654, 67.0, 1828),
          'подвал: площадка у лестницы': (-644, 62.0, 1828), 'подвал: юго-восточный угол': (x1 - 1, 62.0, z1 - 1),
          'подвал: юго-западный угол': (x0 + 2, 62.0, z1 - 1), 'подвал: северо-восточный угол': (x1 - 1, 62.0, z0 + 1),
          f'подвал: под гнездом {some_farm}': (some_farm[0], 62.0, some_farm[1])}
    bad = 0
    for k, t in tg.items():
        ok = dl.reached(s0, *t); bad += 0 if ok else 1
        print(f'  маршрут тротуар проспекта → {k}: {ok}')
    print('ИТОГО недостижимых точек:', bad)
    nosl = [(x, z) for (x, z) in I['farm'] if not (final(x, SLOT, z) == 'air' and all(final(x, y, z) == 'air' for y in range(BF + 1, SLOT))
                                                    and final(x, BF, z) not in ('air', 'water'))]
    nosl = [c for c in nosl if c not in I['stairs']]
    print(f'гнёзда под пашней (воздух Y 65, под ним проход 3 бл.): {len(I["farm"]) - len(nosl)} из {len(I["farm"])}; без гнезда — обрыв — {len(nosl)}', nosl[:3])
    narrow = [z for z in STZ if sum(1 for x in range(STX[0], STX[1] + 1) if final(x, TOP - STZ.index(z) + 2, z) == 'air') < 3]
    print(f'узких рядов (уже 3 бл.): {len(narrow)}')
    lamps = [k for k, b in D.items() if b == LAMP] + I['exist']
    dark = [t for t in I['targets'] if not any(man(l, t) <= 7 for l in lamps)]
    print(f'клетки без света (фонарь дальше 7 бл. по сумме осей, свет меньше 8): {len(dark)}', dark[:4], f'| фонарей {len(I["lamps"])}')
    low = []
    for (x, z) in I['base']:
        tv = [yy for a_, b_, t in T.voids(x, z) for yy in range(a_, min(b_, BF - 1) + 1) if final(x, yy, z) in ('air', 'water', 'lava')]
        if tv and BF - max(tv) - 1 < 3: low.append((x, z))
    print(f'кровля каньона меньше 3 бл. под подвалом: {len(low)}')
    # негативы
    neg = dict(D); wc = sorted(I['water'])[0]; neg[(wc[0], SLOT, wc[1])] = 'air'
    print('НЕГАТИВ: убран камень под канавкой — вода в подвал найдена:', len(wet(fin_of(neg))) > 0)
    neg = dict(D)
    for x in range(STX[0], STX[1] + 1): neg[(x, TOP - 2, STZ[2])] = 'stonebrick'; neg[(x, TOP - 1, STZ[2])] = 'stonebrick'
    print('НЕГАТИВ: лестница заложена — подвал недостижим:', not dl.reached(dl.walk_reachable(fin_of(neg), (-624, 65.0, 1820), *box), x1 - 1, 62.0, z1 - 1))
    neg = dict(D); neg[(some_farm[0], SLOT, some_farm[1])] = 'stonebrick'
    nn = [c for c in I['farm'] if c not in I['stairs'] and fin_of(neg)(c[0], SLOT, c[1]) != 'air']
    print('НЕГАТИВ: гнездо заложено — найдено:', len(nn) > 0)
    some = I['lamps'][0]
    print('НЕГАТИВ: убран фонарь в подвале — тёмные клетки найдены:', any(not any(man(l, t) <= 7 for l in lamps if l != some) for t in I['targets']))
    if a.preview: preview(a.preview, final, D, I)


def preview(path, final, D, I):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    x0, x1, z0, z1 = I['rect']
    S = 12
    mw, mh = (x1 - x0 + 3) * S, (z1 - z0 + 3) * S
    S2 = 10
    secs = [('Разрез по X −644 (север → юг): лестница в подвал, главный проход', [(-644, z) for z in range(z0 - 1, z1 + 2)], (58, 78)),
            ('Разрез по Z 1840 (запад → восток): грядки, канавки (камень под водой), гнёзда Y 65 под пашней, подвал',
             [(x, 1840) for x in range(x0 - 1, x1 + 2)], (58, 78))]
    sh = sum((y1 - y0 + 1) * S2 + 34 for _, _, (y0, y1) in secs)
    img = Image.new('RGB', (max(mw, max(len(c) for _, c, _ in secs) * S2) + 60, mh + 60 + sh), (250, 250, 247)); dr = ImageDraw.Draw(img)
    dr.text((25, 6), 'Подвал оранжереи (Y 61…65): план на уровне ног подвала (Y 62) и гнёзд (Y 65); разрезы', fill='black', font=F(12))
    for x in range(x0 - 1, x1 + 2):
        for z in range(z0 - 1, z1 + 2):
            b62, b65 = final(x, 62, z), final(x, 65, z)
            if b62.startswith('stone_brick_stairs') or final(x, 66, z).startswith('stone_brick_stairs'): c = (190, 150, 90)
            elif b62 == 'air' and b65 == 'air': c = (250, 215, 120)
            elif b62 == 'air': c = (215, 215, 210)
            else: c = col(b62)
            if final(x, 61, z) == LAMP or b65 == LAMP: c = (120, 220, 230)
            dr.rectangle([25 + (x - x0 + 1) * S, 30 + (z - z0 + 1) * S, 25 + (x - x0 + 2) * S - 1, 30 + (z - z0 + 2) * S - 1], fill=c)
    dr.text((25, mh + 36), 'жёлтое — гнездо под пашней (воздух Y 65), серое — проход под канавкой/проходом, коричневое — лестница, бирюзовое — фонари',
            fill='black', font=F(11))
    oy = mh + 60
    for title, cols_, (y0, y1) in secs:
        dr.text((25, oy), title, fill='black', font=F(11)); oy += 16
        for u, (x, z) in enumerate(cols_):
            for y in range(y0, y1 + 1):
                b = final(x, y, z)
                if b in ('air', 'plant'): continue
                c = (120, 170, 225) if b == 'water' else (150, 135, 105) if b in ('stone', 'ground') and (x, y, z) not in D else col(b)
                yy = oy + (y1 - y) * S2
                dr.rectangle([25 + u * S2, yy, 25 + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
        oy += (y1 - y0 + 1) * S2 + 18
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
