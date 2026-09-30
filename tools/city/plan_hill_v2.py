"""План района «Холм E» v2 — как построено (CITY.md §7.6): вид сверху по модели мира (все схемы BUILT,
включая hill-1-ground, hill-1-tower, hill-1-fix-1), вид с юга 1:1, подписи объектов, незакрытые пункты
(подъём Горной дороги на гору F, продолжение проспекта к промзоне).
Запуск: plan_hill_v2.py [--out docs/districts/hill-plan-v2.png]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, BUILT, REPO  # noqa: E402
from oldtown_lib import col  # noqa: E402

X0, X1, Z0, Z1 = -630, -593, 1764, 1826
S = 12
CX = {'grass': (110, 165, 70), 'sandstone:2': (225, 212, 160), 'stone_slab:1': (220, 208, 158), 'quartz_block': (240, 238, 232),
      'quartz_stairs': (235, 232, 225), 'sandstone_stairs': (215, 200, 150), 'glass': (170, 215, 240), 'glass_pane': (170, 215, 240),
      'concrete:0': (238, 238, 238), 'concrete:14': (180, 40, 40), 'concrete:7': (90, 90, 90), 'glowstone': (250, 220, 90),
      'sea_lantern': (205, 235, 235), 'leaves:4': (60, 120, 40), 'leaves:6': (110, 150, 60), 'red_flower': (220, 60, 90),
      'stonebrick': (130, 130, 130), 'double_stone_slab': (170, 170, 170), 'stone_slab:5': (125, 125, 125)}
LABELS = [(-629, 1771, 'Горная дорога'), (-623, 1776, 'Северная лестница'), (-624, 1788, 'смотровая\n«Над парком»'),
          (-612, 1790, 'ТЕЛЕБАШНЯ'), (-611, 1800, 'Башенная площадь'), (-613, 1809, 'Парадная\nлестница'),
          (-629, 1816, 'главный проспект → промзона'), (-630, 1790, 'театр')]
OPEN = [('F', -624, -593, 1769, 1773, 'подъём Горной дороги на гору F — район 7'),
        ('P', -596, -593, 1813, 1820, 'проспект дальше к промзоне — район 9 (покрытие 66.5/67.0)')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'hill-plan-v2.png'))
    a = ap.parse_args()
    W = World(BUILT)
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    E = 4
    ew, eh = (X1 - X0 + 1) * E, (192 - 58) * E
    img = Image.new('RGB', (mw + 60 + max(ew + 60, 440), max(mh + 50, 330 + eh + 40)), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 40 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    cc = lambda b: CX.get(b) or CX.get(b.split(':')[0]) or col(b)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 84                                        # по высоте человека: видно площадь и вестибюль под башней
            while y > 30 and W.block(x, y, z) in ('air', 'plant'): y -= 1
            b = W.block(x, y, z)
            if b == 'ground':
                k = (max(60, min(y, 90)) - 60) / 30; c = (int(200 - 60 * k), int(215 - 40 * k), int(145 - 50 * k))
            else: c = cc(b)
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    for x in range(-630, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(10))
    for z in range(1770, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    dr.rectangle([px(-624), pz(1773), px(-592) - 1, pz(1821) - 1], outline=(0, 0, 0), width=2)
    for tag, x0, x1, z0, z1, _ in OPEN:
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], outline=(150, 40, 170), width=3)
        dr.text((px(x0) + 3, pz(z0) + 2), tag, fill=(150, 40, 170), font=F(12))
    for x, z, t in LABELS:
        dr.text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    lx = mw + 60
    dr.text((lx, 12), 'ХОЛМ E — план v2 (построено)', fill='black', font=F(16))
    notes = ['hill-1-ground, hill-1-tower, hill-1-fix-1 построены.', '',
             'Телебашня (ostankino.json), вестибюль со щитовой,', 'стремянка в стволе с площадками, свет в стволе,',
             'стеклянная «тарелка» r 9.5 (Y 136…141), кафе.', 'Площадь 79.0, смотровая «Над парком»,',
             'Северная и Парадная лестницы, проспект до X −593.', 'Вне 25 чанков загрузчика — только декор.', '',
             'Не закрыто (фиолетовое):'] + [f' {t}: {d}' for t, *_, d in OPEN] + ['', 'Чёрная рамка — район X −624…−593, Z 1773…1820.']
    for i, t in enumerate(notes): dr.text((lx, 40 + i * 18), t, fill='black', font=F(11))
    # вид с юга 1:1 по Z 1790
    ex0, ey0 = lx, 330
    base = ey0 + eh
    dr.text((ex0, ey0 - 20), 'Вид с юга, разрез Z 1790, масштаб 1:1', fill='black', font=F(12))
    for x in range(X0, X1 + 1):
        for y in range(58, 192):
            b = W.block(x, y, 1790)
            if b in ('air', 'plant'): continue
            c = (150, 140, 110) if b == 'ground' else cc(b)
            dr.rectangle([ex0 + (x - X0) * E, base - (y - 57) * E, ex0 + (x - X0 + 1) * E - 1, base - (y - 58) * E - 1], fill=c)
    for yy in range(60, 192, 20): dr.text((ex0 + ew + 4, base - (yy - 58) * E - 6), str(yy), fill='black', font=F(9))
    img.save(a.out); print('план', a.out, img.size, '| построенных схем:', len(BUILT))


if __name__ == '__main__':
    main()
