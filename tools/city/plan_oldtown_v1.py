"""План района «Старый город» v1 (CITY.md §7.3): рельеф + всё построенное
(tools/city/world_model.py), пустоты каньона, зоны, объекты и этапы района,
резерв трасс метро и коллектора (CITY.md §2.4).

Запуск: plan_oldtown_v1.py [--out docs/districts/oldtown-plan-v1.png]
Печатает сводку проверок плана: пересечения объектов, резерв трасс,
кровля каньона под объектами, правка берегов прудов.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO  # noqa: E402

X0, X1, Z0, Z1 = -730, -655, 1728, 1868   # окно картинки
DX0, DX1, DZ0, DZ1 = -724, -661, 1780, 1848  # район (CITY.md §2.3; юг — до улицы-набережной Z 1849)
S = 9
ML, MT = 46, 30

# ---- объекты плана v1: (ключ, подпись, X0, X1, Z0, Z1, этап, заливка, обводка) ----
AV = (95, 95, 95, 225)
ST = (150, 150, 150, 225)
SQ = (232, 222, 196, 235)
HOUSE = (214, 150, 110, 190)
OBJ = [
    ('av_ns', 'проспект С–Ю', -692, -688, 1780, 1848, 2, AV, None),
    ('av_ew', 'главный проспект', -724, -661, 1814, 1818, 2, AV, None),
    ('l1', 'переулок', -724, -693, 1789, 1791, 2, ST, None),
    ('l2', 'переулок', -724, -693, 1839, 1841, 2, ST, None),
    ('l3', 'Рыночный пер.', -687, -661, 1793, 1795, 2, ST, None),
    ('l4', 'Ратушная ул.', -687, -661, 1836, 1838, 2, ST, None),
    ('sq_town', 'Ратушная площадь', -687, -674, 1819, 1834, 3, SQ, (140, 120, 90)),
    ('townhall', 'ратуша', -672, -662, 1821, 1833, 3, (205, 205, 215, 245), (60, 60, 90)),
    ('market_sq', 'рынок: прилавки', -687, -676, 1796, 1812, 4, SQ, (140, 120, 90)),
    ('market_hall', 'крытый рынок', -674, -663, 1797, 1811, 4, (236, 214, 160, 245), (150, 100, 40)),
    ('bar', 'бар «Таверна»', -686, -677, 1840, 1846, 5, (150, 90, 50, 245), (80, 40, 10)),
    ('cathedral', 'собор', -718, -707, 1794, 1810, 6, (240, 232, 205, 250), (120, 90, 40)),
    ('sq_cath', 'Соборная пл.', -706, -699, 1794, 1811, 6, SQ, (140, 120, 90)),
    ('pavilion', 'павильон «Галерея»', -703, -696, 1830, 1838, 7, (190, 230, 240, 245), (30, 110, 140)),
    ('k1', 'К1', -724, -694, 1780, 1788, 8, HOUSE, (150, 80, 50)),
    ('k2', 'К2', -724, -720, 1792, 1812, 8, HOUSE, (150, 80, 50)),
    ('k3', 'К3', -724, -709, 1819, 1837, 8, HOUSE, (150, 80, 50)),
    ('k4', 'К4', -724, -700, 1842, 1847, 8, HOUSE, (150, 80, 50)),
    ('vest_c', 'вестибюль «Центр»', -687, -683, 1807, 1812, 2, (120, 40, 160, 255), (60, 10, 90)),
    ('vest_e', 'вестибюль «Набережная»', -699, -695, 1842, 1847, 2, (120, 40, 160, 255), (60, 10, 90)),
    ('k5', 'К5', -687, -661, 1780, 1792, 8, HOUSE, (150, 80, 50)),
    ('k6', 'К6', -675, -661, 1840, 1847, 8, HOUSE, (150, 80, 50)),
]
# пруды после этапа 1 (вода Y 62…64, дно Y 61, углы срезаны, набережные — каменный кирпич до Y 65)
PONDS = [('lakeD', 'озеро D', -705, -694, 1820, 1832, 64), ('lake2', 'Соборный пруд', -698, -694, 1800, 1811, 64)]
PROMENADE = (-707, -693, 1819, 1834)     # кольцо-променад вокруг озера D (ширина 2, внутри — вода)
TOWER = (-672, -668, 1825, 1829)         # часовая башня ратуши 5×5
BELFRY = (-718, -714, 1800, 1804)        # колокольня собора
PIT = (-691, -688, 1840, 1846)           # провал до Y 59 — засыпать (этап 1)
# резерв трасс (CITY.md §2.4): без фундаментов ниже Y 60
RESERVE = [('общий тоннель метро 1 + коллектор', -724, -661, 1812, 1820),
           ('метро 2 (X≈−694) + отвод коллектора (X≈−686)', -696, -684, 1780, 1848)]
# метро (черновик до схемы сечения): залы станций под землёй, уровни — ориентир
METRO_LINES = [((-724, 1816), (-661, 1816)), ((-694, 1728), (-694, 1862))]
STATIONS = [('Центр (1+2)', -704, -678, 1814, 1818), ('', -697, -691, 1804, 1828),
            ('Набережная (2)', -697, -691, 1846, 1866), ('Вокзал (2)', -697, -691, 1742, 1760)]
# вне района — зона «Окраины» (CITY.md §2.3), ориентир
STATION_RAIL = (-706, -674, 1728, 1745)     # головной вокзал, пути уходят на север
STATION_SQ = (-704, -676, 1746, 1764)       # вокзальная площадь в торце проспекта С–Ю
BASEMENT_FREE = {'cathedral', 'pavilion', 'market_hall', 'townhall', 'bar'}  # проверка кровли каньона


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-plan-v1.png'))
    args = ap.parse_args()
    W = World()

    # ---------- проверки плана ----------
    print('== проверки плана ==')
    area = {}
    for k, _, x0, x1, z0, z1, *_ in OBJ:
        assert DX0 <= x0 <= x1 <= DX1 and DZ0 <= z0 <= z1 <= DZ1, ('вне района', k)
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                area.setdefault((x, z), []).append(k)
    ok_cross = {frozenset(('av_ns', 'av_ew')), frozenset(('market_sq', 'vest_c'))}  # вестибюль — в углу рынка
    bad = {frozenset(v) for v in area.values() if len(v) > 1 and frozenset(v) not in ok_cross}
    print('пересечения объектов:', 'нет' if not bad else sorted(map(sorted, bad)))
    for pk, pn, x0, x1, z0, z1, wl in PONDS:
        hit = {k for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) for k in area.get((x, z), [])}
        hit -= {'pavilion'}   # павильон консолью над водой — задумано
        print(f'{pn}: объектов на воде {sorted(hit) or "нет"}', end='; ')
        now = {(x, z) for x in range(x0 - 3, x1 + 4) for z in range(z0 - 3, z1 + 4)
               if W.water(x, z) is not None and W.water(x, z) >= W.surf(x, z)}
        new = {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
        print(f'засыпать {len(now - new)} кл., выкопать {len(new - now)} кл.')
    for k, _, x0, x1, z0, z1, *_ in OBJ:
        if k not in BASEMENT_FREE: continue
        m = min(((W.surf(x, z) - W.cave_top(x, z)), x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
                if W.cave_top(x, z) is not None)
        print(f'кровля каньона под {k}: мин. {m[0]} бл. (X {m[1]} Z {m[2]})')
    for name, x0, x1, z0, z1 in STATIONS:   # пол зала ≈Y 44 (линия 2) — пустоты каньона должны быть ниже
        tops = [(W.cave_top(x, z), x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if W.cave_top(x, z) is not None]
        print(f'станция {name or "Центр, зал л.2"}: верх пустот под залом max Y', max(tops)[0] if tops else '—')
    built = [k for k, _, x0, x1, z0, z1, *_ in OBJ
             if any((x, y, z) in W.pre for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) for y in range(55, 100))]
    print('объекты поверх построенного:', built or 'нет')
    sh = [W.surf(x, z) for x in range(DX0, DX1 + 1) for z in range(DZ0, DZ1 + 1)]
    print('рельеф района: Y', min(sh), '…', max(sh))

    # ---------- картинка ----------
    def col(x, z):
        y = 110
        while y > 30 and W.block(x, y, z) in ('air', 'plant'): y -= 1
        b = W.block(x, y, z)
        if b == 'water' or b.startswith('flowing_water'):
            yb = y
            while yb > 30 and W.block(x, yb, z) in ('water',): yb -= 1
            dep = min(y - yb, 16)
            return (int(150 - 7 * dep), int(195 - 7 * dep), int(235 - 3 * dep))
        if b not in ('ground',):
            return (185, 180, 172)          # построенное
        h = max(58, min(y, 70))
        k = (h - 58) / 12
        return (int(215 - 55 * k), int(210 - 45 * k), int(150 - 50 * k))

    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    fb = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf') if os.path.exists(f)), None)
    F = lambda n, b=False: ImageFont.truetype(fb if b and fb else fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (ML + mw + 500, MT + mh + 40), (250, 250, 247))
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
            rect(x, x, z, z, col(x, z))
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            ct = W.cave_top(x, z)
            a = W._cv['air'][(z - W._cv['z0']) * W._cv['w'] + x - W._cv['x0']] or 0
            if a >= 10 and (x + z) % 2 == 0:
                dr.line([px(x), pz(z + 1) - 1, px(x + 1) - 1, pz(z)], fill=(200, 30, 30, 170), width=2)
    for x in range(X0, X1 + 2):
        if x % 16 == 0: dr.line([px(x), MT, px(x), MT + mh], fill=(90, 90, 90, 110), width=1)
    for z in range(Z0, Z1 + 2):
        if z % 16 == 0: dr.line([ML, pz(z), ML + mw, pz(z)], fill=(90, 90, 90, 110), width=1)
    for x in range(-730, X1 + 1, 10): dr.text((px(x) - 10, 10), str(x), fill='black', font=F(11))
    for z in range(1780, Z1 + 1, 10): dr.text((4, pz(z) - 6), str(z), fill='black', font=F(11))

    # граница района
    dashed(DX0, DX1, DZ0, DZ1, (0, 0, 0, 200), 2, 8)
    # променад, пруды, объекты
    rect(*PROMENADE, SQ, None)
    for _, _, x0, x1, z0, z1, _ in PONDS:
        rect(x0, x1, z0, z1, (70, 130, 215, 235), (90, 90, 90), 2)
    for k, name, x0, x1, z0, z1, st, fill, ol in OBJ:
        rect(x0, x1, z0, z1, fill, ol)
    for x in range(-724, -660):   # штрих жилых кварталов
        for z in range(1780, 1849):
            if any(k.startswith('k') and len(k) == 2 for k in area.get((x, z), [])) and (x - z) % 4 == 0:
                dr.line([px(x), pz(z), px(x + 1), pz(z + 1)], fill=(150, 80, 50, 150), width=1)
    for (ax, az), (bx, bz) in METRO_LINES:
        dr.line([px(ax) + S // 2, pz(az) + S // 2, px(bx) + S // 2, pz(bz) + S // 2], fill=(120, 40, 160, 150), width=3)
    rect(*STATION_SQ, SQ, (140, 120, 90))
    rect(*STATION_RAIL, (170, 150, 190, 245), (70, 40, 110))
    for name, x0, x1, z0, z1 in STATIONS:
        dashed(x0, x1, z0, z1, (120, 40, 160, 255), 3, 4)
    for x in range(-702, -677, 4):
        dr.line([px(x) + S // 2, pz(1728), px(x) + S // 2, pz(1738)], fill=(60, 40, 30), width=2)
    rect(-692, -688, 1765, 1779, AV, None)
    for k, *_r in OBJ:
        if k.startswith('vest'):
            x0, x1, z0, z1 = _r[1:5]
            dr.text((px(x0) + 8, pz(z0) + 6), 'M', fill='white', font=F(14, True))
    rect(*TOWER, (120, 120, 150, 255), (40, 40, 70))
    rect(*BELFRY, (200, 180, 130, 255), (110, 80, 30))
    rect(*PIT, None, (200, 30, 30), 2)
    for name, x0, x1, z0, z1 in RESERVE:
        dashed(x0, x1, z0, z1, (120, 40, 160, 230), 2, 5)
    # фонари по проспектам (через 8)
    for z in range(1784, 1848, 8):
        for x in (-693, -687):
            if not (1812 <= z <= 1820): dr.ellipse([px(x) + 2, pz(z) + 2, px(x) + S - 3, pz(z) + S - 3], fill=(240, 200, 40), outline=(120, 90, 0))
    for x in range(-720, -660, 8):
        for z in (1813, 1819):
            if not (-694 <= x <= -686) and not (-687 <= x <= -674 and z == 1819):
                dr.ellipse([px(x) + 2, pz(z) + 2, px(x) + S - 3, pz(z) + S - 3], fill=(240, 200, 40), outline=(120, 90, 0))

    L = lambda x, z, s, sz=12, fill='black': dr.text((px(x), pz(z)), s, fill=fill, font=F(sz), stroke_width=3, stroke_fill=(255, 255, 255))
    L(-691, 1784, 'П\nР\nО\nС\nП\nЕ\nК\nТ\n\nС\n–\nЮ', 10)
    L(-722, 1815, 'ГЛАВНЫЙ ПРОСПЕКТ', 11)
    L(-686, 1824, 'РАТУШНАЯ\nПЛОЩАДЬ', 11)
    L(-671, 1830, 'РАТУША', 11, (20, 20, 70))
    L(-672, 1823, 'башня', 9, (20, 20, 70))
    L(-686, 1802, 'РЫНОК\n(прилавки)', 11)
    L(-673, 1802, 'КРЫТЫЙ\nРЫНОК', 11, (110, 60, 10))
    L(-686, 1841, 'БАР\n«Таверна»', 10, (80, 30, 0))
    L(-717, 1795, 'СОБОР', 12, (110, 70, 20))
    L(-718, 1805, 'колокольня', 9, (110, 70, 20))
    L(-706, 1795, 'Собор-\nная\nпл.', 9)
    L(-698, 1812, 'пруд', 9, (20, 40, 120))
    L(-703, 1824, 'ОЗЕРО D', 12, (20, 40, 120))
    L(-703, 1834, 'ПАВИЛЬОН\n«Галерея»', 9, (10, 70, 90))
    for k, _, x0, x1, z0, z1, *_ in OBJ:
        if k.startswith('k') and len(k) == 2: L(x0 + 1, z0 + (1 if z1 - z0 < 8 else 2), k.upper().replace('K', 'К'), 12, (120, 50, 20))
    L(-690, 1841, 'провал', 9, (180, 20, 20))
    L(-760 + 45, 1850, 'УЛИЦА-НАБЕРЕЖНАЯ (построено)', 11)
    L(-697, 1856, 'площадь с фонтаном', 10)
    L(-697, 1774, 'озеро N', 9, (20, 40, 120))
    L(-704, 1737, 'ВОКЗАЛ (головной)\nпути → север, деревня 1', 11, (60, 20, 100))
    L(-703, 1752, 'ВОКЗАЛЬНАЯ ПЛОЩАДЬ\nстанция метро «Вокзал»\nвход — из зала вокзала', 10)
    L(-728, 1768, 'ОКРАИНЫ (вне района)', 11, (90, 90, 90))
    L(-679, 1811, 'М «Центр»', 9, (60, 10, 90))
    L(-722, 1843, '', 9)
    L(-690, 1865, 'М «Набережная»', 9, (60, 10, 90))
    # номера этапов
    for k, name, x0, x1, z0, z1, st, *_ in OBJ:
        if k in ('l1', 'l2', 'l3', 'l4', 'av_ew') or (k.startswith('k') and len(k) == 2 and k != 'k1'): continue
        cx, cz = px(x1 + 1) - 16, pz(z0) + 2
        dr.ellipse([cx, cz, cx + 14, cz + 14], fill=(255, 255, 255), outline=(200, 30, 30), width=2)
        dr.text((cx + 4, cz), str(st), fill=(200, 30, 30), font=F(11, True))
    cx, cz = px(STATION_RAIL[1] + 1) - 16, pz(STATION_RAIL[2]) + 2
    dr.ellipse([cx, cz, cx + 14, cz + 14], fill=(255, 255, 255), outline=(200, 30, 30), width=2)
    dr.text((cx + 4, cz), '9', fill=(200, 30, 30), font=F(11, True))
    dr.text((ML, MT + mh + 8), 'Старый город: X −724…−661, Z 1780…1848 (пунктир); севернее — окраины. Клетка = блок, сетка — чанки, серое — построено, кружок — этап.', fill='black', font=F(12))

    lx = ML + mw + 20
    dr.text((lx, 12), 'СТАРЫЙ ГОРОД — план v1', fill='black', font=F(20, True))
    items = [((95, 95, 95), 'проспекты (5 бл.)'), ((150, 150, 150), 'улицы и переулки (3 бл.)'),
             ((232, 222, 196), 'площади, променад'), ((214, 150, 110), 'исторические кварталы К1–К6'),
             ((205, 205, 215), 'ратуша, часовая башня'), ((236, 214, 160), 'рынок'), ((150, 90, 50), 'бар'),
             ((240, 232, 205), 'собор, колокольня'), ((190, 230, 240), 'павильон (совр. архитектура)'),
             ((70, 130, 215), 'пруды после этапа 1'), ((240, 200, 40), 'фонарь'),
             ((170, 40, 40), 'каньон (≥10 бл. пустоты); провал'), ((120, 40, 160), 'резерв трасс: без фундаментов ниже Y 60'),
             ((150, 90, 190), 'метро: линия, зал станции (пунктир), M — вестибюль'),
             ((170, 150, 190), 'вокзал (окраины)')]
    for i, (cc, t) in enumerate(items):
        y = 48 + i * 22
        dr.rectangle([lx, y, lx + 22, y + 15], fill=cc, outline=(60, 60, 60))
        dr.text((lx + 30, y), t, fill='black', font=F(13))
    notes = [
        'Оси: проспект С–Ю X −692…−688 (по оси фонтана',
        '  набережной), главный Z 1814…1818 — по перешейку',
        '  между прудами (генплан: ≈1822, сдвиг на 6).',
        'Перекрёсток — точка D (−688, 1817).',
        '',
        'Этапы:',
        ' 1 — земляные работы: засыпка провала, пруды',
        '     (глубина 3, каменные набережные), подрезка',
        '     озера N и берегов под проспект;',
        ' 2 — проспекты, переулки, фонари, скамейки;',
        ' 3 — Ратушная площадь, ратуша с башней;',
        ' 4 — рынок: прилавки + крытый рынок;',
        ' 5 — бар «Таверна» с террасой к морю;',
        ' 6 — собор с колокольней, Соборная площадь;',
        ' 7 — павильон «Галерея», променад озера D;',
        ' 8 — кварталы К1–К6 (схема на квартал);',
        ' 9 — вокзал и вокзальная площадь (окраины,',
        '     отдельный этап; продолжение проспекта).',
        '',
        'Без подвалов: собор, павильон (кровля',
        '  каньона 4 бл.), всё над резервом трасс.',
        '',
        'Метро (черновик до схемы сечения):',
        ' «Центр» — пересадочная под перекрёстком:',
        '   линия 1 выше (рельс ≈Y 52), линия 2 ниже',
        '   (≈Y 46); вестибюль — угол рынка.',
        ' «Набережная» (л. 2) — под площадью',
        '   с фонтаном; вестибюль — торец К4.',
        ' «Вокзал» (л. 2) — под вокзальной площадью.',
        ' Вестибюли: Центр↔Набережная ≈36 бл.,',
        '   Центр↔Вокзал ≈50 бл.; линия 1: Каньон',
        '   (−748) ↔ Центр ≈58 бл. ↔ Парк (≈−640).',
    ]
    for i, t in enumerate(notes):
        dr.text((lx, 400 + i * 19), t, fill='black', font=F(13))
    img.save(args.out)
    print('план', args.out, img.size)


if __name__ == '__main__':
    main()
