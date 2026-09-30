"""План района «Парк + зоопарк» v2 — как построено (CITY.md §7.5): вид сверху по модели мира (все схемы
BUILT, включая park-1-ground, park-1-build, park-2-zoo), подписи объектов, незакрытые пункты
(вестибюль метро «Парк», подъём Горной дороги на гору F) и ручные правки владельца.
Запуск: plan_park_v2.py [--out docs/districts/park-plan-v2.png]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, BUILT, REPO  # noqa: E402
from oldtown_lib import col  # noqa: E402

X0, X1, Z0, Z1 = -668, -618, 1740, 1824
S = 12
CX = {'water': (70, 130, 215), 'grass': (110, 165, 70), 'sandstone:2': (225, 212, 160), 'stone_slab:1': (220, 208, 158),
      'quartz_block': (240, 238, 232), 'quartz_stairs': (235, 232, 225), 'snow': (245, 250, 250), 'packed_ice': (160, 190, 240),
      'dirt:1': (130, 95, 65), 'stone:5': (130, 130, 130), 'glass': (200, 230, 240), 'stained_glass:5': (130, 200, 80),
      'brick_stairs': (150, 70, 60), 'leaves:4': (60, 120, 40), 'leaves:6': (110, 150, 60), 'leaves:5': (40, 80, 50),
      'leaves:7': (60, 140, 40), 'planks:5': (70, 50, 30), 'wooden_slab:5': (80, 58, 35), 'red_flower': (220, 60, 90),
      'stained_hardened_clay:14': (150, 60, 50), 'stained_hardened_clay:4': (190, 140, 40), 'concrete:0': (235, 235, 235),
      'dirt:2': (90, 65, 40), 'fence': (150, 120, 80), 'spruce_fence': (90, 65, 40)}
LABELS = [(-660, 1742, 'Парковая ул.'), (-654, 1771, 'Горная дорога → гора F'), (-652, 1815, 'главный проспект → промзона'),
          (-652, 1786, 'озеро'), (-649, 1779, 'ротонда'), (-640, 1779, 'сцена'), (-634, 1790, 'Зелёный\nтеатр'),
          (-656, 1790, 'ворота'), (-652, 1797, 'лодки'), (-644, 1799, 'кафе'), (-655, 1806, 'площадка'), (-635, 1805, 'розарий'),
          (-655, 1747, 'медведи'), (-655, 1760, 'волки'), (-645, 1744, 'тропич. купол'), (-645, 1763, 'амбар'),
          (-641, 1757, 'загон'), (-632, 1744, 'ламы'), (-651, 1766, 'касса')]
OPEN = [('M', -643, -640, 1809, 1812, 'вестибюль метро «Парк» — со схемой тоннеля'),
        ('F', -628, -625, 1769, 1773, 'подъём Горной дороги на гору F — район 7')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'park-plan-v2.png'))
    a = ap.parse_args()
    W = World(BUILT)
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 60 + 420, mh + 50), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 40 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 120
            while y > 30 and W.block(x, y, z) in ('air', 'plant'): y -= 1
            b = W.block(x, y, z)
            if b == 'ground':
                k = (max(60, min(y, 90)) - 60) / 30; c = (int(200 - 60 * k), int(215 - 40 * k), int(145 - 50 * k))
            else: c = CX.get(b) or CX.get(b.split(':')[0]) or col(b)
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    for x in range(-660, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(10))
    for z in range(1750, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    dr.rectangle([px(-660), pz(1745), px(-624) - 1, pz(1813) - 1], outline=(0, 0, 0), width=2)
    for tag, x0, x1, z0, z1, _ in OPEN:
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], outline=(150, 40, 170), width=3)
        dr.text((px(x0) + 3, pz(z0) + 2), tag, fill=(150, 40, 170), font=F(12))
    for x, z, t in LABELS:
        dr.text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    lx = mw + 60
    dr.text((lx, 12), 'ПАРК + ЗООПАРК — план v2 (построено)', fill='black', font=F(16))
    notes = ['Этап 1 — парк (park-1-ground, park-1-build),', 'этап 2 — зоопарк (park-2-zoo) построены.', '',
             'Вручную владелец: камыш, кувшинки, лодки', 'на озере; животные в вольерах', '(в модели мира их нет).', '',
             'Щитовые 3×3 с шахтой: кафе (парк),', 'амбар (зоопарк).', '',
             'Не закрыто (фиолетовое):'] + [f' {t}: {d}' for t, *_, d in OPEN] + \
            ['', 'Чёрная рамка — район', 'X −660…−625, Z 1745…1812.']
    for i, t in enumerate(notes): dr.text((lx, 44 + i * 19), t, fill='black', font=F(12))
    img.save(a.out); print('план', a.out, img.size, '| построенных схем:', len(BUILT))


if __name__ == '__main__':
    main()
