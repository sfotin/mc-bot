"""План района «Сити» v1 (CITY.md §7.4): рельеф + всё построенное (world_model.py),
каньон (caves.json), улицы, площадь, Каньон-парк, башни и этапы, резерв трасс
метро 1 и коллектора (CITY.md §2.4), силуэт с моря.

Запуск: plan_city_v1.py [--out docs/districts/city-plan-v1.png]
Печатает сводку проверок плана: границы района, пересечения объектов, башни вне
полосы каньона, кровля каньона под зданиями (норма >= 3), резерв трасс, перепад
рельефа под площадками, стык улиц со Старым городом.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO  # noqa: E402

X0, X1, Z0, Z1 = -806, -700, 1768, 1868      # окно картинки
DX0, DX1, DZ0, DZ1 = -800, -725, 1776, 1848  # район (CITY.md §2.3; юг — до улицы-набережной Z 1849)
S = 9
ML, MT = 46, 30

AV = (95, 95, 95, 225)
ST = (150, 150, 150, 225)
WALK = (205, 200, 190, 230)
SQ = (232, 222, 196, 235)
TOWER = (150, 185, 215, 250)
LOW = (205, 215, 225, 245)

# ---- улицы: (ключ, подпись, X0, X1, Z0, Z1, этап, заливка) ----
STREETS = [
    ('av', 'главный проспект', -800, -725, 1814, 1818, 2, AV),
    ('av_n', 'тротуар', -800, -725, 1812, 1813, 2, WALK),
    ('av_s', 'тротуар', -800, -725, 1819, 1820, 2, WALK),
    ('pr', 'проспект Сити', -771, -767, 1776, 1848, 2, AV),       # ось дороги мыса X −771…−767
    ('st_n', 'Северная ул.', -784, -730, 1788, 1792, 2, ST),       # продолжение переулка Z 1789…1791
    ('st_s', 'Южная ул.', -800, -730, 1838, 1842, 2, ST),          # продолжение переулка Z 1839…1841
    ('st_b', 'Пограничная ул.', -729, -725, 1776, 1848, 2, ST),    # стык со Старым городом
    ('al_c', 'Коллекторная аллея', -747, -743, 1793, 1811, 3, WALK),  # над отводом коллектора X≈−745
]
# ---- объекты: (ключ, подпись, X0, X1, Z0, Z1, этап, заливка, обводка, верх Y) ----
OBJ = [
    ('sq', 'Площадь Сити', -766, -744, 1821, 1829, 3, SQ, (140, 120, 90), None),
    ('t1', 'Башня Сити', -764, -752, 1797, 1809, 4, TOWER, (20, 60, 110), 190),
    ('t2', 'Близнец З', -756, -748, 1831, 1837, 5, TOWER, (20, 60, 110), 150),
    ('t3', 'Близнец В', -741, -733, 1831, 1837, 5, TOWER, (20, 60, 110), 150),
    ('ex', 'Биржа', -739, -730, 1795, 1809, 5, LOW, (60, 60, 90), 92),
    ('t4', '«Парус»', -797, -786, 1822, 1833, 6, TOWER, (20, 60, 110), 165),
    ('t5', '«Холм»', -797, -788, 1795, 1804, 6, TOWER, (20, 60, 110), 170),
    ('t6', 'Северная З', -784, -775, 1777, 1786, 7, TOWER, (20, 60, 110), 130),
    ('t7', 'Северная Ц', -764, -755, 1777, 1786, 7, TOWER, (20, 60, 110), 140),
    ('t8', 'Северная В', -740, -731, 1777, 1786, 7, TOWER, (20, 60, 110), 120),
    ('mall', 'Торговая галерея', -764, -732, 1843, 1847, 7, LOW, (60, 60, 90), 76),
    ('look', 'смотровая «Провал»', -788, -777, 1844, 1855, 3, SQ, (140, 120, 90), None),
]
SKYBRIDGE = (-747, -742, 1832, 1834, 118)     # переход между Близнецами на Y 118
VEST = ('вестибюль «Каньон»', -747, -744, 1822, 1826)   # после схемы тоннеля (как в Старом городе)
# резерв трасс (CITY.md §2.4): без фундаментов ниже Y 60
RESERVE = [('общий тоннель метро 1 + коллектор', -800, -725, 1812, 1820),
           ('отвод коллектора на север (X≈−745)', -747, -743, 1776, 1811)]
BUILDINGS = {'t1', 't2', 't3', 'ex', 't4', 't5', 't6', 't7', 't8', 'mall'}
STATION = ('Каньон (л. 1)', -756, -744, 1814, 1818)     # зал на мосту в пустоте каньона


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'city-plan-v1.png'))
    args = ap.parse_args()
    W = World()
    cv = W._cv
    air = lambda x, z: cv['air'][(z - cv['z0']) * cv['w'] + x - cv['x0']] or 0

    # полоса каньона: пустота >= 8 бл. с кровлей выше Y 50 (главная ветка) + 2 бл. запаса
    canyon = {(x, z) for x in range(X0, X1 + 1) for z in range(Z0, Z1 + 1)
              if air(x, z) >= 8 and (W.cave_top(x, z) or 0) >= 50}
    park = {(x + dx, z + dz) for (x, z) in canyon for dx in range(-2, 3) for dz in range(-2, 3)
            if DZ0 + 20 <= z + dz <= DZ1 and DX0 <= x + dx <= DX1}
    sink = {(x, z) for x in range(DX0, DX1 + 1) for z in range(DZ0, 1856) if W.surf(x, z) < 50}

    print('== проверки плана ==')
    area = {}
    for k, _, x0, x1, z0, z1, *_ in STREETS + OBJ:
        zmax = 1855 if k == 'look' else DZ1     # смотровая обнимает провал, он южнее границы района
        assert DX0 <= x0 <= x1 <= DX1 and DZ0 <= z0 <= z1 <= zmax, ('вне района', k)
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                area.setdefault((x, z), []).append(k)
    ok = {frozenset(p) for p in (('av', 'pr'), ('st_n', 'pr'), ('st_s', 'pr'), ('st_b', 'av'), ('st_b', 'st_n'),
                                  ('st_b', 'st_s'), ('av_n', 'pr'), ('av_s', 'pr'), ('av_n', 'st_b'), ('av_s', 'st_b'))}
    bad = sorted({tuple(sorted(v)) for v in area.values() if len(v) > 1 and frozenset(v) not in ok})
    print('пересечения объектов:', 'нет' if not bad else bad)
    inpark = {k: len({(x, z) for x in range(o[2], o[3] + 1) for z in range(o[4], o[5] + 1)} & park)
              for k, *o in [(o[0], *o) for o in OBJ] if k in BUILDINGS}
    print('здания в полосе каньона (+2 бл.):', {k: v for k, v in inpark.items() if v} or 'нет')
    for k, _, x0, x1, z0, z1, st, *_r in OBJ:
        if k not in BUILDINGS: continue
        ys = [W.surf(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
        roofs = [W.surf(x, z) - W.cave_top(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
                 if W.cave_top(x, z) is not None and air(x, z) >= 3]
        top = _r[-1]
        print(f'{k:4s} {x1 - x0 + 1}×{z1 - z0 + 1} этап {st}: рельеф Y {min(ys)}…{max(ys)}, верх Y {top} '
              f'(≈{(top - max(ys)) // 4} эт.), кровля каньона мин. {min(roofs) if roofs else "—"}')
    rv = [(k, n) for n, x0, x1, z0, z1 in RESERVE for k, _, a0, a1, b0, b1, *_ in OBJ
          if k in BUILDINGS and not (a1 < x0 or a0 > x1 or b1 < z0 or b0 > z1)]
    print('здания над резервом трасс:', rv or 'нет')
    print('окно в каньон (площадь, над пустотой):',
          len({(x, z) for x in range(-766, -743) for z in range(1821, 1830)} & canyon), 'кл.')
    print('естественный провал до каньона: клеток', len(sink), '| X', min(x for x, _ in sink), '…', max(x for x, _ in sink),
          'Z', min(z for _, z in sink), '…', max(z for _, z in sink), '| дно Y', min(W.surf(x, z) for x, z in sink))
    for name, x0, x1, z0, z1 in [STATION]:
        c = [(W.cave_top(x, z) - air(x, z) + 1, W.cave_top(x, z)) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
             if (x, z) in canyon]
        print(f'станция {name}: пустота под проспектом Y {min(a for a, _ in c)}…{max(b for _, b in c)}, '
              f'по X {min(x for x in range(x0, x1 + 1) if any((x, z) in canyon for z in range(z0, z1 + 1)))}…'
              f'{max(x for x in range(x0, x1 + 1) if any((x, z) in canyon for z in range(z0, z1 + 1)))}')
    for nm, z in (('проспект', 1816), ('переулок С', 1790), ('переулок Ю', 1840)):
        print(f'стык Старый город X −724/−725, {nm} Z {z}: Y {W.surf(-724, z)} / {W.surf(-725, z)}')
    built = [k for k, _, x0, x1, z0, z1, *_ in STREETS + OBJ
             if any((x, y, z) in W.pre for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) for y in range(55, 100))]
    print('объекты поверх построенного:', built or 'нет')
    sh = [W.surf(x, z) for x in range(DX0, DX1 + 1) for z in range(DZ0, DZ1 + 1) if (x, z) not in sink]
    print('рельеф района: Y', min(sh), '…', max(sh))

    # ---------- картинка ----------
    def colr(x, z):
        y = 120
        while y > 20 and W.block(x, y, z) in ('air', 'plant'): y -= 1
        b = W.block(x, y, z)
        if b == 'water' or b.startswith('flowing_water'):
            yb = y
            while yb > 30 and W.block(x, yb, z) == 'water': yb -= 1
            d = min(y - yb, 16)
            return (int(150 - 7 * d), int(195 - 7 * d), int(235 - 3 * d))
        if b != 'ground': return (185, 180, 172)
        if y < 55: return (40, 30, 30)
        k = (max(62, min(y, 80)) - 62) / 18
        return (int(215 - 85 * k), int(212 - 60 * k), int(150 - 70 * k))

    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    fb = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf') if os.path.exists(f)), None)
    F = lambda n, b=False: ImageFont.truetype(fb if b and fb else fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    SK = 3                                              # силуэт: 3 px на блок
    skh = (200 - 60) * SK
    img = Image.new('RGB', (ML + mw + 470, MT + mh + 60 + skh + 40), (250, 250, 247))
    dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: ML + (x - X0) * S
    pz = lambda z: MT + (z - Z0) * S

    def rect(x0, x1, z0, z1, fill, outline=None, w=2):
        dr.rectangle([px(x0), pz(z0), px(x1 + 1) - 1, pz(z1 + 1) - 1], fill=fill, outline=outline, width=w)

    def dashed(x0, x1, z0, z1, c, w=2, d=6):
        pts = [(px(x0), pz(z0)), (px(x1 + 1), pz(z0)), (px(x1 + 1), pz(z1 + 1)), (px(x0), pz(z1 + 1)), (px(x0), pz(z0))]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = max(1, int(max(abs(bx - ax), abs(by - ay)) / d))
            for i in range(0, n, 2):
                dr.line([ax + (bx - ax) * i / n, ay + (by - ay) * i / n,
                         ax + (bx - ax) * min(i + 1, n) / n, ay + (by - ay) * min(i + 1, n) / n], fill=c, width=w)

    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            rect(x, x, z, z, colr(x, z))
    for (x, z) in park:                                 # Каньон-парк
        rect(x, x, z, z, (120, 175, 95, 200))
    for (x, z) in canyon:                               # пустота каньона под ним
        if (x + z) % 2 == 0:
            dr.line([px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z)], fill=(200, 30, 30, 230), width=2)
    for x in range(X0, X1 + 2):
        if x % 16 == 0: dr.line([px(x), MT, px(x), MT + mh], fill=(90, 90, 90, 110), width=1)
    for z in range(Z0, Z1 + 2):
        if z % 16 == 0: dr.line([ML, pz(z), ML + mw, pz(z)], fill=(90, 90, 90, 110), width=1)
    for x in range(-800, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1770, Z1 + 1, 10): dr.text((4, pz(z) - 6), str(z), fill='black', font=F(11))
    dashed(DX0, DX1, DZ0, DZ1, (0, 0, 0, 200), 2, 8)
    for k, _, x0, x1, z0, z1, st, fill in STREETS:
        rect(x0, x1, z0, z1, fill)
    for k, name, x0, x1, z0, z1, st, fill, ol, top in OBJ:
        rect(x0, x1, z0, z1, fill, ol)
    for (x, z) in canyon:                               # каньон поверх площади и улиц — пунктиром
        if (x + z) % 4 == 0 and any((x, z) in set() or k in ('sq', 'look') or not k.startswith('t')
                                    for k in area.get((x, z), [])):
            dr.line([px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z)], fill=(200, 30, 30, 200), width=2)
    wx = {(x, z) for x in range(-766, -743) for z in range(1821, 1830)} & canyon
    for (x, z) in wx: rect(x, x, z, z, (170, 225, 245, 255), (40, 120, 160), 1)   # стеклянное окно
    for (x, z) in sink: rect(x, x, z, z, (30, 20, 20, 255))
    x0, x1, z0, z1, _ = SKYBRIDGE
    rect(x0, x1, z0, z1, (90, 130, 170, 255), (20, 60, 110))
    _, x0, x1, z0, z1 = VEST
    rect(x0, x1, z0, z1, (120, 40, 160, 255), (60, 10, 90)); dr.text((px(x0) + 8, pz(z0) + 10), 'M', fill='white', font=F(14, True))
    for n, x0, x1, z0, z1 in RESERVE:
        dashed(x0, x1, z0, z1, (120, 40, 160, 230), 2, 5)
    dashed(*STATION[1:], (120, 40, 160, 255), 3, 4)
    dr.line([px(-800), pz(1816) + S // 2, px(-700), pz(1816) + S // 2], fill=(120, 40, 160, 150), width=3)
    for x in range(-796, -725, 8):                      # фонари проспекта
        for z in (1812, 1820):
            if not (-772 <= x <= -766):
                dr.ellipse([px(x) + 2, pz(z) + 2, px(x) + S - 3, pz(z) + S - 3], fill=(240, 200, 40), outline=(120, 90, 0))

    L = lambda x, z, s, sz=12, fill='black': dr.text((px(x), pz(z)), s, fill=fill, font=F(sz), stroke_width=3, stroke_fill=(255, 255, 255))
    L(-760, 1815, 'ГЛАВНЫЙ ПРОСПЕКТ', 11)
    L(-770, 1850, 'к дороге мыса ↓', 9)
    L(-770, 1778, 'П\nР\nО\nС\nП\nЕ\nК\nТ\n\nС\nИ\nТ\nИ', 10)
    L(-782, 1789, 'Северная ул.', 10); L(-800, 1839, 'Южная ул.', 10)
    L(-729, 1846, 'Погранич-\nная ул.', 8)
    L(-762, 1822, 'ПЛОЩАДЬ СИТИ', 11)
    L(-758, 1826, 'стекл. окно', 9, (10, 70, 110))
    L(-746, 1794, 'аллея', 9)
    for k, name, x0, x1, z0, z1, st, fill, ol, top in OBJ:
        if k in BUILDINGS:
            L(x0 + 1, z0 + 1, f'{k.upper().replace("T", "Т")}\n{name}\nY {top}', 9, (20, 40, 90))
    L(-788, 1844, '«ПРОВАЛ»', 10)
    L(-748, 1829, 'переход\nY 118', 8, (20, 40, 90))
    L(-790, 1830, 'КАНЬОН-\nПАРК', 11, (30, 90, 20)); L(-747, 1805, 'Каньон-\nпарк', 9, (30, 90, 20))
    L(-790, 1856, 'провал до Y 32', 9, (180, 20, 20))
    L(-722, 1783, 'СТАРЫЙ\nГОРОД', 11, (90, 90, 90))
    L(-790, 1771, 'ОКРАИНЫ (вне района)', 10, (90, 90, 90))
    L(-752, 1856, 'УЛИЦА-НАБЕРЕЖНАЯ (построено)', 10)
    L(-744, 1813, 'М «Каньон»', 9, (60, 10, 90))
    for k, name, x0, x1, z0, z1, st, *_ in OBJ + [s + (None, None) for s in STREETS if s[0] in ('pr',)]:
        cx, cz = px(x1 + 1) - 16, pz(z0) + 2
        dr.ellipse([cx, cz, cx + 14, cz + 14], fill=(255, 255, 255), outline=(200, 30, 30), width=2)
        dr.text((cx + 4, cz), str(st), fill=(200, 30, 30), font=F(11, True))

    # силуэт с моря (вид с юга): верх башен по X
    oy = MT + mh + 50
    base = oy + skh
    dr.text((ML, oy - 18), 'Силуэт с моря (вид с юга, 3 px = 1 бл., Y 60…200); Старый город — дома до Y ≈80', fill='black', font=F(12))
    for y in range(60, 201, 20):
        yy = base - (y - 60) * SK
        dr.line([ML, yy, ML + mw, yy], fill=(200, 200, 200), width=1)
        dr.text((4, yy - 6), str(y), fill='black', font=F(10))
    sx = lambda x: ML + (x - X0) * S
    for x in range(X0, X1 + 1):
        g = W.surf(x, 1800)
        dr.rectangle([sx(x), base - (g - 60) * SK, sx(x + 1) - 1, base], fill=(190, 180, 150))
    dr.rectangle([sx(-724), base - 20 * SK, sx(-700) - 1, base - 7 * SK], fill=(214, 150, 110))
    for k, name, x0, x1, z0, z1, st, fill, ol, top in sorted(OBJ, key=lambda o: -o[5]):
        if k not in BUILDINGS: continue
        g = min(W.surf(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
        dr.rectangle([sx(x0), base - (top - 60) * SK, sx(x1 + 1) - 1, base - (g - 60) * SK],
                     fill=fill, outline=ol, width=2)
        dr.text((sx(x0) + 2, base - (top - 60) * SK - 14), k.upper().replace('T', 'Т'), fill=(20, 40, 90), font=F(11, True))
    x0, x1, z0, z1, y = SKYBRIDGE
    dr.rectangle([sx(x0), base - (y + 3 - 60) * SK, sx(x1 + 1) - 1, base - (y - 60) * SK], fill=(90, 130, 170))
    dr.text((ML, base + 8), 'Сити: X −800…−725, Z 1776…1848 (пунктир). Клетка = блок, сетка — чанки, серое — построено, кружок — этап.',
            fill='black', font=F(12))

    lx = ML + mw + 20
    dr.text((lx, 12), 'СИТИ — план v1', fill='black', font=F(20, True))
    items = [((95, 95, 95), 'проспекты (5 бл.)'), ((150, 150, 150), 'улицы (5 бл.)'), ((205, 200, 190), 'тротуары, аллея'),
             ((232, 222, 196), 'площадь, смотровая'), ((150, 185, 215), 'башни (верх Y — подпись)'),
             ((205, 215, 225), 'Биржа, Торговая галерея'), ((120, 175, 95), 'Каньон-парк (полоса каньона +2)'),
             ((170, 40, 40), 'пустота каньона ≥ 8 бл.'), ((170, 225, 245), 'стеклянное окно в каньон'),
             ((30, 20, 20), 'естественный провал до Y 32'), ((120, 40, 160), 'резерв трасс; метро 1, зал «Каньон»'),
             ((240, 200, 40), 'фонарь')]
    for i, (cc, t) in enumerate(items):
        y = 48 + i * 22
        dr.rectangle([lx, y, lx + 22, y + 15], fill=cc, outline=(60, 60, 60))
        dr.text((lx + 30, y), t, fill='black', font=F(13))
    notes = [
        'Оси: главный проспект Z 1814…1818 (как в',
        '  Старом городе) + тротуары по 2 бл.;',
        '  проспект Сити X −771…−767 — продолжение',
        '  дороги мыса: маяк — мыс — Сити — окраины.',
        'Улицы 5 бл.: Северная Z 1788…1792, Южная',
        '  Z 1838…1842 (продолжают переулки Старого',
        '  города), Пограничная X −729…−725.',
        '',
        'Этапы:',
        ' 1 — земляные работы: площадки, срез холма',
        '     под проспектом, кровля над окном;',
        ' 2 — проспекты и улицы, фонари, деревья;',
        ' 3 — Площадь Сити со стеклянным окном,',
        '     Каньон-парк, аллея, смотровая «Провал»;',
        ' 4 — Т1 «Башня Сити» (13×13, до Y 190);',
        ' 5 — Т2/Т3 «Близнецы» с переходом, Биржа;',
        ' 6 — Т4 «Парус», Т5 «Холм»;',
        ' 7 — Т6–Т8 северный ряд, Торговая галерея.',
        ' Позже: вестибюль «Каньон» (со схемой',
        '   тоннеля), спуск в каньон из «Провала».',
        '',
        'Каньон под районом — открытая',
        '  достопримечательность (§1.4): над ним',
        '  парк, зданий в полосе нет; кровля под',
        '  зданиями ≥ 3, без подвалов.',
        'Метро 1: станция «Каньон» — зал на мосту',
        '  в пустоте каньона под проспектом',
        '  (≈X −756…−744, рельс ≈Y 50).',
        'Резерв: под проспектом Z 1812…1820 —',
        '  общий тоннель; X −747…−743 — отвод',
        '  коллектора на север (над ним аллея).',
    ]
    for i, t in enumerate(notes):
        dr.text((lx, 330 + i * 19), t, fill='black', font=F(13))
    img.save(args.out)
    print('план', args.out, img.size)


if __name__ == '__main__':
    main()
