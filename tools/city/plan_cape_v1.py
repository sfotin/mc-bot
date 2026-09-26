"""План района «Мыс» v1 (CITY.md §7.2): рельеф с уже построенной набережной,
пустоты каньона, зоны и объекты района, резерв ветки метро к куполу у A.

Запуск: plan_cape_v1.py [--out docs/districts/cape-plan-v1.png]
Модель мира: docs/terrain/site.json + построенные схемы набережной (BOT.md §9).
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, '..', '..'))
BUILT = (('embankment-1-earthworks.json', (-776, 56, 1847)),
         ('embankment-1d-beach-rebuild.json', (-756, 47, 1860)),
         ('embankment-2-promenade.json', (-775, 63, 1848)),
         ('embankment-3-pier-cafe.json', (-713, 48, 1869)))
X0, X1, Z0, Z1 = -800, -730, 1842, 1930
S = 9
ML, MT = 46, 30          # поля под подписи осей

# ---- объекты плана v1 (прямоугольники X0,X1,Z0,Z1 включительно) ----
ZONES = [
    # (подпись, X0, X1, Z0, Z1, заливка RGBA, обводка)
    ('улица-набережная', -775, -731, 1850, 1854, (90, 90, 90, 200), None),
    ('', -775, -731, 1855, 1859, (225, 215, 190, 220), (140, 120, 90)),
    ('дорога мыса', -771, -767, 1860, 1883, (95, 95, 95, 215), None),
    ('площадь маяка', -775, -763, 1884, 1892, (232, 222, 196, 235), (140, 120, 90)),
    ('яхт-клуб', -764, -755, 1869, 1877, (240, 240, 236, 240), (40, 60, 140)),
    ('акватория марины', -758, -739, 1878, 1894, (60, 110, 200, 70), (40, 80, 180)),
    ('фарватер', -778, -757, 1894, 1898, (60, 110, 200, 90), (40, 80, 180)),
    ('смотровая «Закат»', -794, -787, 1862, 1868, (232, 222, 196, 235), (140, 120, 90)),
    ('', -786, -772, 1865, 1866, (232, 222, 196, 235), None),
]
PONTOONS = [(-757, -739, 1878, 1879)] + [(x, x, 1880, 1890) for x in (-753, -748, -743)]
BRIDGE = (-768, -766, 1893, 1901)
LIGHTHOUSE = (-771, 1888, 2.6)   # центр, радиус
LAMPS = [(-772, z) for z in range(1864, 1884, 8)] + [(-766, z) for z in range(1864, 1884, 8)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'cape-plan-v1.png'))
    args = ap.parse_args()
    d = json.load(open(os.path.join(REPO, 'docs', 'terrain', 'site.json')))
    c = json.load(open(os.path.join(REPO, 'docs', 'terrain', 'caves.json')))
    W, SX, SZ = d['w'], d['x0'], d['z0']

    def G(x, z): return d['ground'][(z - SZ) * W + x - SX]

    def WA(x, z): return d['water'][(z - SZ) * W + x - SX]

    def CAVE(x, z): return c['air'][(z - c['z0']) * c['w'] + x - c['x0']] or 0
    PRE = {}
    for fn, o in BUILT:
        for e in json.load(open(os.path.join(REPO, 'schemas', fn))):
            PRE[(e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])] = e['block']

    def world(x, y, z):
        if (x, y, z) in PRE: return PRE[(x, y, z)]
        if y <= G(x, z): return 'ground'
        if WA(x, z) is not None and y <= WA(x, z): return 'water'
        return 'air'

    def col(x, z):
        y = 90
        while y > 30 and world(x, y, z) == 'air': y -= 1
        if world(x, y, z) in ('water',) or world(x, y, z).startswith('flowing'):
            yb = y
            while yb > 30 and world(x, yb, z) == 'water': yb -= 1
            dep = min(y - yb, 16)
            return (int(150 - 7 * dep), int(195 - 7 * dep), int(235 - 3 * dep))
        h = max(58, min(y, 72))
        k = (h - 58) / 14
        return (int(215 - 45 * k), int(205 - 40 * k), int(150 - 45 * k))

    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    fb = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf') if os.path.exists(f)), None)
    F = lambda n, b=False: ImageFont.truetype(fb if b and fb else fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (ML + mw + 470, MT + mh + 40), (250, 250, 247))
    dr = ImageDraw.Draw(img, 'RGBA')

    def px(x): return ML + (x - X0) * S

    def pz(z): return MT + (z - Z0) * S

    def rect(x0, x1, z0, z1, fill, outline=None, w=2):
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], fill=fill, outline=outline, width=w)

    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            rect(x, x, z, z, col(x, z))
    for x in range(X0, X1 + 1):  # каньон под поверхностью - штриховка
        for z in range(Z0, Z1 + 1):
            if CAVE(x, z) >= 10 and (x + z) % 2 == 0:  # только крупные пустоты (каньон), мелкие пещеры не показываем
                dr.line([px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z)], fill=(200, 30, 30, 200), width=2)
    for x in range(X0, X1 + 2):  # сетка чанков
        if x % 16 == 0: dr.line([px(x), MT, px(x), MT + mh], fill=(90, 90, 90, 110), width=1)
    for z in range(Z0, Z1 + 2):
        if z % 16 == 0: dr.line([ML, pz(z), ML + mw, pz(z)], fill=(90, 90, 90, 110), width=1)
    for x in range(X0, X1 + 1, 10):
        dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1850, Z1 + 1, 10):
        dr.text((4, pz(z) - 6), str(z), fill='black', font=F(11))

    for name, x0, x1, z0, z1, fill, ol in ZONES:
        rect(x0, x1, z0, z1, fill, ol)
    for x0, x1, z0, z1 in PONTOONS: rect(x0, x1, z0, z1, (170, 120, 70, 255), (90, 60, 30), 1)
    rect(*BRIDGE, (150, 100, 60, 255), (80, 50, 20), 1)
    cx, cz, r = LIGHTHOUSE
    dr.ellipse([px(cx) + S / 2 - r * S, pz(cz) + S / 2 - r * S, px(cx) + S / 2 + r * S, pz(cz) + S / 2 + r * S],
               fill=(245, 245, 245), outline=(190, 40, 40), width=3)
    for x, z in LAMPS: dr.ellipse([px(x) + 1, pz(z) + 1, px(x) + S - 2, pz(z) + S - 2], fill=(240, 200, 40), outline=(120, 90, 0))
    # резерв: ветка метро 2 под бухтой к куполу у A (ориентир), и точка A
    dr.line([px(-731), pz(1882), px(-762), pz(1910)], fill=(120, 40, 160, 220), width=3)
    ax, az = -762, 1910
    dr.ellipse([px(ax) - 5, pz(az) - 5, px(ax) + 5, pz(az) + 5], outline=(120, 40, 160), width=2)
    # подписи
    L = lambda x, z, s, sz=12, fill='black': dr.text((px(x), pz(z)), s, fill=fill, font=F(sz), stroke_width=3, stroke_fill=(255, 255, 255))
    L(-760, 1851, 'УЛИЦА-НАБЕРЕЖНАЯ', 11)
    L(-760, 1856, 'аллея', 10)
    L(-770, 1870, 'дорога\nмыса', 11)
    L(-763, 1871, 'ЯХТ-КЛУБ', 11, (20, 40, 120))
    L(-751, 1891, 'МАРИНА', 12, (20, 40, 120))
    L(-783, 1885, 'МАЯК', 13, (160, 30, 30))
    L(-763, 1886, 'площадь\nмаяка', 10)
    L(-765, 1899, 'МОСТ → A', 12, (90, 50, 20))
    L(-799, 1896, 'фарватер под мостом', 11, (20, 40, 120))
    L(-799, 1860, 'смотровая\n«Закат»', 10)
    L(-770, 1912, 'ОСТРОВ A', 13)
    L(-757, 1915, 'купол (район 8)', 10, (120, 40, 160))
    L(-750, 1904, 'ветка метро 2\n(резерв, глубоко)', 10, (120, 40, 160))
    L(-742, 1866, 'пляж\n(этап 1d)', 10)
    dr.text((ML, MT + mh + 8), 'Мыс: X −800…−730, Z 1842…1930. 1 клетка = 1 блок, сетка — чанки. Штриховка — каньон под поверхностью (≥10 бл. пустоты, CITY.md §1.4).',
            fill='black', font=F(12))

    # легенда
    lx = ML + mw + 20
    dr.text((lx, 12), 'МЫС — план v1', fill='black', font=F(20, True))
    items = [((90, 90, 90), 'дорога мыса / улица'), ((232, 222, 196), 'площадь, дорожки'), ((240, 240, 236), 'яхт-клуб'),
             ((170, 120, 70), 'понтоны марины (Y 63)'), ((150, 100, 60), 'мост на остров A'),
             ((120, 170, 225), 'выемка: акватория, фарватер'), ((245, 245, 245), 'маяк'), ((240, 200, 40), 'фонарь'),
             ((170, 40, 40), 'каньон под поверхностью (≥10 бл.)'), ((120, 40, 160), 'резерв метро 2 к куполу')]
    for i, (cc, t) in enumerate(items):
        y = 50 + i * 24
        dr.rectangle([lx, y, lx + 22, y + 16], fill=cc, outline=(60, 60, 60))
        dr.text((lx + 30, y), t, fill='black', font=F(13))
    notes = [
        'Дорога мыса X −771…−767 от аллеи',
        '  к площади маяка, уклон ≤1 на 4, фонари ×8.',
        'Площадь маяка X −775…−763, Z 1884…1892.',
        'Маяк Ø5, центр (−771, 1888), верх ≈Y 92.',
        'Мост X −768…−766, Z 1893…1901, выгнутый:',
        '  полублоки, ½ бл. на блок, середина ≈Y 66;',
        '  под ним фарватер, глубина ≥3.',
        'Яхт-клуб X −764…−755, Z 1869…1877,',
        '  терраса к марине; БЕЗ подвалов (каньон).',
        'Марина: причал Z 1878…1879, 3 пальца',
        '  по 11 бл.; акватория — дно не выше Y 56.',
        'Смотровая «Закат» на западном берегу.',
        '',
        'Этапы:',
        ' 1 — земляные работы: выемка акватории',
        '     и фарватера, основания площади и маяка;',
        ' 2 — дорога, площадь, фонари, «Закат»;',
        ' 3 — яхт-клуб и марина;',
        ' 4 — маяк;',
        ' 5 — мост на остров A.',
        '',
        'Под мысом — ветка каньона: фундаменты',
        'не глубже грунта, выемки не ниже Y 56.',
    ]
    for i, t in enumerate(notes):
        dr.text((lx, 310 + i * 19), t, fill='black', font=F(13))
    img.save(args.out)
    print('план', args.out, img.size)


if __name__ == '__main__':
    main()
