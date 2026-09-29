"""План Старого города v2 — как построено (CITY.md §7.3): вид сверху по модели мира
(все схемы BUILT + исправления к постройке), подписи объектов, незакрытые пункты
(вестибюли метро, вокзал). Запуск: plan_oldtown_v2.py [--out docs/districts/oldtown-plan-v2.png]
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, BUILT, REPO  # noqa: E402
from oldtown_lib import col  # noqa: E402

PENDING = [('oldtown-7-fix-1.json', (-707, 65, 1827)), ('oldtown-8-fix-1.json', (-722, 64, 1818))]
X0, X1, Z0, Z1 = -730, -655, 1728, 1862
S = 8
LABELS = [(-686, 1824, 'РАТУША, площадь'), (-686, 1800, 'РЫНОК'), (-686, 1843, 'ТАВЕРНА'), (-716, 1802, 'БИБЛИОТЕКА'),
          (-700, 1793, 'крипер'), (-704, 1824, 'озеро D'), (-703, 1835, '«Галерея»'), (-722, 1784, 'К1'), (-723, 1795, 'К2'),
          (-722, 1822, 'К3'), (-722, 1844, 'К4'), (-685, 1783, 'К5'), (-673, 1843, 'К6'), (-706, 1850, 'улица-набережная')]
OPEN = [('M', -687, -683, 1807, 1812, 'вестибюль «Центр» — после схемы тоннеля'),
        ('M', -699, -695, 1842, 1847, 'вестибюль «Набережная» — после схемы тоннеля'),
        ('9', -706, -674, 1728, 1745, 'вокзал (этап 9, окраины)'), ('9', -704, -676, 1746, 1764, 'вокзальная площадь')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-plan-v2.png'))
    a = ap.parse_args()
    pend = [p for p in PENDING if os.path.exists(os.path.join(REPO, 'schemas', p[0]))]
    W = World(tuple(BUILT) + tuple(pend))
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 60 + 380, mh + 50), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 40 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 110
            while y > 40 and W.block(x, y, z) in ('air', 'plant'): y -= 1
            b = W.block(x, y, z)
            if b == 'water': c = (70, 130, 215)
            elif b == 'ground':
                k = (max(60, min(y, 70)) - 60) / 10; c = (int(200 - 60 * k), int(215 - 40 * k), int(145 - 50 * k))
            else: c = col(b)
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    for x in range(-730, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1730, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(11))
    dr.rectangle([px(-724), pz(1780), px(-660) - 1, pz(1849) - 1], outline=(0, 0, 0), width=2)
    for tag, x0, x1, z0, z1, _ in OPEN:
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], outline=(150, 40, 170), width=3)
        dr.text((px(x0) + 3, pz(z0) + 2), tag, fill=(150, 40, 170), font=F(13))
    for x, z, t in LABELS:
        dr.text((px(x), pz(z)), t, fill='black', font=F(12), stroke_width=3, stroke_fill='white')
    lx = mw + 60
    dr.text((lx, 12), 'СТАРЫЙ ГОРОД — план v2 (построено)', fill='black', font=F(16))
    notes = ['Этапы 1–8 построены (с исправлениями).', 'Собор плана v1 заменён библиотекой', '(чаровальня, серверная ME) и статуей крипера.',
             '', 'Не закрыто (фиолетовое):'] + [f' {t}: {d}' for t, *_, d in OPEN] + \
            ['', 'Чёрная рамка — граница района', 'X −724…−661, Z 1780…1848.']
    for i, t in enumerate(notes): dr.text((lx, 44 + i * 20), t, fill='black', font=F(12))
    img.save(a.out); print('план', a.out, img.size, '| исправлений к постройке учтено:', len(pend))


if __name__ == '__main__':
    main()
