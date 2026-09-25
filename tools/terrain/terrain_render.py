"""
Рисует картинку рельефа по JSON, снятому terrain_from_region.py: высота
грунта (заливка + горизонтали через 4 блока), вода (глубина оттенком),
береговая линия, сетка чанков с подписями координат, опорные точки города
(см. CITY.md §1.2) и легенда.

Запуск:
    terrain_render.py <вход.json> <выход.png>
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

K = 5  # блоков на пиксель: 1 блок = K px, 1 чанк (16 блоков) = 16*K px
ML, MT = 60, 45  # отступы слева/сверху под подписи осей

# Опорные точки города (см. CITY.md §1.2) - специфичны для этого участка,
# не часть общего формата terrain-JSON.
PTS = {'A': (-762, 1910), 'B': (-748, 1819), 'C': (-667, 1816),
       'D': (-688, 1817), 'E': (-622, 1790), 'F': (-617, 1747)}

SEA_LEVEL = 62  # см. CITY.md §1.1


def _find_font_path(bold=False):
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold
        else '/System/Library/Fonts/Supplemental/Arial.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _load_font(size, bold=False):
    path = _find_font_path(bold)
    if path:
        return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def land_col(h):
    stops = [(56, (120, 170, 90)), (62, (150, 195, 110)), (66, (205, 215, 130)), (72, (215, 185, 120)),
             (80, (190, 140, 95)), (90, (165, 130, 115)), (104, (240, 240, 240))]
    for (h0, c0), (h1, c1) in zip(stops, stops[1:]):
        if h <= h1:
            t = max(0, min(1, (h - h0) / (h1 - h0)))
            return tuple(c0[i] + (c1[i] - c0[i]) * t for i in range(3))
    return stops[-1][1]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('inp', help='входной JSON (см. terrain_from_region.py)')
    p.add_argument('out', help='выходной PNG')
    return p.parse_args()


def main():
    args = parse_args()
    d = json.load(open(args.inp, encoding='utf-8'))
    X0, Z0, W, H = d['x0'], d['z0'], d['w'], d['h']

    g = np.array([v if v is not None else 0 for v in d['ground']], float).reshape(H, W)
    wat = np.array([v if v is not None else -1 for v in d['water']], float).reshape(H, W)
    isw = wat >= 0

    f10, f12, f14, f20 = _load_font(10), _load_font(12), _load_font(14, bold=True), _load_font(20, bold=True)

    # hillshade
    gy, gx = np.gradient(g)
    shade = np.clip(0.75 + 0.18 * (-gx - gy), 0.45, 1.15)

    rgb = np.zeros((H, W, 3))
    for z in range(H):
        for x in range(W):
            if isw[z, x]:
                dep = wat[z, x] - g[z, x]
                t = min(1, dep / 16)
                rgb[z, x] = (140 - 110 * t, 200 - 120 * t, 240 - 90 * t)
            else:
                rgb[z, x] = np.array(land_col(g[z, x])) * shade[z, x]
    img = Image.fromarray(np.clip(rgb, 0, 255).astype('uint8')).resize((W * K, H * K), Image.NEAREST)

    LEG = 300
    out = Image.new('RGB', (ML + W * K + LEG, MT + H * K + 45), (250, 250, 247))
    out.paste(img, (ML, MT))
    dr = ImageDraw.Draw(out)

    # горизонтали на суше через 4 блока (границы между клетками)
    for z in range(H):
        for x in range(W):
            if isw[z, x]: continue
            c = int(g[z, x]) // 4
            for dx, dz in ((1, 0), (0, 1)):
                x2, z2 = x + dx, z + dz
                if x2 < W and z2 < H and not isw[z2, x2] and int(g[z2, x2]) // 4 != c:
                    px, py = ML + x2 * K, MT + z2 * K
                    if dx: dr.line([(px, py - K), (px, py)], fill=(90, 60, 40), width=1)
                    else: dr.line([(px - K, py), (px, py)], fill=(90, 60, 40), width=1)
    # береговая линия (граница суша/вода) потолще
    for z in range(H):
        for x in range(W):
            for dx, dz in ((1, 0), (0, 1)):
                x2, z2 = x + dx, z + dz
                if x2 < W and z2 < H and isw[z, x] != isw[z2, x2]:
                    px, py = ML + x2 * K, MT + z2 * K
                    if dx: dr.line([(px, py - K), (px, py)], fill=(20, 40, 120), width=2)
                    else: dr.line([(px - K, py), (px, py)], fill=(20, 40, 120), width=2)

    # сетка чанков + подписи (число чанков считается из W/H, не хардкожено)
    nx, nz = W // 16, H // 16
    cx_label0, cz_label0 = X0 // 16, Z0 // 16
    for i in range(nx + 1):
        dr.line([(ML + i * 80, MT), (ML + i * 80, MT + H * K)], fill=(80, 80, 80), width=1)
    for i in range(nz + 1):
        dr.line([(ML, MT + i * 80), (ML + W * K, MT + i * 80)], fill=(80, 80, 80), width=1)
    for i in range(nx):
        dr.text((ML + i * 80 + 40, MT - 12), str(cx_label0 + i), font=f10, fill=(80, 80, 80), anchor='mm')
    for i in range(nz):
        dr.text((ML - 22, MT + i * 80 + 40), str(cz_label0 + i), font=f10, fill=(80, 80, 80), anchor='mm')
    dr.text((ML - 55, MT - 30), 'чанки Z \\ X', font=f10, fill=(80, 80, 80))

    for k, (x, z) in PTS.items():
        lx_, lz_ = x - X0, z - Z0
        if not (0 <= lx_ < W and 0 <= lz_ < H):
            continue  # точка вне текущего бокса - пропускаем, не падаем
        px, py = ML + lx_ * K + 2, MT + lz_ * K + 2
        h = int(g[lz_, lx_])
        dr.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(220, 0, 0), outline='white', width=2)
        dr.text((px + 7, py - 16), f'{k} {h}', font=f14, fill=(160, 0, 0), stroke_width=3, stroke_fill='white')

    dr.text((ML, MT + H * K + 10),
            f'X {X0} … {X0 + W - 1},  Z {Z0} … {Z0 + H - 1}.  1 клетка = 1 чанк.  '
            f'Горизонтали через 4 блока.  Уровень моря {SEA_LEVEL}.  Север — вверх.',
            font=f12, fill=(50, 50, 50))

    lx, y = ML + W * K + 20, MT
    dr.text((lx, y), 'РЕЛЬЕФ УЧАСТКА', font=f20, fill=(0, 0, 0)); y += 30
    dr.text((lx, y), f'{W}×{H} блоков ({nx}×{nz} чанков)', font=f12, fill=(80, 80, 80)); y += 30
    dr.text((lx, y), 'Высота грунта (Y):', font=f14, fill=(0, 0, 0)); y += 22
    for h in (58, 62, 64, 66, 70, 75, 80, 90, 100):
        dr.rectangle([lx, y, lx + 26, y + 16], fill=tuple(int(c) for c in land_col(h)), outline=(0, 0, 0))
        dr.text((lx + 34, y), str(h), font=f12, fill=(0, 0, 0)); y += 20
    y += 10
    dr.text((lx, y), 'Глубина воды:', font=f14, fill=(0, 0, 0)); y += 22
    for dep in (1, 4, 8, 12, 16):
        t = min(1, dep / 16)
        dr.rectangle([lx, y, lx + 26, y + 16], fill=(int(140 - 110 * t), int(200 - 120 * t), int(240 - 90 * t)), outline=(0, 0, 0))
        dr.text((lx + 34, y), f'{dep} бл.', font=f12, fill=(0, 0, 0)); y += 20
    y += 10
    dr.line([(lx, y + 8), (lx + 26, y + 8)], fill=(20, 40, 120), width=3); dr.text((lx + 34, y), 'береговая линия', font=f12, fill=(0, 0, 0)); y += 22
    dr.line([(lx, y + 8), (lx + 26, y + 8)], fill=(90, 60, 40), width=1); dr.text((lx + 34, y), 'горизонталь 4 бл.', font=f12, fill=(0, 0, 0)); y += 22
    dr.ellipse([lx + 8, y + 3, lx + 18, y + 13], fill=(220, 0, 0)); dr.text((lx + 34, y), 'опорная точка, Y', font=f12, fill=(0, 0, 0))

    out.save(args.out)
    print(out.size)


if __name__ == '__main__':
    main()
