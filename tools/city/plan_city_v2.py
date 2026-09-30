"""План Сити v2 — как построено (CITY.md §7.4): вид сверху по модели мира (все схемы BUILT,
включая этап 8 — шары и вертолёт), подписи объектов, незакрытые пункты (вестибюли метро
«Каньон», спуск в каньон). Запуск: plan_city_v2.py [--out docs/districts/city-plan-v2.png]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, BUILT, REPO  # noqa: E402
from oldtown_lib import col  # noqa: E402

PENDING = [('city-8-fix-1.json', (-800, 158, 1782)), ('city-8-balloons.json', (-762, 78, 1793))]
X0, X1, Z0, Z1 = -806, -680, 1772, 1916
S = 6
LABELS = [(-763, 1802, 'Т1 «Открывашка»'), (-756, 1834, 'Т2 «Ворота»'), (-739, 1801, 'Биржа'), (-797, 1826, '«Парус»'),
          (-800, 1797, '«Галька»'), (-786, 1781, '«Спираль»'), (-760, 1780, '«Три башни»'), (-760, 1845, '«Подкова»'),
          (-799, 1787, '«Вершина»'), (-765, 1824, 'Площадь Сити'), (-742, 1825, 'сквер'), (-780, 1807, 'пруд'),
          (-788, 1850, '«Провал»'), (-760, 1815, 'главный проспект'), (-737, 1886, 'шар «Сова»'), (-706, 1903, 'шар «Кит»'),
          (-697, 1797, 'шар «Лягушка»'), (-762, 1812, 'шар «Классика»'), (-745, 1854, 'вертолёт')]
OPEN = [('M', -747, -744, 1822, 1826, 'вестибюль «Каньон» Ю — после схемы тоннеля'),
        ('M', -751, -748, 1806, 1810, 'вестибюль «Каньон» С — после схемы тоннеля'),
        ('К', -784, -779, 1848, 1852, 'спуск в каньон из «Провала» — позже')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'city-plan-v2.png'))
    a = ap.parse_args()
    names = {b[0] for b in BUILT}
    pend = [p for p in PENDING if p[0] not in names and os.path.exists(os.path.join(REPO, 'schemas', p[0]))]
    W = World(tuple(BUILT) + tuple(pend))
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 60 + 400, mh + 50), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 40 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 200
            while y > 30 and W.block(x, y, z) in ('air', 'plant'): y -= 1
            b = W.block(x, y, z)
            if b == 'water': c = (70, 130, 215)
            elif b == 'ground':
                k = (max(60, min(y, 80)) - 60) / 20; c = (int(200 - 60 * k), int(215 - 40 * k), int(145 - 50 * k))
            else:
                c = col(b)
                if y > 100: c = tuple(min(255, int(v * 0.85 + 30)) for v in c)
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    for x in range(-800, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(10))
    for z in range(1780, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    dr.rectangle([px(-800), pz(1776), px(-724) - 1, pz(1849) - 1], outline=(0, 0, 0), width=2)
    for tag, x0, x1, z0, z1, _ in OPEN:
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], outline=(150, 40, 170), width=3)
        dr.text((px(x0) + 3, pz(z0) + 2), tag, fill=(150, 40, 170), font=F(12))
    for x, z, t in LABELS:
        dr.text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    lx = mw + 60
    dr.text((lx, 12), 'СИТИ — план v2 (построено)', fill='black', font=F(16))
    notes = ['Этапы 1–8 и холм построены', '(этап 8 — шары и вертолёт).',
             'Башни — все разной формы (план v1).', 'Шар над «Вершиной» снят: его закрывали',
             'башни; вместо него четыре шара вне', 'высокой застройки.', '',
             'Не закрыто (фиолетовое):'] + [f' {t}: {d}' for t, *_, d in OPEN] + \
            ['', 'Ручные правки владельца после city-1', '(не описаны) — в модели мира их нет.', '',
             'Чёрная рамка — граница района', 'X −800…−725, Z 1776…1848.']
    for i, t in enumerate(notes): dr.text((lx, 44 + i * 19), t, fill='black', font=F(12))
    img.save(a.out); print('план', a.out, img.size, '| к постройке учтено схем:', len(pend))


if __name__ == '__main__':
    main()
