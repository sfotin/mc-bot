"""План района «Гора F» v2 — как построено (CITY.md §7.7, редакция 2): вид сверху по модели мира (все схемы
BUILT, включая mount-2-demolish, mount-2-track, mount-2-start, mount-2-fix-1; рельеф вне участка —
docs/terrain/mount.json), разрез по южной прямой (Z 1738), подписи, незакрытые пункты.
Запуск: plan_mount_v2.py [--out docs/districts/mount-plan-v2.png]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, BUILT, REPO  # noqa: E402
from oldtown_lib import col  # noqa: E402

X0, X1, Z0, Z1 = -664, -530, 1638, 1778
S = 6
CX = {'grass': (110, 165, 70), 'sandstone:2': (225, 212, 160), 'stone_slab:1': (220, 208, 158), 'quartz_block': (240, 238, 232),
      'sandstone_stairs': (215, 200, 150), 'glass_pane': (160, 205, 235), 'packed_ice': (150, 190, 245), 'concrete:0': (245, 245, 245),
      'concrete:14': (200, 40, 40), 'snow': (252, 252, 255), 'wool:15': (30, 30, 30), 'sea_lantern': (205, 235, 235),
      'stonebrick': (125, 125, 125), 'stone_slab:5': (140, 140, 140), 'spruce_fence': (100, 70, 40), 'double_stone_slab': (170, 170, 170),
      'quartz_block:2': (245, 243, 236), 'stone_slab:15': (236, 234, 228), 'leaves:4': (60, 120, 40), 'leaves:6': (110, 150, 60)}
LABELS = [(-640, 1700, 'ВИАДУК'), (-600, 1693, 'шпилька'), (-543, 1676, 'ТОННЕЛЬ'), (-575, 1688, 'ущелье'),
          (-620, 1731, 'тоннель под\nвершиной'), (-590, 1750, 'СТАРТ'), (-606, 1751, 'трибуна'), (-606, 1768, 'Горная\nплощадь'),
          (-662, 1758, 'зоопарк'), (-620, 1777, 'холм E →')]
OPEN = [('L', -626, -624, 1766, 1773, 'Горная дорога кончается у X −625 (подъём на гору снят: на седловину ведёт Северная лестница холма E)')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'mount-plan-v2.png'))
    a = ap.parse_args()
    W = World(BUILT, ext=True)
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    E = 3
    img = Image.new('RGB', (mw + 460, mh + 50 + 200), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 40 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    cc = lambda b: CX.get(b) or CX.get(b.split(':')[0]) or col(b)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 125
            while y > 30 and W.block(x, y, z) in ('air', 'plant'): y -= 1
            b = W.block(x, y, z)
            if b == 'ground':
                k = (max(60, min(y, 118)) - 60) / 58; c = (int(200 - 70 * k), int(215 - 45 * k), int(145 - 55 * k))
            elif b == 'water': c = (90, 140, 210)
            else: c = cc(b)
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    for x in range(-660, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(10))
    for z in range(1640, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    dr.rectangle([px(-624), pz(1728), px(-592) - 1, pz(1776) - 1], outline=(0, 0, 0), width=2)
    for tag, x0, x1, z0, z1, _ in OPEN:
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], outline=(150, 40, 170), width=3)
        dr.text((px(x0) - 10, pz(z0) - 12), tag, fill=(150, 40, 170), font=F(12))
    for x, z, t in LABELS:
        dr.text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    lx = mw + 60
    dr.text((lx, 12), 'ГОРА F — план v2 (построено)', fill='black', font=F(16))
    notes = ['mount-2-demolish, mount-2-track, mount-2-start,', 'mount-2-fix-1 построены (этап 1 снесён).', '',
             'Ледовая трасса для лодок: круг 470 бл.,', 'лёд Y 90, повороты с поребриками и', 'зонами вылета; ущелья, тоннели под',
             'вершиной и сквозь восточный массив,', 'виадук над низиной к северу от зоопарка.', '',
             'Старт: арка, павильон с калиткой на лёд,', 'трибуна 7 рядов; лестница 3 бл.', 'с Горной площади (79.0) и площадка.',
             'Горная площадь — стык с Башенной', 'площадью холма E.', 'Вне 25 чанков загрузчика — только декор.', '',
             'Не закрыто (фиолетовое):'] + [f' {t}: {d[:40]}' for t, *_, d in OPEN] + [f'   {d[40:]}' for *_, d in OPEN] + \
            ['', 'Чёрная рамка — район X −624…−593,', 'Z 1728…1775; трасса выходит за неё', 'на север и восток (mount.json).']
    for i, t in enumerate(notes): dr.text((lx, 40 + i * 17), t, fill='black', font=F(11))
    # разрез по южной прямой Z 1738 (запад → восток)
    ey0 = mh + 60
    base = ey0 + 180
    dr.text((40, ey0 - 18), 'Разрез по южной прямой Z 1738 (запад → восток), Y ×3: тоннель под вершиной, старт', fill='black', font=F(12))
    for x in range(X0, X1 + 1):
        for y in range(60, 120):
            b = W.block(x, y, 1738)
            if b in ('air', 'plant'): continue
            c = (150, 140, 110) if b == 'ground' else cc(b)
            dr.rectangle([px(x), base - (y - 59) * E, px(x + 1) - 1, base - (y - 60) * E - 1], fill=c)
    for yy in range(60, 120, 10): dr.text((px(X1) + 8, base - (yy - 60) * E - 6), str(yy), fill='black', font=F(9))
    img.save(a.out); print('план', a.out, img.size, '| построенных схем:', len(BUILT))


if __name__ == '__main__':
    main()
