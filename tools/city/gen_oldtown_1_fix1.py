"""Старый город, исправление 1 к этапу 1 (пруды) — после постройки этапов 1 и 2.

Замечания владельца на сервере:
- из пруда не выбраться: вода Y 64, верх набережной — Y 66 (блок Y 65);
- Соборный пруд не виден: набережная на блок выше земли вокруг.

Правило: верх набережной — вровень с землёй вокруг, вода — вровень с набережной
(блок воды на той же Y, что верхний блок набережной; выход из воды — шаг 0.1).
- озеро D: земля вокруг — Y 65 (верх 66) → набережная остаётся Y 65,
  вода поднимается до Y 65 (добавляется слой воды Y 65, глубина 4);
- Соборный пруд: земля вокруг — Y 64, у главного проспекта — Y 65 →
  набережная понижается до Y 64 (верхний блок Y 65 → воздух) везде, кроме
  клеток, где рядом земля Y >= 65; вода остаётся Y 64.

Запуск: gen_oldtown_1_fix1.py [--out schemas/oldtown-1-fix-1.json]
                              [--preview docs/districts/oldtown-1-fix-1-preview.png]
Мир — World(built_before('oldtown-1-fix-1.json')): всё построенное, включая этапы 1 и 2.
Проверки: опоры + вода + порядок (decor_lib), вода рельефа не открыта в воздух,
выход из воды (доля кромки с выходом, дальность до выхода), проходимость
с кромки на землю, негативный прогон на состоянии до исправления.
"""
import argparse
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO, built_before  # noqa: E402
import gen_oldtown_1 as st1  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

WATER_Y = {'озеро D': 65, 'Соборный пруд': 64}
LAMP = ('quartz_block:1', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')
EXIT_SHARE_MIN = 0.5      # доля кромки (клетки набережной у воды) с выходом из воды
EXIT_DIST_MAX = 6         # от любой клетки воды до ближайшего выхода, блоков


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'oldtown-1-fix-1.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-1-fix-1-preview.png'))
    return p.parse_args()


def ground_y(W, x, z):
    """Верх земли/покрытия без фонарей."""
    y = W.surf(x, z)
    while W.block(x, y, z) in LAMP: y -= 1
    return y


def build(W):
    cells = {}
    ponds = []
    for name, *r in st1.PONDS:
        water = st1.pond_cells(*r); quay = st1.ring(water); out = st1.ring(water | quay)
        wy = WATER_Y[name]
        for x, z in water:
            for y in range(st1.WATER_TOP + 1, wy + 1): cells[(x, y, z)] = 'water'
        rim = {}
        for x, z in quay:
            nb = [ground_y(W, x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (x + a, z + b) in out]
            top = st1.QUAY_TOP if (nb and max(nb) >= st1.QUAY_TOP) else wy
            top = max(top, wy)
            for y in range(top + 1, st1.QUAY_TOP + 1): cells[(x, y, z)] = 'air'
            rim[(x, z)] = top
        ponds.append((name, water, quay, rim, wy))
    return cells, ponds


def exit_stats(ponds_state):
    """ponds_state: [(name, water, rim{xz:top_block_y}, water_y)] → [(name, доля, макс. дальность)]"""
    res = []
    for name, water, rim, wy in ponds_state:
        edge = [c for c in rim if any((c[0] + a, c[1] + b) in water for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
        ex = [c for c in edge if rim[c] <= wy]            # верх набережной не выше верха воды + 0.1
        far = max((min((abs(x - ex_[0]) + abs(z - ex_[1]) for ex_ in ex), default=99) for x, z in water), default=99)
        res.append((name, len(ex) / max(1, len(edge)), far))
    return res


def main():
    args = parse_args()
    W = World(built_before('oldtown-1-fix-1.json'))
    cells, ponds = build(W)
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, '| габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, '| записей', len(cells))
    print(Counter(cells.values()))
    for name, water, quay, rim, wy in ponds:
        print(f'{name}: вода до Y {wy}; набережная: {dict(Counter(rim.values()))} (верхний блок Y)')

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
    # вода: каждая клетка воды — соседи по горизонтали вода или твёрдое, снизу твёрдое/вода
    open_w = [(x, y, z) for (x, y, z), b in cells.items() if b == 'water'
              for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)) if final(x + a, y, z + c) == 'air']
    print('вода, открытая в воздух (весь мир):', len(open_w), open_w[:4])
    for name, share, far in exit_stats([(n, w, r, wy) for n, w, q, r, wy in ponds]):
        ok = share >= EXIT_SHARE_MIN and far <= EXIT_DIST_MAX
        print(f'выход из воды — {name}: доля кромки {share:.0%}, до выхода не дальше {far} бл. —', 'OK' if ok else 'ОШИБКА')
    # с кромки-выхода на землю без прыжка
    bad = 0; tot = 0
    for name, water, quay, rim, wy in ponds:
        for (x, z), t in rim.items():
            if t > wy: continue
            for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + a, z + b)
                if n in water or n in quay: continue
                tot += 1
                if abs(ground_y(W, *n) - t) > 1: bad += 1
    print('с кромки-выхода на землю: переходов', tot, ', с перепадом > 1 блока —', bad)
    before = []
    for name, water, quay, rim, wy in ponds:
        before.append((name, water, {c: st1.QUAY_TOP for c in quay}, st1.WATER_TOP))
    for name, share, far in exit_stats(before):
        print(f'НЕГАТИВ (как построено до исправления) — {name}: доля кромки {share:.0%} → ошибка:', share < EXIT_SHARE_MIN)
    if args.preview: preview(args.preview, final, ponds)


def preview(path, final, ponds):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    img = Image.new('RGB', (760, 330), 'white'); dr = ImageDraw.Draw(img); S = 9

    def col(b):
        n = b.split(':')[0]
        return {'water': (70, 130, 215), 'grass': (95, 150, 60), 'stonebrick': (110, 110, 110), 'sand': (219, 207, 163),
                'stone': (150, 140, 110)}.get(n, (170, 170, 170))

    def section(x0, y0, label, pts):
        dr.text((x0, y0 - 16), label, fill='black', font=F(12))
        for u, (x, z) in enumerate(pts):
            for y in range(59, 69):
                b = final(x, y, z)
                if b == 'air': continue
                yy = y0 + (68 - y) * S
                if b.startswith('stone_slab') or b.startswith('stone_slab'):
                    dr.rectangle([x0 + u * S, yy + S // 2, x0 + (u + 1) * S - 1, yy + S - 1], fill=col(b))
                else:
                    dr.rectangle([x0 + u * S, yy, x0 + (u + 1) * S - 1, yy + S - 1], fill=col(b))
        dr.text((x0, y0 + 10 * S + 2), f'{pts[0]} … {pts[-1]}', fill='black', font=F(10))
    section(10, 30, 'озеро D, разрез Z=1826 (вода до Y 65, выход вровень)', [(x, 1826) for x in range(-710, -687)])
    section(10, 190, 'Соборный пруд, разрез Z=1806 (набережная Y 64)', [(x, 1806) for x in range(-704, -685)])
    section(390, 30, 'озеро D, разрез X=−700', [(-700, z) for z in range(1815, 1838)])
    section(390, 190, 'Соборный пруд, разрез X=−696 (юг — у проспекта)', [(-696, z) for z in range(1796, 1820)])
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
