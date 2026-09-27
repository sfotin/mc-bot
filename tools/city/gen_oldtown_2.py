"""Старый город, этап 2: проспекты и переулки (CITY.md §7.3).

- проспект С–Ю X −692…−688 (Z 1780…1847) и главный проспект Z 1814…1818
  (X −724…−661): середина — каменный кирпич, края — гладкий камень;
- переулки 3 бл. (Z 1789…1791, 1839…1841 на западе; Z 1793…1795, 1836…1838
  на востоке): булыжник с мшистым (≈15 %, без периодичности);
- высота покрытия идёт по сглаженному рельефу, перепад между соседними
  клетками не больше полублока (полублоки вместо полных ступеней); на юге —
  вровень с площадью набережной (верх Y 65);
- обочины 2 бл.: грунт подтягивается к покрытию откосом не круче 1:1;
- фонари DECOR §3.2а на краях проспектов через 8 блоков, парами;
- скамейки — не в этом этапе (площади и променад, этапы 3–7).

Запуск: gen_oldtown_2.py [--out schemas/oldtown-2-streets.json]
                         [--preview docs/districts/oldtown-2-preview.png]
Мир — tools/city/world_model.py (в BUILT уже есть oldtown-1).
Проверки: опоры + вода + порядок (decor_lib), вода рельефа не открыта в
воздух, проходимость без прыжков (walk_reachable) от площади набережной до
каждой клетки улиц и концов улиц, перепад покрытия <= 0.5, резерв трасс,
кровля каньона; негативные прогоны.
"""
import argparse
import os
import sys
from collections import Counter, deque

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

AV = [('av_ns', -692, -688, 1780, 1847, 'x'), ('av_ew', -724, -661, 1814, 1818, 'z')]   # ось поперёк: x — края по X
LANES = [('l1', -724, -693, 1789, 1791), ('l2', -724, -693, 1839, 1841),
         ('l3', -687, -661, 1793, 1795), ('l4', -687, -661, 1836, 1838)]
ANCHOR_H = 65.0            # верх площади набережной (Z 1848)
LAMP_STEP = 8
ROOF_MIN = 3
RESERVE_Y = 60


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'oldtown-2-streets.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-2-preview.png'))
    return p.parse_args()


def h32(x, z, k=0):
    v = (x * 73856093 ^ z * 19349663 ^ k * 83492791 ^ 0x2F1A) & 0xffffffff
    v = (v ^ (v >> 13)) * 0x5bd1e995 & 0xffffffff
    return (v ^ (v >> 15)) / 0xffffffff


def plan_network():
    role = {}
    for _, x0, x1, z0, z1 in LANES:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1): role[(x, z)] = 'lane'
    for _, x0, x1, z0, z1, ax in AV:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                edge = (x in (x0, x1)) if ax == 'x' else (z in (z0, z1))
                prev = role.get((x, z))
                if prev in ('av_mid',) or (prev == 'av_edge' and not edge): role[(x, z)] = 'av_mid'
                elif prev == 'av_edge' and edge: role[(x, z)] = 'av_mid'   # край на перекрёстке — середина
                else: role[(x, z)] = 'av_edge' if edge else 'av_mid'
    # на перекрёстке проспектов края — внутри другого проспекта: середина
    for (x, z) in list(role):
        if -692 <= x <= -688 and 1814 <= z <= 1818: role[(x, z)] = 'av_mid'
    return role


def heights(W, net, shield):
    """Верх покрытия (шаг 0.5): сглаженный рельеф, перепад соседей <= 0.5, якорь — площадь набережной."""
    def t0(x, z):
        hs = sorted(W.surf(x + a, z + b) + 1 for a in range(-2, 3) for b in range(-2, 3)
                    if (x + a, z + b) not in shield and W.block(x + a, W.surf(x + a, z + b) + 1, z + b) != 'water')
        return hs[len(hs) // 2]
    H = {c: float(t0(*c)) for c in net}
    N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for _ in range(8):
        H = {c: (H[c] * 2 + sum(H.get((c[0] + a, c[1] + b), H[c]) for a, b in N4)) / 6 for c in net}
    H = {c: round(v * 2) / 2 for c, v in H.items()}
    anchors = {c for c in net if c[1] == 1847 and -692 <= c[0] <= -688}   # соседи площади Z 1848
    d = {c: 0 for c in anchors}; q = deque(anchors)
    while q:
        c = q.popleft()
        for a, b in N4:
            n = (c[0] + a, c[1] + b)
            if n in net and n not in d: d[n] = d[c] + 1; q.append(n)
    for c in net:
        lo, hi = ANCHOR_H - 0.5 * d[c], ANCHOR_H + 0.5 * d[c]
        H[c] = min(max(H[c], lo), hi)
    # ступени — прямыми линиями поперёк улицы: в каждом сечении одна высота (медиана),
    # приоритет — проспект С–Ю, затем главный, затем переулки (их сечения у проспектов не трогаются)
    owned = set()
    streets = [(x0, x1, z0, z1, ax) for _, x0, x1, z0, z1, ax in AV] + [(x0, x1, z0, z1, 'z') for _, x0, x1, z0, z1 in LANES]
    for x0, x1, z0, z1, ax in streets:
        if ax == 'x':
            secs = [[(x, z) for x in range(x0, x1 + 1)] for z in range(z0, z1 + 1)]
        else:
            secs = [[(x, z) for z in range(z0, z1 + 1)] for x in range(x0, x1 + 1)]
        for sec in secs:
            sec = [c for c in sec if c in net and c not in owned]
            if not sec: continue
            v = sorted(H[c] for c in sec)[len(sec) // 2]
            for c in sec: H[c] = v
            owned |= set(sec)
    changed = True
    while changed:
        changed = False
        for c in net:
            m = min(H.get((c[0] + a, c[1] + b), 1e9) + 0.5 for a, b in N4)
            if H[c] > m: H[c] = m; changed = True
    return H


def build(W):
    role = plan_network()
    shield = set()   # пруды, набережные (этап 1), построенное — не трогать
    for (x, y, z), b in W.pre.items():
        if 1776 <= z <= 1848 and -730 <= x <= -655: shield.add((x, z))
    built_cols = {(x, z) for (x, y, z), b in W.pre.items() if b not in ('air',) and y >= 60
                  and W.surf(x, z) == y and b not in ('grass', 'stone', 'sand')}
    shield = {c for c in shield if c in built_cols}          # только клетки с постройкой сверху (набережные, площадь)
    net = {c for c in role if c not in shield}
    H = heights(W, net, shield)
    cells = {}

    def put(x, y, z, b): cells[(x, y, z)] = b

    def plant_top(x, z):
        y = W.surf(x, z) + 1
        while W.block(x, y, z) == 'plant': y += 1
        return y - 1

    lamps = set()
    for name, x0, x1, z0, z1, ax in AV:
        if ax == 'x':
            for z in range(z0 + 4, z1 + 1, LAMP_STEP):
                for x in (x0, x1): lamps.add((x, z))
        else:
            for x in range(x0 + 4, x1 + 1, LAMP_STEP):
                for z in (z0, z1): lamps.add((x, z))
    # не у перекрёстков и выходов переулков (±2), не в проезде: только на краях
    lamps = {c for c in lamps if role.get(c) == 'av_edge' and c in net and
             not any(role.get((c[0] + a, c[1] + b)) in ('lane',) or
                     (role.get((c[0] + a, c[1] + b)) == 'av_mid' and -692 <= c[0] + a <= -688 and 1814 <= c[1] + b <= 1818)
                     for a in range(-2, 3) for b in range(-2, 3))}

    MAT = {'av_mid': ('stonebrick', 'stone_slab:5'), 'av_edge': ('double_stone_slab', 'stone_slab'),
           'lane': ('cobblestone', 'stone_slab:3')}
    for (x, z) in net:
        h = H[(x, z)]; k = int(h) if h == int(h) else int(h)   # целая часть
        full, slab = MAT[role[(x, z)]]
        if role[(x, z)] == 'lane' and h32(x, z) < 0.15: full = 'mossy_cobblestone'
        if role[(x, z)] == 'av_mid' and h32(x, z, 7) < 0.08: full = 'stonebrick:2'   # трещины — старая мостовая
        g = W.surf(x, z)
        if h == int(h) or (x, z) in lamps:
            top_y = int(h) - 1 if h == int(h) else int(h)          # блок покрытия
            if (x, z) in lamps and h != int(h): full = full        # под фонарём — полный блок на полблока выше
            for y in range(g + 1, top_y): put(x, y, z, 'stone')
            put(x, top_y, z, full); surf_y = top_y
        else:
            k = int(h)                                             # полублок на Y k, под ним полный блок
            for y in range(g + 1, k - 1): put(x, y, z, 'stone')
            put(x, k - 1, z, full); put(x, k, z, slab); surf_y = k
        for y in range(surf_y + 1, max(plant_top(x, z), g) + 1): put(x, y, z, 'air')
        if (x, z) in lamps:
            for i, b in enumerate(('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')):
                put(x, surf_y + 1 + i, z, b)
    # обочины: кольца 1..2 вокруг сети, грунт в [уровень − d, уровень + d] (уровень — верх покрытия, блоками)
    N8 = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]
    SH = {}
    for (x, z) in net:
        for a in range(-2, 3):
            for b in range(-2, 3):
                c = (x + a, z + b)
                if c in net or c in shield: continue
                dd = max(abs(a), abs(b)); lvl = H[(x, z)] - 1   # блок, на котором стоишь, Y
                lo, hi = SH.get(c, (-1e9, 1e9))
                SH[c] = (max(lo, lvl - dd), min(hi, lvl + dd))
    SHO = 0
    for c, (lo, hi) in SH.items():
        x, z = c
        if not (-730 <= x <= -655 and 1776 <= z <= 1848): continue
        g = W.surf(x, z)
        if W.block(x, g + 1, z) == 'water' or W.water(x, z) is not None and W.water(x, z) > g and (x, z) not in {k[::2] for k in W.pre}:
            continue
        lo_i, hi_i = int(-(-lo // 1)), int(hi // 1)          # ceil(lo), floor(hi)
        if lo_i > hi_i: hi_i = lo_i
        if g > hi_i:
            for y in range(hi_i + 1, max(plant_top(x, z), g) + 1): put(x, y, z, 'air')
            put(x, hi_i, z, 'grass'); SHO += 1
        elif g < lo_i:
            for y in range(g + 1, lo_i): put(x, y, z, 'stone')
            put(x, lo_i, z, 'grass')
            for y in range(lo_i + 1, plant_top(x, z) + 1): put(x, y, z, 'air')
            SHO += 1
    return cells, net, H, role, lamps, SHO


def main():
    args = parse_args()
    W = World()
    cells, net, H, role, lamps, SHO = build(W)
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, '| габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, '| записей', len(cells))
    print('клеток улиц', len(net), '| фонарей', len(lamps), '| обочин изменено', SHO,
          '| верх покрытия Y', min(H.values()), '…', max(H.values()))
    print(Counter(cells.values()).most_common(10))

    def final(x, y, z):
        b = cells.get((x, y, z)) or W.block(x, y, z)
        return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)

    def terrain_rel(x, y, z):
        b = W.block(x + ox, y + oy, z + oz)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)

    print('== ПРОВЕРКИ ==')
    errs = dl.check_water(rel, terrain_rel)
    se, wr = dl.check_supports(rel, order, terrain_rel)
    print('опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок', len(errs) + len(se), '| предупреждений', len(wr))
    for m in (errs + se)[:10]: print('  E', m)
    leak = [(x + a, y, z + c) for (x, y, z), b in cells.items() if b == 'air' for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (x + a, y, z + c) not in cells and W.block(x + a, y, z + c) == 'water']
    print('вода рельефа, открытая в воздух схемы:', len(leak), leak[:5])
    jump = [(c, n) for c in net for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1)) if n in net and abs(H[c] - H[n]) > 0.5]
    print('перепад покрытия между соседями > 0.5:', len(jump))

    def walk(fin):   # только по клеткам улиц и улице-набережной — обочины не в счёт
        f2 = lambda x, y, z: fin(x, y, z) if (x, z) in net or z >= 1848 else 'air'
        return dl.walk_reachable(f2, (-690, 65, 1850), (-726, -659), (1778, 1851), (58, 75))
    seen = walk(final)
    miss = [c for c in net if c not in lamps and not dl.reached(seen, c[0], H[c], c[1])]
    ends = {'С–Ю, север (−690,1780)': (-690, 1780), 'главный, запад (−724,1816)': (-724, 1816),
            'главный, восток (−661,1816)': (-661, 1816), 'пер. Z1790, запад': (-724, 1790), 'пер. Z1840, запад': (-724, 1840),
            'Рыночный, восток': (-661, 1794), 'Ратушная, восток': (-661, 1837)}
    print('ПРОХОДИМОСТЬ без прыжков, только по покрытию, от улицы-набережной (−690,1850): клеток улиц', len(net) - len(lamps),
          'недостижимо', len(miss), miss[:5])
    for k, (x, z) in ends.items(): print('  ', k, dl.reached(seen, x, H[(x, z)], z))
    # резерв и кровля
    low = [k for k, b in cells.items() if b != 'air' and k[1] < RESERVE_Y]
    print('резерв трасс: блоков ниже Y', RESERVE_Y, '—', len(low))
    lo = {}
    for (x, y, z) in cells: lo[(x, z)] = min(lo.get((x, z), 999), y)
    roof = [y - W.cave_top(x, z) - 1 for (x, z), y in lo.items() if W.cave_top(x, z) is not None]
    print('кровля каньона под схемой: мин.', min(roof), '(норма >=', ROOF_MIN, ')')
    dev = []
    ring1 = {(x + a, z + b) for x, z in net for a in (-1, 0, 1) for b in (-1, 0, 1)} - net
    for (x, z) in ring1:
        yy = max((y for y in range(58, 80) if final(x, y, z) not in ('air', 'water')), default=None)
        nb = [H[(x + a, z + b)] - 1 for a in (-1, 0, 1) for b in (-1, 0, 1) if (x + a, z + b) in net]
        if yy is not None and nb and W.block(x, yy + 1, z) != 'water': dev.append(max(abs(yy - v) for v in nb))
    print('обочина (1 бл.) относительно покрытия: макс. разница', max(dev), 'бл.; > 1.5 —', sum(1 for v in dev if v > 1.5))
    # негатив: ступень в полный блок поперёк проспекта С–Ю
    bad = dict(cells)
    for x in range(-692, -687):
        yy = max(y for (xx, y, zz), b in cells.items() if (xx, zz) == (x, 1830) and b != 'air')
        bad[(x, yy + 1, 1830)] = 'stonebrick'
    s2 = walk(lambda x, y, z: bad.get((x, y, z)) or final(x, y, z))
    print('НЕГАТИВ: ступень 1 блок поперёк С–Ю на Z 1830 — север недостижим:', not dl.reached(s2, -690, H[(-690, 1780)], 1780))
    if args.preview: preview(args.preview, final, W, H, net)


def preview(path, final, W, H, net):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    X0, X1, Z0, Z1 = -726, -659, 1776, 1852
    S = 8
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 40 + 600, mh + 40), 'white')
    dr = ImageDraw.Draw(img)
    COL = {'stonebrick': (120, 120, 120), 'double_stone_slab': (165, 165, 165), 'stone_slab': (175, 175, 175),
           'cobblestone': (105, 105, 100), 'mossy_cobblestone': (95, 115, 85), 'quartz_block': (240, 238, 232),
           'stone_slab:7': (240, 238, 232), 'sea_lantern': (220, 240, 240)}
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 100
            while y > 30 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            if b == 'water': c = (70, 130, 215)
            elif b in ('grass', 'stone', 'dirt'):
                k = (max(60, min(y, 68)) - 60) / 8; c = (int(200 - 70 * k), int(215 - 40 * k), int(140 - 60 * k))
            else: c = COL.get(b) or COL.get(b.split(':')[0], (185, 180, 172))
            dr.rectangle([20 + (x - X0) * S, 20 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 20 + (z - Z0 + 1) * S - 1], fill=c)
            if (x, z) in net and H[(x, z)] != int(H[(x, z)]):
                dr.line([20 + (x - X0) * S + 1, 20 + (z - Z0) * S + S - 2, 20 + (x - X0) * S + S - 2, 20 + (z - Z0) * S + 1], fill=(40, 40, 40))
    dr.text((20, 2), 'Старый город, этап 2 — вид сверху; косая черта — полублок', fill='black', font=F(12))
    bx = mw + 40; S2 = 7

    def profile(y0, label, pts, lab):
        dr.text((bx, y0 - 16), label, fill='black', font=F(12))
        for u, (x, z) in enumerate(pts):
            for y in range(60, 72):
                b = final(x, y, z)
                if b == 'air' or b == 'water' and False: continue
                if b == 'air': continue
                n = b.split(':')[0]
                c = (70, 130, 215) if b == 'water' else (95, 150, 60) if b == 'grass' else (150, 140, 110) if b == 'stone' else \
                    COL.get(b) or COL.get(n, (120, 120, 120))
                yy = y0 + (71 - y) * S2
                if n.endswith('slab') and b not in ('stone_slab:7',) and not n.startswith('double'):
                    dr.rectangle([bx + u * S2, yy + S2 // 2, bx + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
                else:
                    dr.rectangle([bx + u * S2, yy, bx + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
            if u % 8 == 0: dr.text((bx + u * S2, y0 + 12 * S2 + 2), str(lab(x, z)), fill='black', font=F(9))
    profile(40, 'профиль проспекта С–Ю по X=−690, Z 1780…1851 (Y 60…71)', [(-690, z) for z in range(1780, 1852)], lambda x, z: z)
    profile(170, 'профиль главного проспекта по Z=1816, X −724…−661', [(x, 1816) for x in range(-724, -660)], lambda x, z: x)
    profile(300, 'переулок Z=1790, X −724…−690', [(x, 1790) for x in range(-724, -689)], lambda x, z: x)
    profile(430, 'переулок Z=1840, X −724…−690', [(x, 1840) for x in range(-724, -689)], lambda x, z: x)
    profile(560, 'Ратушная ул. Z=1837, X −690…−661', [(x, 1837) for x in range(-690, -660)], lambda x, z: x)
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
