"""План района «Промзона» v1 (CITY.md §3, §7.9): рельеф + построенное (world_model.py), 25 рабочих чанков
загрузчика (§3.1), промплощадка, проезды (связь с главным проспектом и улицей набережной), корпуса по подзонам
§3.3, залы реакторов (каждый реактор — в одном чанке), градирни, загрузчик в центре чанка (−39, 117),
технические галереи под проездами (кабели IC2, МЭ, трубы, проход ≥ 2), коллектор к проспекту,
цех булыжника (целый чанк, глубоко), пустоты третьей ветки каньона под площадкой, этапы, вид с юга.

Запуск: plan_industry_v1.py [--out docs/districts/industry-plan-v1.png]
Печатает проверки плана (с негативными прогонами): корпуса в 25 чанках, пересечения, реакторные залы
в одном чанке и их размеры, загрузчик в центре чанка внутри диспетчерской, цех булыжника = чанк,
связность мощения от проспекта и от набережной до двери каждого корпуса, ширина проездов ≥ 3,
уклоны пандусов (0.5 не чаще чем через 3 бл.), земляные работы, пустоты под корпусами и галереями
(кровля < 3 — закладка), резерв трасс под проспектом.
"""
import argparse
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO  # noqa: E402

X0, X1, Z0, Z1 = -664, -590, 1810, 1938          # окно картинки (восточнее X −593 рельефа нет)
S = 7
ML, MT = 46, 30
WALK = 67.0                                      # промплощадка: верх мощения Y 66, ходим 67.0
LOADER = {(cx, cz) for cx in range(-41, -37) for cz in range(114, 119)} | {(-40, 119), (-39, 119), (-38, 119),
                                                                          (-39, 120), (-38, 120)}
LOADER_CHUNK = (-39, 117)
LOADER_BLOCK = (-617, 1879)                      # центр чанка X −624…−609, Z 1872…1887 (≈ −616.5, 1879.5)

ROAD = (120, 120, 120, 235)
APRON = (200, 195, 185, 245)

# ---- проезды: (ключ, подпись, X0, X1, Z0, Z1) — ширина 6, ходим 67.0 (кроме пандусов к соседям) ----
ROADS = [
    ('r1', 'Заводская ул. (С–Ю)', -627, -622, 1821, 1935),
    ('r2', 'Промышленный пр. (З–В)', -656, -593, 1885, 1890),
    ('r3', 'Береговой проезд (З–В)', -660, -593, 1850, 1855),
]
# пандусы к соседям: (подпись, ось, клетки, отметки ходьбы по оси)
RAMPS = {
    'r1': ('от тротуара проспекта 65.0', 'z', {1821: 65.0, 1824: 65.5, 1827: 66.0, 1830: 66.5, 1833: 67.0}),
    'r3': ('от улицы набережной 65.0', 'x', {-660: 65.0, -657: 65.5, -654: 66.0, -651: 66.5, -648: 67.0}),
}
# ---- корпуса: (ключ, подпись, X0, X1, Z0, Z1, этап, верх Y, цвет, двери [(x, z)]) ----
OBJ = [
    ('npp', 'Корпус АЭС: 4 зала реакторов', -621, -593, 1891, 1919, 1, 83, (236, 236, 240), [(-621, 1897), (-621, 1912)]),
    ('ct1', 'Градирня 1 (бассейн — вода для помп)', -621, -609, 1922, 1934, 1, 99, (205, 205, 210), [(-615, 1922)]),
    ('ct2', 'Градирня 2', -606, -594, 1922, 1934, 1, 99, (205, 205, 210), [(-600, 1922)]),
    ('ore', 'Цех переработки руд', -656, -631, 1859, 1869, 1, 80, (205, 120, 90), [(-644, 1859), (-631, 1864)]),
    ('prod', 'Производственный цех (МЭ-ячейки)', -656, -631, 1873, 1882, 1, 80, (190, 105, 80), [(-631, 1877), (-644, 1882)]),
    ('wh', 'Центральный склад (МЭ-хранилище)', -618, -604, 1830, 1846, 1, 78, (215, 180, 120), [(-611, 1846), (-618, 1838)]),
    ('disp', 'Диспетчерская: загрузчик, контроллер МЭ', -620, -611, 1873, 1882, 2, 98, (120, 160, 210), [(-620, 1877)]),
    ('sub', 'Подстанция: энергохранилища, трансформаторы', -607, -594, 1873, 1882, 2, 75, (110, 140, 190), [(-600, 1882)]),
    ('craft', 'Цех автокрафта МЭ', -620, -611, 1859, 1869, 2, 77, (175, 110, 90), [(-615, 1859)]),
    ('matter', 'Лаборатория материи', -607, -594, 1859, 1869, 2, 79, (160, 130, 200), [(-600, 1859)]),
    ('turb', 'Машинный зал (переработка тепла)', -640, -628, 1894, 1918, 2, 81, (150, 165, 175), [(-628, 1900)]),
    ('pump', 'Насосная (водозабор)', -656, -644, 1894, 1903, 2, 74, (120, 185, 200), [(-650, 1894)]),
    ('gh', 'Оранжерея селекции', -656, -631, 1826, 1846, 3, 76, (170, 220, 200), [(-644, 1846)]),
    ('wind', 'Ветряки (3 мачты)', -601, -594, 1828, 1846, 3, 96, (240, 240, 200), [(-601, 1838)]),
]
# подходы от дверей к проездам (мощение)
APRONS = {
    'ore': [(-646, -642, 1856, 1858), (-630, -628, 1863, 1865)],
    'prod': [(-630, -628, 1876, 1878), (-646, -642, 1883, 1884)],
    'wh': [(-613, -609, 1847, 1849), (-621, -619, 1837, 1839)],
    'disp': [(-621, -621, 1876, 1878)],
    'sub': [(-602, -598, 1883, 1884)],
    'craft': [(-617, -613, 1856, 1858)],
    'matter': [(-602, -598, 1856, 1858)],
    'turb': [],                                   # дверь выходит прямо на Заводскую (X −627)
    'pump': [(-652, -648, 1891, 1893)],
    'gh': [(-646, -642, 1847, 1849)],
    'wind': [(-603, -602, 1828, 1849)],           # служебная дорожка вдоль мачт
    'ct': [(-621, -593, 1920, 1921)],             # дорожка к градирням вдоль корпуса АЭС
}
# реакторные залы (внутренность): (подпись, X0, X1, Z0, Z1, нужно внутри)
HALLS = [
    ('реактор 1 (обычный)', -620, -609, 1892, 1903, (3, 3)),
    ('реактор 2 (обычный)', -607, -594, 1892, 1903, (3, 3)),
    ('жидкостный 1', -620, -609, 1905, 1918, (11, 11)),     # 9×9×5 + обход 1 с двух сторон
    ('жидкостный 2', -607, -594, 1905, 1918, (11, 11)),
]
COBBLE = (-39, 115, 14, 20)                      # чанк, пол Y 14, потолок Y 20 (внутри 15…19)
GALLERY_Y = (60, 64)                             # технические галереи под проездами: пол 60, внутри 61…63, потолок 64
GALLERIES = [('r1', -626, -623, 1821, 1919), ('r2', -652, -594, 1886, 1889), ('r3', -656, -594, 1851, 1854)]
RESERVE = [('метро 1 + коллектор (проспект)', -660, -593, 1812, 1820)]
STACK = (-608, 1904)                             # вентиляционная труба АЭС на стыке залов


def rc(x0, x1, z0, z1):
    return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


def disc(cx, cz, r):
    return {(x, z) for x in range(cx - 8, cx + 9) for z in range(cz - 8, cz + 9) if math.hypot(x - cx, z - cz) <= r}


def chunk(x, z):
    return (x >> 4, z >> 4)


def footprint(o):
    k, _, x0, x1, z0, z1, *_ = o
    if k in ('ct1', 'ct2'):
        return disc((x0 + x1) // 2, (z0 + z1) // 2, 6.5)
    return rc(x0, x1, z0, z1)


def check(obj=OBJ, roads=ROADS, aprons=APRONS, halls=HALLS, loader=LOADER_BLOCK, cobble=COBBLE, quiet=False):
    """Все проверки плана; возвращает список ошибок (для негативных прогонов)."""
    err = []
    foot = {o[0]: footprint(o) for o in obj}
    # 1. корпуса — в 25 чанках
    for k, c in foot.items():
        out = {chunk(*p) for p in c} - LOADER
        if out: err.append(f'{k}: вне 25 чанков {sorted(out)}')
    # 2. пересечения корпусов друг с другом и с проездами
    allroad = set().union(*(rc(*r[2:6]) for r in roads))
    ks = list(foot)
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            if foot[a] & foot[b]: err.append(f'пересечение {a}/{b}')
        if foot[a] & allroad: err.append(f'{a} на проезде')
    # 3. реакторные залы — каждый в одном чанке, размер
    for n, x0, x1, z0, z1, need in halls:
        ch = {chunk(x, z) for x, z in rc(x0, x1, z0, z1)}
        if len(ch) != 1: err.append(f'{n}: зал в {len(ch)} чанках')
        if ch - LOADER: err.append(f'{n}: вне 25 чанков')
        if x1 - x0 + 1 < need[0] or z1 - z0 + 1 < need[1]: err.append(f'{n}: мал')
        if not (rc(x0, x1, z0, z1) <= foot['npp']): err.append(f'{n}: вне корпуса АЭС')
    # 4. загрузчик
    cx, cz = LOADER_CHUNK
    if chunk(*loader) != LOADER_CHUNK or abs(loader[0] - (cx * 16 + 7.5)) > 0.5 or abs(loader[1] - (cz * 16 + 7.5)) > 0.5:
        err.append('загрузчик не в центре чанка (−39, 117)')
    if loader not in foot['disp']: err.append('загрузчик вне диспетчерской')
    # 5. цех булыжника — целый чанк из 25, высота ≥ 5 внутри
    if (cobble[0], cobble[1]) not in LOADER: err.append('цех булыжника вне 25 чанков')
    if cobble[3] - cobble[2] - 1 < 5: err.append('цех булыжника ниже 5')
    # 6. ширина проездов
    for k, n, x0, x1, z0, z1 in roads:
        if min(x1 - x0, z1 - z0) + 1 < 3: err.append(f'{k}: уже 3 бл.')
    # 7. связность: проезды + подходы; старт — тротуар проспекта и улица набережной
    paved = set(allroad)
    for v in aprons.values():
        for r in v: paved |= rc(*r)
    seen, st = set(), [(-624, 1821), (-660, 1852)]
    while st:
        c = st.pop()
        if c in seen or c not in paved: continue
        seen.add(c); st += [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]
    for o in obj:
        k, doors = o[0], o[9]
        for d in doors:
            if not any((d[0] + a, d[1] + b) in seen for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                err.append(f'{k}: дверь {d} без мощёного подхода от проспекта/набережной')
            if d not in foot[k]: err.append(f'{k}: дверь {d} не на стене корпуса')
    # проспект и набережная связаны между собой через промзону
    for s in ((-624, 1821), (-660, 1852)):
        if s not in seen: err.append(f'старт {s} не на мощении')
    # 8. уклоны пандусов: 0.5 не чаще чем через 3 бл.
    for k, (n, ax, prof) in RAMPS.items():
        ps = sorted(prof)
        for a, b in zip(ps, ps[1:]):
            if abs(prof[b] - prof[a]) > 0.5 or abs(b - a) < 3: err.append(f'{k}: пандус круче нормы {a}→{b}')
        if prof[ps[-1]] != WALK and prof[ps[0]] != WALK: err.append(f'{k}: пандус не выходит на 67.0')
    if not quiet:
        print('  ошибок:', len(err), '|', '; '.join(err[:6]) if err else 'OK')
    return err, foot, seen, paved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'industry-plan-v1.png'))
    args = ap.parse_args()
    W = World()

    print('== проверки плана ==')
    err, foot, seen, paved = check()
    used = {}
    for k, c in foot.items():
        for p in c: used.setdefault(chunk(*p), set()).add(k)
    used.setdefault(COBBLE[:2], set()).add('cobble')
    free = sorted(LOADER - set(used))
    print('25 чанков: занято', len(LOADER) - len(free), '| свободно:', free or 'нет')
    print('корпуса вне 25 чанков:', [e for e in err if 'вне 25' in e] or 'нет', '| пересечения:',
          [e for e in err if 'пересеч' in e or 'на проезде' in e] or 'нет')
    for n, x0, x1, z0, z1, need in HALLS:
        print(f'  {n}: внутри {x1 - x0 + 1}×{z1 - z0 + 1}, чанк {chunk(x0, z0)}, нужно ≥ {need[0]}×{need[1]} —',
              'OK' if not [e for e in err if e.startswith(n)] else 'ОШИБКА')
    print('загрузчик', LOADER_BLOCK, 'в центре чанка (−39, 117), в диспетчерской:', 'OK' if not [e for e in err if 'загрузчик' in e] else 'ОШИБКА')
    print(f'цех булыжника: чанк {COBBLE[:2]}, пол Y {COBBLE[2]}, внутри Y {COBBLE[2] + 1}…{COBBLE[3] - 1} (≥ 5) —',
          'OK' if not [e for e in err if 'булыжн' in e] else 'ОШИБКА')
    print('двери без мощёного подхода:', [e for e in err if 'дверь' in e] or 'нет', f'| мощёных клеток в сети {len(seen)}')
    print('ширина проездов ≥ 3 и пандусы (0.5 не чаще чем через 3 бл.):',
          'OK' if not [e for e in err if 'уже' in e or 'пандус' in e] else 'ОШИБКА')
    # негативные прогоны
    neg = []
    h2 = [(n, x0 + 4, x1 + 4, z0, z1, nd) for n, x0, x1, z0, z1, nd in HALLS]
    neg.append(('зал сдвинут на 4 бл. на восток (через границу чанка)', any('чанках' in e for e in check(halls=h2, quiet=True)[0])))
    neg.append(('загрузчик на 2 бл. от центра чанка', any('загрузчик' in e for e in check(loader=(-615, 1879), quiet=True)[0])))
    neg.append(('без Заводской АЭС отрезана',
                any('npp' in e for e in check(roads=[r for r in ROADS if r[0] != 'r1'], quiet=True)[0])))
    a2 = dict(APRONS); a2['pump'] = []
    neg.append(('без подхода к насосной', any('pump' in e for e in check(aprons=a2, quiet=True)[0])))
    o3 = [o if o[0] != 'gh' else ('gh', o[1], -660, -631, *o[4:]) for o in OBJ]
    neg.append(('оранжерея заходит в чанк −42 (вне 25)', any('gh: вне 25' in e for e in check(obj=o3, quiet=True)[0])))
    neg.append(('цех булыжника в чанке (−41, 119)', any('булыжн' in e for e in check(cobble=(-41, 119, 14, 20), quiet=True)[0])))
    print('НЕГАТИВ:', '; '.join(f'{n} — {"ошибка найдена" if ok else "НЕ НАЙДЕНА"}' for n, ok in neg))

    # земляные работы под площадкой (ходим 67.0 → верх грунта/мощения 66)
    top = int(WALK) - 1
    cells = set().union(*foot.values()) | set(paved)
    cut = fill = 0; deep = 0
    for x, z in cells:
        g = W.surf(x, z)
        if g is None: continue
        if g > top: cut += g - top
        elif g < top:
            fill += top - g
            if top - g >= 4: deep += 1
    print(f'земляные работы (площадка — верх Y {top}): срезка {cut} бл., подсыпка {fill} бл., подсыпка ≥ 4 — {deep} кл. '
          f'(берег бухты у насосной — подпорная стенка)')
    # пустоты под площадкой
    thin = {}
    for k, c in list(foot.items()) + [('гал. ' + g[0], rc(*g[1:])) for g in GALLERIES]:
        lim = GALLERY_Y[0] if k.startswith('гал.') else top
        n = [W.cave_top(x, z) for x, z in c if W.cave_top(x, z) is not None and lim - W.cave_top(x, z) - 1 < 3]
        if n: thin[k] = (len(n), max(n))
    vol = sum(max(0, t - 54) for k, c in list(foot.items()) + [('g', rc(*g[1:])) for g in GALLERIES]
              for x, z in c for t in [W.cave_top(x, z)] if t is not None and t >= 55)
    print('пустоты с кровлей < 3 под корпусами/галереями (кл., верх пустоты):', thin or 'нет',
          '| верх оценочный (caves.json: воздух колонны суммарно) — уточнить по r.-2.3.mca')
    print(f'  → закладка камнем от верха пустоты до Y 55 в этих колоннах ≈ {vol} бл. (в схеме земляных работ)')
    cob = [W.cave_top(x, z) for x, z in rc(COBBLE[0] * 16, COBBLE[0] * 16 + 15, COBBLE[1] * 16, COBBLE[1] * 16 + 15)]
    print(f'  цех булыжника: колонн с пустотами {sum(1 for t in cob if t is not None)} из 256 → цех — замкнутая коробка '
          f'(стены, пол, потолок), пустоты вокруг не мешают')
    rv = sorted({k for k, c in foot.items() for x, z in c for _, x0, x1, z0, z1 in RESERVE if x0 <= x <= x1 and z0 <= z <= z1})
    print('корпуса над резервом метро/коллектора:', rv or 'нет', '| галерея Заводской выходит к резерву на Z 1821')
    built = [k for k, c in foot.items() if any(W.pre.get((x, y, z)) not in (None, 'grass', 'air', 'ground')
                                               for x, z in c for y in range(60, 110))]
    print('корпуса поверх построенного:', built or 'нет', '| стык Берегового проезда — бортик набережной X −661 '
          '(Z 1850…1855) разобрать в створе')
    print('итог проверок плана:', 'OK' if not err and all(ok for _, ok in neg) else 'ОШИБКИ')

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
    EH = 60 * 4                                   # вид с юга: Y 60…120, 4 px на блок
    img = Image.new('RGB', (ML + mw + 560, MT + mh + EH + 70), (250, 250, 247))
    dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: ML + (x - X0) * S
    pz = lambda z: MT + (z - Z0) * S

    def rect(x0, x1, z0, z1, fill, outline=None, w=2):
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], fill=fill, outline=outline, width=w)

    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            if W.inside(x, z): rect(x, x, z, z, colr(x, z))
            else: rect(x, x, z, z, (225, 225, 225))
    # пустоты с тонкой кровлей — штриховка
    for x in range(-660, -592):
        for z in range(1824, 1936):
            t = W.cave_top(x, z)
            if t is not None and t >= 55 and (x + z) % 2 == 0: rect(x, x, z, z, (150, 40, 150, 90))
    for k, n, x0, x1, z0, z1 in ROADS: rect(x0, x1, z0, z1, ROAD)
    for v in APRONS.values():
        for r in v: rect(*r, APRON)
    stc = {1: (200, 30, 30), 2: (30, 90, 200), 3: (30, 140, 60)}
    for o in OBJ:
        k, name, x0, x1, z0, z1, st, ytop, fill, doors = o
        for (x, z) in foot[k]: rect(x, x, z, z, fill + (240,))
        if k in ('ct1', 'ct2'):
            cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
            dr.ellipse([px(cx - 6), pz(cz - 6), px(cx + 7), pz(cz + 7)], outline=stc[st], width=3)
            dr.ellipse([px(cx - 4), pz(cz - 4), px(cx + 5), pz(cz + 5)], outline=(120, 120, 130), width=1)
        else:
            rect(x0, x1, z0, z1, None, stc[st], 3)
        for d in doors: rect(d[0], d[0], d[1], d[1], (60, 40, 20))
    for n, x0, x1, z0, z1, _ in HALLS:
        rect(x0, x1, z0, z1, None, (90, 90, 100), 1)
    for n, x0, x1, z0, z1, _ in HALLS[2:]:
        cx, cz = (x0 + x1 + 1) / 2, (z0 + z1 + 1) / 2
        dr.ellipse([px(cx - 5.5), pz(cz - 5.5), px(cx + 5.5), pz(cz + 5.5)], outline=(150, 150, 160), width=2)
    rect(STACK[0], STACK[0], STACK[1], STACK[1], (200, 40, 40))
    rect(LOADER_BLOCK[0], LOADER_BLOCK[0], LOADER_BLOCK[1], LOADER_BLOCK[1], (255, 220, 0), (0, 0, 0), 1)
    # мачты ветряков
    for z in (1831, 1838, 1845):
        dr.ellipse([px(-598), pz(z), px(-596), pz(z + 2)], fill=(80, 80, 80))
    # галереи — пунктир
    for g in GALLERIES:
        _, gx0, gx1, gz0, gz1 = g
        if gx1 - gx0 > gz1 - gz0:
            y = (pz(gz0) + pz(gz1 + 1)) / 2
            for x in range(gx0, gx1, 3): dr.line([px(x), y, px(x + 2), y], fill=(230, 120, 0), width=3)
        else:
            xx = (px(gx0) + px(gx1 + 1)) / 2
            for z in range(gz0, gz1, 3): dr.line([xx, pz(z), xx, pz(z + 2)], fill=(230, 120, 0), width=3)
    # цех булыжника — контур чанка
    cbx, cbz = COBBLE[0] * 16, COBBLE[1] * 16
    for i in range(0, 16, 2):
        dr.line([px(cbx + i), pz(cbz), px(cbx + i + 1), pz(cbz)], fill=(90, 50, 20), width=2)
        dr.line([px(cbx + i), pz(cbz + 16), px(cbx + i + 1), pz(cbz + 16)], fill=(90, 50, 20), width=2)
        dr.line([px(cbx), pz(cbz + i), px(cbx), pz(cbz + i + 1)], fill=(90, 50, 20), width=2)
        dr.line([px(cbx + 16), pz(cbz + i), px(cbx + 16), pz(cbz + i + 1)], fill=(90, 50, 20), width=2)
    # резерв
    for n, x0, x1, z0, z1 in RESERVE:
        rect(x0, x1, z0, z1, (230, 120, 0, 40))
    # сетка чанков, 25 чанков
    for x in range(X0, X1 + 2):
        if x % 16 == 0: dr.line([px(x), MT, px(x), MT + mh], fill=(70, 70, 70, 90), width=1)
    for z in range(Z0, Z1 + 2):
        if z % 16 == 0: dr.line([ML, pz(z), ML + mw, pz(z)], fill=(70, 70, 70, 90), width=1)
    for (cx, cz) in LOADER:
        col = (255, 200, 0) if (cx, cz) == LOADER_CHUNK else (60, 60, 60)
        for e in (((0, 0), (16, 0)), ((0, 16), (16, 16)), ((0, 0), (0, 16)), ((16, 0), (16, 16))):
            a, b = e
            na = (cx + (1 if a[0] == b[0] == 16 else -1 if a[0] == b[0] == 0 else 0), cz + (1 if a[1] == b[1] == 16 else -1 if a[1] == b[1] == 0 else 0))
            if na in LOADER and (cx, cz) != LOADER_CHUNK and na != LOADER_CHUNK: continue
            dr.line([px(cx * 16 + a[0]), pz(cz * 16 + a[1]), px(cx * 16 + b[0]), pz(cz * 16 + b[1])],
                    fill=col, width=3 if col[0] == 255 else 2)
    for x in range(-660, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1820, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(11))
    L = lambda x, z, s, sz=11: dr.text((px(x), pz(z)), s, fill='black', font=F(sz), stroke_width=3, stroke_fill='white')
    nums = {}
    for i, o in enumerate(OBJ, 1):
        nums[o[0]] = i
        k, _, x0, x1, z0, z1, st = o[:7]
        L((x0 + x1) / 2 - 1, (z0 + z1) / 2 - 1, str(i), 13)
    L(-640, 1814, 'главный проспект (резерв: метро 1 + коллектор)', 10)
    L(-626, 1830, 'Заводская', 10); L(-652, 1850.5, 'Береговой', 10); L(-650, 1885.5, 'Промышленный', 10)
    L(-663, 1846, 'набережная →', 10); L(-662, 1915, 'бухта', 11)

    # вид с юга
    ex0, ey0 = ML, MT + mh + 40
    ey = lambda y: ey0 + (120 - y) * 4
    dr.text((ex0, ey0 - 26), 'Вид с юга (запад → восток), 1 блок = 7 px по X, 4 px по высоте', fill='black', font=F(12, True))
    for yy in range(60, 121, 10):
        dr.line([ex0, ey(yy), ex0 + mw, ey(yy)], fill=(225, 225, 225), width=1)
        dr.text((ex0 + mw + 4, ey(yy) - 6), str(yy), fill='black', font=F(9))
    dr.rectangle([ex0, ey(WALK), ex0 + mw, ey(60)], fill=(205, 190, 150))
    order = sorted(OBJ, key=lambda o: o[4] + o[5])        # сначала дальние (север), ближние (юг) — поверх
    for o in order:
        k, _, x0, x1, z0, z1, st, ytop, fill, _ = o
        if k in ('ct1', 'ct2'):
            cx = (x0 + x1 + 1) / 2
            pts = []
            for yy in range(67, ytop + 1):
                t = (yy - 67) / (ytop - 67)
                r = 6.5 - 2.3 * math.sin(min(t / 0.75, 1) * math.pi / 2) + (0.6 * (t - 0.75) / 0.25 if t > 0.75 else 0)
                pts.append((yy, r))
            poly = [(px(cx - r), ey(yy)) for yy, r in pts] + [(px(cx + r), ey(yy)) for yy, r in reversed(pts)]
            dr.polygon(poly, fill=fill + (255,), outline=(90, 90, 90))
        elif k == 'wind':
            for i in range(1):
                xm = px(-597)
                dr.line([xm, ey(WALK), xm, ey(ytop)], fill=(90, 90, 90), width=3)
                for a in (90, 210, 330):
                    dr.line([xm, ey(ytop), xm + 30 * math.cos(math.radians(a)), ey(ytop) - 30 * math.sin(math.radians(a))],
                            fill=(60, 60, 60), width=2)
        else:
            dr.rectangle([px(x0), ey(ytop), px(x1 + 1), ey(WALK)], fill=fill + (255,), outline=(70, 70, 70))
            if k in ('ore', 'prod'):
                for x in range(x0, x1, 4):
                    dr.polygon([(px(x), ey(ytop)), (px(x + 3), ey(ytop + 3)), (px(x + 3), ey(ytop))], fill=fill, outline=(70, 70, 70))
            if k == 'npp':
                for cx in (-614.5, -600.5):
                    dr.pieslice([px(cx - 6), ey(ytop + 7), px(cx + 6), ey(ytop - 7)], 180, 360, fill=(225, 225, 230), outline=(70, 70, 70))
                dr.rectangle([px(STACK[0] - 1), ey(115), px(STACK[0] + 2), ey(ytop)], fill=(230, 230, 230), outline=(70, 70, 70))
                for yy in (111, 105): dr.rectangle([px(STACK[0] - 1), ey(yy + 2), px(STACK[0] + 2), ey(yy)], fill=(200, 40, 40))
            if k == 'disp':
                dr.line([px(-615.5), ey(ytop), px(-615.5), ey(106)], fill=(60, 60, 60), width=2)
                dr.ellipse([px(-617.5), ey(94), px(-613.5), ey(90)], fill='white', outline='black')
        dr.text((px((x0 + x1) / 2) - 4, ey(ytop) - 14), str(nums[k]), fill='black', font=F(11, True), stroke_width=2, stroke_fill='white')
    dr.text((px(-660), ey(WALK) + 4), f'площадка — ходим {WALK}', fill='black', font=F(10))

    # легенда
    lx = ML + mw + 34
    dr.text((lx, 10), 'ПРОМЗОНА — план v1', fill='black', font=F(17, True))
    y = 40
    lines = [('Этапы: красный — 1, синий — 2, зелёный — 3', True)]
    for i, o in enumerate(OBJ, 1):
        lines.append((f'{i}. {o[1]} (этап {o[6]}, верх Y {o[7]})', False))
    lines += [('', False),
              ('Площадка: ходим 67.0 (верх мощения Y 66)', False),
              ('Проезды по 6 бл.: Заводская X −627…−622, Береговой', False),
              ('  Z 1850…1855 (стык с улицей набережной), Промыш-', False),
              ('  ленный Z 1885…1890; пандусы 65.0 → 67.0 по 0.5', False),
              ('Оранжевый пунктир — техгалереи под проездами', False),
              ('  (пол Y 60, высота 3: кабели IC2, МЭ, трубы, проход)', False),
              ('  коллектор: Подстанция → Промышленный → Заводская', False),
              ('  → резерв под проспектом (X ≈ −625)', False),
              ('Залы АЭС: сев. — обычные реакторы, юж. — жидкостные', False),
              ('  (купола-гермооболочки), красный — вент. труба', False),
              ('Жёлтый — загрузчик (−617, 1879), чанк (−39, 117)', False),
              ('Тёмные контуры — 25 рабочих чанков', False),
              ('Коричн. пунктир — цех булыжника, чанк (−39, 115),', False),
              ('  глубина Y 14…20 (замкнутая коробка)', False),
              ('Лиловая штриховка — пустоты каньона с кровлей', False),
              ('  тоньше 7 бл. (верх ≥ Y 55): закладка камнем', False),
              ('Порт — после решения владельца (берег бухты', False),
              ('  у чанков (−41, 119/120), вне 25 чанков)', False)]
    for t, b in lines:
        dr.text((lx, y), t, fill='black', font=F(12, b)); y += 18
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    img.save(args.out)
    print('картинка:', os.path.relpath(args.out, REPO))


if __name__ == '__main__':
    main()
