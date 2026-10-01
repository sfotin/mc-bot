"""План района «Подводный купол» v2 — как построено (CITY.md §7.8): вид сверху по модели мира (все схемы BUILT,
включая dome-1-ground, dome-1-dry, dome-1-build, dome-1-metro; рельеф к югу от участка — docs/terrain/dome.json),
разрезы через купол (Z 1946) и галерею (X −756), подписи, ручные правки владельца, незакрытые пункты.
Запуск: plan_dome_v2.py [--out docs/districts/dome-plan-v2.png]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, BUILT, REPO  # noqa: E402
from oldtown_lib import col  # noqa: E402

X0, X1, Z0, Z1 = -790, -694, 1846, 1965
S = 6
CX = {'glass': (175, 215, 235), 'stained_glass:3': (120, 175, 225), 'concrete:0': (245, 245, 245), 'quartz_block': (240, 238, 232),
      'quartz_block:2': (245, 243, 236), 'sandstone:2': (225, 212, 160), 'stonebrick': (125, 125, 125), 'sea_lantern': (205, 235, 235),
      'grass': (110, 165, 70), 'leaves:4': (60, 120, 40), 'leaves:6': (110, 150, 60), 'stone:6': (150, 150, 150)}
LABELS = [(-782, 1944, 'КУПОЛ Ø 31\nсад, обход'), (-752, 1952, 'станция «Купол»'), (-752, 1899, 'павильон'),
          (-770, 1913, 'площадка'), (-751, 1918, 'галерея-\nлестница'), (-770, 1888, 'мыс'), (-740, 1880, 'марина'),
          (-697, 1905, 'ветка\nметро 2'), (-735, 1955, 'над впадиной —\nна опорах'), (-742, 1857, 'ст. «Набережная» →')]
OPEN = [('M', -702, -698, 1849, 1851, 'Ветка 2 — тупик у станции «Набережная»; линия 2 на север (§2.4) — позже, с метро всего города')]
MANUAL = ['Ручные правки владельца (в модели мира нет):', ' кнопки запуска на обеих станциях — на верх', ' блоков (из вагонетки достать);',
          ' скамейка на площадке острова A развёрнута,', ' песок у неё убран; грунт, ссыпавшийся на', ' стекло купола снаружи, убран.']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'dome-plan-v2.png'))
    a = ap.parse_args()
    W = World(BUILT, ext=True)
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    E = 5
    secs = [('Разрез по Z 1946: купол и станция «Купол» (X −790…−740)', [(x, 1946) for x in range(-790, -739)]),
            ('Разрез по X −756: павильон, галерея-лестница, вход в купол (Z 1900…1945)', [(-756, z) for z in range(1900, 1946)])]
    sh = len(secs) * (30 * E + 30)
    img = Image.new('RGB', (mw + 470, mh + 50 + sh), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 40 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    cc = lambda b: CX.get(b) or CX.get(b.split(':')[0]) or col(b)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 90
            while y > 25 and W.block(x, y, z) in ('air', 'plant'): y -= 1
            b = W.block(x, y, z)
            if b == 'water':
                yy = y
                while yy > 25 and W.block(x, yy, z) == 'water': yy -= 1
                bb = W.block(x, yy, z)
                if bb not in ('ground', 'air'):
                    c = tuple(int(0.55 * v + 0.45 * w) for v, w in zip(cc(bb), (70, 130, 210)))
                else:
                    k = max(0, min(1, (62 - yy) / 30)); c = (int(150 - 110 * k), int(200 - 110 * k), int(230 - 80 * k))
            elif b == 'ground':
                k = (max(60, min(y, 80)) - 60) / 20; c = (int(200 - 40 * k), int(200 - 20 * k), int(140 - 40 * k))
            else: c = cc(b)
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    for x in range(-790, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(10))
    for z in range(1850, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    for tag, x0, x1, z0, z1, _ in OPEN:
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], outline=(150, 40, 170), width=3)
        dr.text((px(x0) - 12, pz(z0) - 12), tag, fill=(150, 40, 170), font=F(12))
    for x, z, t in LABELS:
        dr.text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    lx = mw + 60
    dr.text((lx, 12), 'ПОДВОДНЫЙ КУПОЛ — план v2 (построено)', fill='black', font=F(16))
    notes = ['dome-1-ground, dome-1-dry, dome-1-build,', 'dome-1-metro построены (2026-10-01,', 'перестройка в 4 шага после outOfWorld).', '',
             'Купол Ø 31, стекло блоками, 8 рёбер,', 'выходит из воды (верх Y 65); сад, обход', 'у стекла, 3 скамейки лицом к морю.',
             'Павильон на острове A (высота 4) и', 'площадка от моста мыса со скамейкой;', 'галерея-лестница 64 → 53, просвет 4,',
             'над водой — голубое стекло.', 'Ветка метро 2: «Набережная» (под',
             'променадом, вход между кадками) —', 'стекло в воде, тоннель в породе —', '«Купол»; 149 бл., вагонетка, кнопки.', ''] + MANUAL + \
            ['', 'Не закрыто (фиолетовое):'] + [f' {t}: {d[:42]}' for t, *_, d in OPEN] + [f'   {d[42:]}' for *_, d in OPEN] + \
            ['', 'Граница участка — Z 1935; южнее —', 'съёмка docs/terrain/dome.json.']
    for i, t in enumerate(notes): dr.text((lx, 40 + i * 17), t, fill='black', font=F(11))
    oy = mh + 50
    for title, cols_ in secs:
        dr.text((40, oy), title, fill='black', font=F(12)); oy += 18
        for u, (x, z) in enumerate(cols_):
            for y in range(40, 70):
                b = W.block(x, y, z)
                if b in ('air', 'plant'): continue
                c = (70, 130, 215) if b == 'water' else (150, 135, 105) if b == 'ground' else cc(b)
                dr.rectangle([40 + u * E * 2, oy + (69 - y) * E, 40 + (u + 1) * E * 2 - 1, oy + (70 - y) * E - 1], fill=c)
        oy += 30 * E + 12
    img.save(a.out); print('план', a.out, img.size, '| построенных схем:', len(BUILT))


if __name__ == '__main__':
    main()
