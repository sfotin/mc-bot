"""План района «Промзона» v2 — как построено (CITY.md §7.9): вид сверху по модели мира (все схемы BUILT,
включая industry-1-*, industry-2-*, industry-3-basement; рельеф к востоку и югу от участка —
docs/terrain/industry-voids.json), подземная часть контурами (техгалереи, цех булыжника, подвал оранжереи),
25 рабочих чанков и место загрузчика, разрезы, подписи, незакрытые пункты.
Запуск: plan_industry_v2.py [--out docs/districts/industry-plan-v2.png]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, BUILT, REPO  # noqa: E402
from oldtown_lib import col  # noqa: E402
import plan_industry_v1 as PI  # noqa: E402
from gen_industry_1 import Terrain  # noqa: E402

X0, X1, Z0, Z1 = -666, -586, 1812, 1942
S = 7
CX = {'glass': (175, 215, 235), 'stained_glass:3': (120, 175, 225), 'concrete:0': (245, 245, 245), 'concrete:8': (200, 200, 200),
      'quartz_block': (240, 238, 232), 'stonebrick': (125, 125, 125), 'sea_lantern': (205, 235, 235), 'grass': (110, 165, 70),
      'double_stone_slab': (165, 165, 165), 'stone_slab': (165, 165, 165), 'stone:6': (150, 150, 150), 'farmland:7': (110, 80, 50)}
LABELS = [(-621, 1904, 'АЭС: 4 зала'), (-620, 1926, 'градирни'), (-654, 1862, 'цех руд'), (-654, 1876, 'производство'),
          (-617, 1836, 'склад'), (-620, 1875, 'диспетч.'), (-606, 1876, 'подстанция'), (-620, 1862, 'автокрафт'),
          (-606, 1862, 'материя'), (-640, 1904, 'машинный\nзал'), (-656, 1897, 'насосная'), (-654, 1832, 'оранжерея\n(подвал)'),
          (-600, 1826, 'ветряки'), (-627, 1822, 'Заводская'), (-664, 1848, 'Береговой'), (-650, 1886, 'Промышленный')]
UNDER = [('техгалереи (Y 60…64)', (230, 120, 0), [(-627, -622, 1821, 1920), (-657, -593, 1885, 1890), (-657, -593, 1850, 1855)]),
         ('цех булыжника (Y 14…20)', (150, 70, 20), [(-625, -608, 1839, 1856)]),
         ('подвал оранжереи (Y 61…65)', (40, 140, 60), [(-656, -631, 1826, 1846)])]
OPEN = ['Не закрыто:', ' порт и водозабор из бухты — отложены владельцем', '  (вариант: чанки (−41, 119/120) вместо двух сухих);',
        ' выход коллектора из галереи Заводской (тупик Z 1821)', '  под проспект — с инженерной схемой тоннеля метро;',
        ' механизмы IC2/AE2, загрузчик чанков (−617, 67, 1879),', '  ряды воды/лавы в цехе булыжника, генераторы на',
        '  мачтах ветряков, кабели — владелец.']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'industry-plan-v2.png'))
    a = ap.parse_args()
    W = World(BUILT)
    T = Terrain(W)
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    E = 5
    secs = [('Разрез по Z 1912: машинный зал, Заводская с галереей, жидкостные залы АЭС с куполами', [(x, 1912) for x in range(-660, -588)], (52, 118)),
            ('Разрез по X −615: склад, лаз, цех булыжника (Y 14…20), Береговой, автокрафт, диспетчерская, АЭС, градирня',
             [(-615, z) for z in range(1822, 1940)], (10, 118))]
    sh = sum((y1 - y0 + 1) * E + 36 for _, _, (y0, y1) in secs)
    img = Image.new('RGB', (mw + 420, mh + 50 + sh), (250, 250, 247))
    dr = ImageDraw.Draw(img)
    blk = lambda x, y, z: W.block(x, y, z) if W.inside(x, z) else T.block(x, y, z)
    known = lambda x, z: W.inside(x, z) or T._i(x, z) is not None
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            c = (225, 225, 225)
            if known(x, z):
                for y in range(120, 40, -1):
                    b = blk(x, y, z)
                    if b in ('air', 'plant') or 'door' in b or b.endswith('pressure_plate'): continue
                    c = (120, 170, 225) if b == 'water' else (150, 180, 110) if b == 'ground' else CX.get(b, col(b))
                    k = max(0.0, min(1.0, (y - 60) / 50))
                    c = tuple(min(255, int(v * (0.8 + 0.3 * k))) for v in c)
                    break
            dr.rectangle([20 + (x - X0) * S, 30 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 30 + (z - Z0 + 1) * S - 1], fill=c)
    px = lambda x: 20 + (x - X0) * S
    pz = lambda z: 30 + (z - Z0) * S
    for (cx, cz) in PI.LOADER:
        dr.rectangle([px(cx * 16), pz(cz * 16), px(cx * 16 + 16) - 1, pz(cz * 16 + 16) - 1], outline=(60, 60, 60), width=1)
    lx, lz = PI.LOADER_BLOCK
    dr.rectangle([px(lx), pz(lz), px(lx + 1), pz(lz + 1)], fill=(255, 210, 0), outline='black')
    for name, c, rects in UNDER:
        for x0, x1, z0, z1 in rects:
            for i in range(0, 2 * ((x1 - x0) + (z1 - z0)) + 2, 2):
                pass
            dr.rectangle([px(x0), pz(z0), px(x1 + 1), pz(z1 + 1)], outline=c, width=2)
    for x, z, t in LABELS:
        dr.multiline_text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    dr.text((20, 8), 'Промзона — план v2, как построено (этапы 1–3); сетка — 25 рабочих чанков, жёлтое — место загрузчика', fill='black', font=F(13))
    lxp, y = mw + 40, 40
    for name, c, _ in UNDER:
        dr.rectangle([lxp, y + 3, lxp + 14, y + 13], outline=c, width=2); dr.text((lxp + 20, y), name, fill='black', font=F(12)); y += 20
    y += 10
    for t in OPEN:
        dr.text((lxp, y), t, fill='black', font=F(12)); y += 18
    oy = mh + 50
    for title, cols_, (y0, y1) in secs:
        dr.text((20, oy), title, fill='black', font=F(12)); oy += 18
        for u, (x, z) in enumerate(cols_):
            if not known(x, z): continue
            for yy in range(y0, y1 + 1):
                b = blk(x, yy, z)
                if b in ('air', 'plant'): continue
                c = (120, 170, 225) if b == 'water' else (230, 100, 20) if b == 'lava' else (150, 135, 105) if b == 'ground' else CX.get(b, col(b))
                dr.rectangle([20 + u * E, oy + (y1 - yy) * E, 20 + (u + 1) * E - 1, oy + (y1 - yy + 1) * E - 1], fill=c)
        oy += (y1 - y0 + 1) * E + 18
    img.save(a.out)
    print('картинка:', os.path.relpath(a.out, REPO))


if __name__ == '__main__':
    main()
