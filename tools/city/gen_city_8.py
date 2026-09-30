"""Сити, этап 8 — воздушные шары и вертолёт (замечания владельца после постройки этапов 5–6):
шар над «Вершиной» (Y 167…187) почти не виден — башни загораживают; вертолёт мелковат.

- city-8-fix-1.json — снять старый шар над «Вершиной» и старый вертолёт (воздух по их клеткам) и
  поставить вертолёт вдвое больше рядом с площадкой на «Воротах» (корпус 10×5×5, несущий винт 21 бл.);
- city-8-balloons.json — четыре шара, вдвое крупнее прежнего, пониже и не в высокой застройке
  (корзина с горелкой, стропы, мешки-балласт на цепях; оболочка полая):
    «Классика» — полосатый шар Ø 15 над Площадью Сити (между «Открывашкой» и «Воротами», низ ≈ Y 88);
    «Сова», «Кит» — над бухтой южнее набережной; «Лягушка» — над Старым городом.
  Фигурные шары — свои персонажи (не мобы игры): оболочка-«голова» с глазами, клювом/улыбкой.

Запуск: gen_city_8.py [--outdir schemas] [--preview docs/districts/city-8-preview.png]
Мир — World() (после постройки — built_before('city-8-fix-1.json')).
Проверки: опоры/порядок (decor_lib), шары и вертолёт не задевают построенное (зазор ≥ 2), видимость —
сколько точек обзора на улицах, набережной и площадях видят каждый шар (луч до 5 точек шара),
негатив (шар в башне — пересечение найдено).
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import *  # noqa: E402,F401,F403
import plan_city_v1 as P  # noqa: E402

NAMES = ['city-8-fix-1.json', 'city-8-balloons.json']
N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'city-8-preview.png'))
    return p.parse_args()


def shell(vol):
    return {p for p in vol if any((p[0] + a, p[1] + b, p[2] + c) not in vol for a, b, c in N6)}


def gondola(c, cx, y_top, cz):
    """Корзина под оболочкой: стропы-забор 3 бл., горелка, корзина 5×5 тёмного дуба, мешки на цепях."""
    for a in (-2, 2):
        for b in (-2, 2):
            for y in range(y_top - 3, y_top): c[(cx + a, y, cz + b)] = 'dark_oak_fence'
    c[(cx, y_top - 1, cz)] = 'sea_lantern'; c[(cx, y_top - 2, cz)] = 'stained_glass:1'
    yb = y_top - 4
    for a in range(-2, 3):
        for b in range(-2, 3):
            c[(cx + a, yb, cz + b)] = 'planks:5'
            if abs(a) == 2 or abs(b) == 2: c[(cx + a, yb + 1, cz + b)] = 'dark_oak_fence'
    for a, b in ((-2, -2), (2, 2), (-2, 2), (2, -2)):
        c[(cx + a, yb - 1, cz + b)] = 'iron_bars'; c[(cx + a, yb - 2, cz + b)] = 'wool:12'


def rounded_box(cx, y0, cz, sx, sy, sz, cut=2):
    """Параллелепипед со скруглёнными рёбрами (срез cut на рёбрах и углах)."""
    v = set()
    hx, hz = sx // 2, sz // 2
    for x in range(-hx, sx - hx):
        for z in range(-hz, sz - hz):
            for y in range(sy):
                ex = min(x + hx, sx - hx - 1 - x); ez = min(z + hz, sz - hz - 1 - z); ey = min(y, sy - 1 - y)
                k = sum(1 for e in (ex, ey, ez) if e < cut)
                if k >= 2 and sorted((ex, ey, ez))[0] + sorted((ex, ey, ez))[1] < cut: continue
                v.add((cx + x, y0 + y, cz + z))
    return v


def classic(c, cx, y0, cz):
    """Полосатый шар Ø 15 (красная/жёлтая/белая шерсть), низ — сужение к горелке."""
    vol = set()
    for y in range(18):
        r = 7.5 * math.sqrt(max(0, 1 - ((y - 10) / 8.5) ** 2)) if y >= 4 else 2.5 + y * 0.9
        for x in range(-8, 9):
            for z in range(-8, 9):
                if math.hypot(x, z) <= r: vol.add((cx + x, y0 + y, cz + z))
    for p in shell(vol):
        sec = int((math.atan2(p[2] - cz, p[0] - cx) + math.pi) / (2 * math.pi) * 12) % 3
        c[p] = ('wool:14', 'wool:4', 'wool:0')[sec]
    gondola(c, cx, y0, cz)


def owl(c, cx, y0, cz, face):
    """«Сова»: коричневая голова 14×13×14, светлый лицевой диск, большие глаза, оранжевый клюв, «ушки»."""
    vol = rounded_box(cx, y0, cz, 14, 13, 14)
    for p in shell(vol): c[p] = 'wool:12'
    fz = cz + face * 7 if face > 0 else cz - 7
    for x in range(-5, 5):                                   # лицевой диск
        for y in range(2, 11):
            if abs(x + 0.5) + abs(y - 6) * 0.8 < 7.2: c[(cx + x, y0 + y, fz)] = 'wool:0'
    for ex in (-4, 1):                                       # глаза 3×3: жёлтые с чёрным зрачком
        for a in range(3):
            for b in range(3):
                c[(cx + ex + a, y0 + 6 + b, fz)] = 'wool:15' if (a == 1 and b == 1) or (a == 1 and b == 2) else 'wool:4'
    for a in (-1, 0):                                        # клюв, торчит на блок
        for y in (4, 5):
            c[(cx + a, y0 + y, fz)] = 'wool:1'; c[(cx + a, y0 + y, fz + face)] = 'wool:1'
    for ex in (-6, 4):                                       # ушки
        for a in range(2):
            for y in range(13, 16):
                if y < 15 or a == (0 if ex < 0 else 1): c[(cx + ex + a, y0 + y, cz + face * 2)] = 'wool:12'
    gondola(c, cx, y0, cz)


def whale(c, cx, y0, cz, face):
    """«Кит»: синее тело 18×12×12 вдоль X, белое брюхо, глаз, улыбка, фонтан из стекла, хвост."""
    vol = rounded_box(cx, y0, cz, 18, 12, 12, cut=3)
    for (x, y, z) in shell(vol): c[(x, y, z)] = 'wool:0' if y - y0 <= 3 else 'wool:11'
    fz = cz + 6 if face > 0 else cz - 7
    for x in (-6, -5): c[(cx + x, y0 + 7, fz)] = 'wool:15'            # глаз
    c[(cx - 6, y0 + 8, fz)] = 'wool:0'
    for x in range(-8, -2): c[(cx + x, y0 + 4 + (1 if x in (-8, -3) else 0), fz)] = 'wool:15'   # улыбка
    for y in range(12, 15): c[(cx - 3, y0 + y, cz)] = 'stained_glass:3'  # фонтан
    for a, b in ((-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (0, -2), (0, 2)):
        c[(cx - 3 + a, y0 + 15 - (1 if abs(a) + abs(b) == 2 else 0), cz + b)] = 'stained_glass:3'
    c[(cx - 3, y0 + 15, cz)] = 'wool:0'
    for y in range(6, 9):                                            # хвост — плавники вверх-в стороны
        for b in range(-3, 4):
            if abs(b) >= y - 5: c[(cx + 10, y0 + y, cz + b)] = 'wool:11'
    for b in range(-1, 2): c[(cx + 9, y0 + 6, cz + b)] = 'wool:11'
    gondola(c, cx, y0, cz)


def frog(c, cx, y0, cz, face):
    """«Лягушка»: зелёная голова 14×11×14, глаза-купола сверху, широкий красный рот, розовые щёки."""
    vol = rounded_box(cx, y0, cz, 14, 11, 14)
    for ex in (-5, 3):                                               # глаза-купола
        vol |= rounded_box(cx + ex, y0 + 10, cz + face * 3, 4, 4, 4, cut=1)
    for p in shell(vol): c[p] = 'wool:5'
    fz = cz + 7 if face > 0 else cz - 7
    for ex in (-5, 3):
        ez = cz + face * 3 + (2 if face > 0 else -2)
        for a in range(-1, 2):
            for y in (11, 12): c[(cx + ex + a, y0 + y, ez)] = 'wool:0'
        c[(cx + ex, y0 + 11, ez)] = 'wool:15'; c[(cx + ex, y0 + 12, ez)] = 'wool:15'
    for x in range(-5, 5): c[(cx + x, y0 + 4, fz)] = 'wool:14'          # рот
    c[(cx - 6, y0 + 5, fz)] = 'wool:14'; c[(cx + 5, y0 + 5, fz)] = 'wool:14'
    for x in (-6, 4):
        for y in (6, 7): c[(cx + x, y0 + y, fz)] = 'wool:6'; c[(cx + x + 1, y0 + y, fz)] = 'wool:6'
    gondola(c, cx, y0, cz)


BALLOONS = [('«Классика» над Площадью Сити', classic, (-755, 88, 1820), None),
            ('«Сова» над бухтой', owl, (-730, 86, 1888), -1),
            ('«Кит» над морем', whale, (-698, 84, 1905), -1),
            ('«Лягушка» над Старым городом', frog, (-690, 104, 1800), 1)]


def heli_big(cx, cy, cz):
    """Вертолёт ×2: корпус 10×5×5 (синий бетон, белая полоса), кабина — голубое стекло, хвостовая балка,
    киль, хвостовой винт, полозья на стойках, несущий винт — крест 21 бл. на мачте."""
    c = {}
    for dx in range(-5, 5):
        for dy in range(5):
            for dz in range(-2, 3):
                if (abs(dz) == 2 and dy in (0, 4)) or (dx in (-5, 4) and (abs(dz) == 2 or dy in (0, 4))): continue
                b = 'concrete:11'
                if dy == 1: b = 'concrete:0'
                if dx <= -3 and dy >= 2: b = 'stained_glass:3'
                c[(cx + dx, cy + dy, cz + dz)] = b
    for dx in range(5, 14):
        for dy in (3, 4) if dx < 9 else (3,):
            c[(cx + dx, cy + dy, cz)] = 'concrete:11'
    for dy in range(4, 8): c[(cx + 13, cy + dy, cz)] = 'concrete:11'
    for d in (-2, -1, 1, 2): c[(cx + 13, cy + 6 + d, cz + 1)] = 'concrete:7'; c[(cx + 13 + d, cy + 6, cz + 1)] = 'concrete:7'
    c[(cx + 13, cy + 6, cz + 1)] = 'concrete:15'
    for dz in (-3, 3):
        for dx in range(-5, 5): c[(cx + dx, cy - 2, cz + dz)] = 'concrete:7'
        for dx in (-3, 2): c[(cx + dx, cy - 1, cz + dz)] = 'iron_bars'
    for dy in (5, 6): c[(cx, cy + dy, cz)] = 'concrete:15'
    for d in range(-10, 11):
        c[(cx + d, cy + 7, cz)] = 'concrete:7'; c[(cx, cy + 7, cz + d)] = 'concrete:7'
    c[(cx, cy + 7, cz)] = 'concrete:15'
    return c


HELI_C = (-744, 160, 1847)


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before(NAMES[0])) if NAMES[0] in names else World()
    fix = {}
    old = set(P.HELI) | set(P.BALLOON) | {(-795, 169, 1787), (-795, 169, 1788), (-795, 170, 1787), (-795, 170, 1788)}
    for p in old:
        if W.block(*p) not in ('air',): fix[p] = 'air'
    new_h = heli_big(*HELI_C)
    fix.update(new_h)
    bal = {}
    per = {}
    for name, fn, (x, y, z), face in BALLOONS:
        cc = {}
        if face is None: fn(cc, x, y, z)
        else: fn(cc, x, y, z, face)
        per[name] = cc; bal.update(cc)
    outs = []
    for nm, cc in ((NAMES[0], fix), (NAMES[1], bal)):
        o, rel, order, dims = save_schema(cc, os.path.join(args.outdir, nm))
        outs.append((nm, cc, o, rel, order))
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(cc)}')
    print(f'снято: старый шар и вертолёт — {sum(1 for p in old if p in fix and fix[p] == "air")} бл.; новый вертолёт '
          f'{len(new_h)} бл. (прежний {len(P.HELI)}), центр {HELI_C}')
    for name, cc in per.items():
        xs = [k[0] for k in cc]; ys = [k[1] for k in cc]; zs = [k[2] for k in cc]
        print(f'  {name}: X {min(xs)}…{max(xs)}, Y {min(ys)}…{max(ys)}, Z {min(zs)}…{max(zs)} '
              f'({max(xs) - min(xs) + 1}×{max(ys) - min(ys) + 1}×{max(zs) - min(zs) + 1}), {len(cc)} бл.')
    print('== ПРОВЕРКИ ==')
    ALL = dict(fix); ALL.update(bal)

    def final(x, y, z):
        b = ALL.get((x, y, z)) or W.block(x, y, z)
        return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
    for nm, cc, o, rel, order in outs:
        def terr(x, y, z, o=o):
            b = W.block(x + o[0], y + o[1], z + o[2])
            return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
        se, wr = dl.check_supports(rel, order, terr)
        print(f'{nm}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(se)} | предупреждений {len(wr)}')
        for m in (se + wr)[:4]: print('   ', m)

    def clash(cells, gap=2):
        hit = 0
        for (x, y, z) in cells:
            for a in range(-gap, gap + 1):
                for b in range(-gap, gap + 1):
                    for d in range(-gap, gap + 1):
                        q = (x + a, y + d, z + b)
                        if q in ALL: continue
                        if W.block(*q) not in ('air', 'water'): hit += 1; break
                    else: continue
                    break
        return hit
    for name, cc in list(per.items()) + [('вертолёт', new_h)]:
        print(f'{name}: клеток ближе 2 бл. к построенному — {clash(cc)}')
    # видимость: точки обзора на уровне глаз, луч до 5 точек шара (центр и края), прозрачны стекло, вода, воздух
    VIEW = {'проспект запад (−790,1816)': (-790, 70.6, 1816), 'проспект у Старого города (−730,1816)': (-730, 69.6, 1816),
            'Площадь Сити (−750,1825)': (-750, 69.6, 1825), 'набережная (−760,1852)': (-760, 66.6, 1852),
            'набережная (−700,1854)': (-700, 66.6, 1854), 'Старый город, проспект (−700,1816)': (-700, 69.6, 1816),
            '«Вершина» (−796,1789)': (-796, 77.6, 1789), 'Пограничная (−727,1790)': (-727, 69.6, 1790)}
    clear_b = lambda b: b in ('air', 'water') or b.startswith(('glass', 'stained_glass', 'iron_bars', 'dark_oak_fence', 'leaves'))

    def sees(v, t, own):
        dx, dy, dz = t[0] - v[0], t[1] - v[1], t[2] - v[2]
        n = int(max(abs(dx), abs(dy), abs(dz)) * 2) + 1
        for i in range(1, n):
            p = (math.floor(v[0] + dx * i / n + 0.5), math.floor(v[1] + dy * i / n), math.floor(v[2] + dz * i / n + 0.5))
            if p in own: return True
            if not clear_b(final(*p)): return False
        return True
    print('видимость (точек обзора из 8, откуда виден шар):')
    for name, cc in per.items():
        xs = [k[0] for k in cc]; ys = [k[1] for k in cc]; zs = [k[2] for k in cc]
        cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2 + 3, (min(zs) + max(zs)) / 2
        pts = [(cx, cy, cz), (min(xs), cy, cz), (max(xs), cy, cz), (cx, cy, min(zs)), (cx, cy, max(zs))]
        seen = [k for k, v in VIEW.items() if any(sees(v, t, set(cc)) for t in pts)]
        print(f'  {name}: {len(seen)} — {", ".join(seen)}')
    # старый шар — для сравнения
    old_b = set(P.BALLOON)
    seen_old = [k for k, v in VIEW.items() if any(sees(v, t, old_b) for t in ((-795, 180, 1787.5), (-800, 180, 1787.5), (-790, 180, 1787.5)))]
    print(f'  (прежний шар над «Вершиной» до снятия: {len(seen_old)})')
    neg = {(x, y, z) for (x, y, z) in rounded_box(-758, 150, 1803, 6, 6, 6)}
    print('НЕГАТИВ: шар внутри «Открывашки» — пересечение с построенным найдено:', clash(neg, 0) > 0)
    if args.preview: preview(args.preview, final)


def preview(path, final):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    WOOL = {0: (240, 240, 240), 1: (235, 125, 40), 4: (245, 205, 50), 5: (120, 190, 40), 6: (240, 150, 170), 11: (50, 70, 170),
            12: (110, 75, 45), 14: (190, 45, 40), 15: (25, 25, 25)}
    CX = dict(CL); CX.update({'concrete:0': (235, 235, 235), 'concrete:7': (70, 75, 80), 'concrete:11': (40, 60, 150),
                              'concrete:15': (25, 25, 25), 'stained_glass:3': (150, 200, 235), 'planks:5': (70, 45, 25)})

    def cc(b):
        n, m = (b.split(':') + ['0'])[:2]
        if n == 'wool': return WOOL.get(int(m), (200, 200, 200))
        return CX.get(b) or CX.get(n) or col(b)
    S = 4
    X0, X1, Y0, Y1 = -806, -670, 60, 195
    img = Image.new('RGB', ((X1 - X0 + 1) * S + 40, (Y1 - Y0 + 1) * S + 40), (225, 238, 250))
    dr = ImageDraw.Draw(img)
    dr.text((10, 4), 'Сити: шары и вертолёт — вид с моря (с юга); ближнее — поверх', fill='black', font=F(12))
    for x in range(X0, X1 + 1):
        for y in range(Y0, Y1 + 1):
            for z in range(1930, 1770, -1):
                b = final(x, y, z)
                if b in ('air', 'water'): continue
                c = (175, 170, 150) if b in ('stone', 'grass', 'dirt', 'sand') else cc(b)
                dr.rectangle([20 + (x - X0) * S, 30 + (Y1 - y) * S, 20 + (x - X0 + 1) * S - 1, 30 + (Y1 - y + 1) * S - 1], fill=c)
                break
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
