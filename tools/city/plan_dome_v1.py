"""План района «Подводный купол» v1 (CITY.md §7.8): вид сверху (дно бухты по съёмке site.json + dome.json,
построенное по модели мира, объекты района), профиль пути с острова и ветки метро.

Объекты: стеклянный купол с подводным садом и смотровым обходом к югу от острова A; станция «Купол» —
вестибюль-узел у купола (сюда приходят галерея и метро); стеклянная галерея-лестница с острова A
(павильон у моста мыса); ветка метро 2 — стеклянная труба по дну от станции «Набережная» (под променадом
к западу от площади с фонтаном) до станции «Купол».

Проверки (печатает; «ОШИБКА» — план не годится): вода над куполом, пересечения с построенным (BUILT),
лодки владельца (сущности из r.-2.3.mca), кровля каньона над выемками, проходимость пешехода по высотам
(остров → купол, променад → платформа) с шириной ≥ 3 и высотой ≥ 3, уклон пути метро, — и негативы
(каждая проверка на заведомо плохом варианте должна дать ошибку).
Запуск: plan_dome_v1.py [--out docs/districts/dome-plan-v1.png]
"""
import argparse
import os
import sys
from collections import deque

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model import World, REPO  # noqa: E402

SEA = 62
# --- купол: эллипсоид над полом, газон Y 52, ноги 53; оболочка — стекло блоками + рёбра -----------------------------------------------
DOME_C, DOME_RH, DOME_RV, DOME_FY = (-768, 1946), 15, 13, 52   # Ø 31, верх 65 — над водой
# --- станция «Купол» (узел): коробка, пол 48, ноги 49, потолок 53 ----------------------------------
HUB = (-752, -744, 1942, 1950)
HUB_FY, HUB_TOP = 52, 57
# --- павильон на острове и галерея-лестница ---------------------------------------------------------
PAV = (-759, -753, 1903, 1909)          # ноги 64
ISLE_PATH = [(x, z) for x in range(-767, -759) for z in range(1904, 1907)]   # от моста (Z 1901, верх 64)
GAL_X = (-757, -755)                     # внутренность галереи по оси павильона, стенки X −758 и −754


def gallery_profile():
    """Z → ноги: площадка 1910…1912 (64), марши 4+4+3 ступени с площадками по 3, низ 1930…1939 (53) — вход в купол."""
    prof, y, z = {}, 64, 1910
    for seg in ('L3', 'S4', 'L3', 'S4', 'L3', 'S3', 'L10'):
        n = int(seg[1:])
        for _ in range(n):
            if seg[0] == 'S': y -= 1
            prof[z] = y; z += 1
    return prof                          # Z 1910…1939


def gallery_ceiling(gal):
    """Низ свода галереи по Z: над ступенью — по верхней из соседних (проём начинается над первой ступенью)."""
    if CEIL_MODE == 'naive': return {z: gal[z] + 3 for z in gal}
    return {z: max(gal.get(z - 1, gal[z]), gal[z], gal.get(z + 1, gal[z])) + 3 for z in gal}


# --- метро: станция «Набережная», рампа, труба по дну -------------------------------------------------
TRACK_X = -700                           # ось пути на юг; труба X −702…−698 (внутри −701…−699)
ST_N = (-709, -699, 1850, 1858)          # зал: платформа X −709…−701, путь X −700 (Z 1850…1866), ноги 57
ST_FEET = 57
ST_STAIR = [(x, z) for x in range(-709, -706) for z in range(1859, 1867)]    # 8 ступеней на юг до ног 65 (вход с юга, Z 1867)
EARTH = {'stone', 'sand', 'dirt', 'gravel', 'grass', 'clay'}   # ядра и подсыпки построенного — копать можно
# стенка набережной Z 1869 над рампой: низ стенки снимается, стенка опирается на свод трубы
ALLOW_CUT = {(x, y, 1869) for x in range(-702, -697) for y in range(50, 60)}
CEIL_MODE = 'safe'                       # 'naive' — потолок по своей ступени (для негатива)
TRACK_Z = 1948                           # поворот на запад к станции «Купол» (южный край зала)
TUBE_FEET = 53


def metro_track():
    """Список (x, z, ноги) по оси пути: станция → рампа 1:1 → по дну 49 → поворот → станция «Купол»."""
    t = []
    for z in range(1850, 1867): t.append((TRACK_X, z, ST_FEET))
    y = ST_FEET
    for z in range(1867, 1867 + ST_FEET - TUBE_FEET): y -= 1; t.append((TRACK_X, z, y))
    for z in range(1867 + ST_FEET - TUBE_FEET, TRACK_Z + 1): t.append((TRACK_X, z, TUBE_FEET))
    for x in range(TRACK_X - 1, -751, -1): t.append((x, TRACK_Z, TUBE_FEET))   # упор у X −750
    return t


def dome_cells():
    cx, cz = DOME_C
    return [(x, z) for x in range(cx - DOME_RH, cx + DOME_RH + 1) for z in range(cz - DOME_RH, cz + DOME_RH + 1)
            if (x - cx) ** 2 + (z - cz) ** 2 <= DOME_RH ** 2]


def tube_cells(track):
    """Колонны трубы метро (ось ± 2), без коробок станций."""
    out = set()
    for x, z, y in track:
        if z <= 1866 or x <= HUB[1]: continue
        for d in range(-2, 3):
            out.add((x + d, z, y) if x == TRACK_X and z < TRACK_Z else (x, z + d, y))
    return out


BOATS = [(-745.0, 1882.2, 'ic2:electric_boat'), (-744.9, 1886.9, 'boat (берёза)')]   # r.-2.3.mca, 2026-10-01


# =================================================================================================
def walk_graph(gal):
    """Клетки «ноги» пешеходной сети: (x, z) → ноги; лестничные клетки допускают шаг 1, остальные 0.5."""
    feet, stair = {}, set()
    for x, z in ISLE_PATH: feet[(x, z)] = 64
    for x in range(PAV[0], PAV[1] + 1):
        for z in range(PAV[2], PAV[3] + 1): feet[(x, z)] = 64
    for z, y in gal.items():
        for x in range(GAL_X[0], GAL_X[1] + 1):
            feet[(x, z)] = y; stair.add((x, z))
    for x in range(HUB[0] + 1, HUB[1]):
        for z in range(HUB[2] + 1, HUB[3]):
            if z != TRACK_Z: feet[(x, z)] = 53           # путь — не тротуар
    for z in (1944, 1945, 1946): feet[(HUB[0], z)] = feet[(HUB[0] - 1, z)] = 53   # проём в купол
    cx, cz = DOME_C
    for x, z in dome_cells():
        if (x - cx) ** 2 + (z - cz) ** 2 <= (DOME_RH - 1) ** 2: feet[(x, z)] = 53
    return feet, stair


def reach(feet, stair, start):
    seen, q = {start}, deque([start])
    while q:
        c = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dz)
            if n not in feet or n in seen: continue
            lim = 1 if (n in stair or c in stair) else 0.5
            if abs(feet[n] - feet[c]) <= lim: seen.add(n); q.append(n)
    return seen


def min_width(feet, path_cols):
    """Ширина прохода поперёк хода по каждому ряду (для галереи — по X)."""
    return min(sum((x, z) in feet for x in range(GAL_X[0] - 1, GAL_X[1] + 2)) for z in path_cols)


def checks(W, verbose=True):
    errs, lines = [], []
    say = lambda s: lines.append(s)
    gal = gallery_profile(); track = metro_track()
    # 1. вода над куполом
    top = DOME_FY + DOME_RV
    say(f'купол: центр {DOME_C}, Ø {2 * DOME_RH + 1}, газон Y {DOME_FY}, верх {top}, над водой {top - SEA} бл., '
        f'глубина у пола {SEA - DOME_FY} бл.')
    if top - SEA < 2: errs.append('купол выходит из воды меньше чем на 2 бл. — внутри темно')
    gal_ = gallery_profile(); ceil_ = gallery_ceiling(gal_)
    above = sum(1 for z in gal_ if ceil_[z] > SEA)
    say(f'галерея над водой (стены и свод — крашеное стекло): Z {min(z for z in gal_ if ceil_[z] > SEA)}…'
        f'{max(z for z in gal_ if ceil_[z] > SEA)} ({above} рядов); пол лестницы — кварц, не стекло')
    # 2. пересечения с построенным
    occ = {}
    for x, z in dome_cells():
        for y in range(DOME_FY - 1, top + 1): occ[(x, y, z)] = 'купол'
    for x in range(HUB[0], HUB[1] + 1):
        for z in range(HUB[2], HUB[3] + 1):
            for y in range(HUB_FY - 1, HUB_TOP + 1): occ[(x, y, z)] = 'станция «Купол»'
    for z, f in gal.items():
        for x in range(GAL_X[0] - 1, GAL_X[1] + 2):
            for y in range(f - 1, f + 4): occ[(x, y, z)] = 'галерея'
    for x, z, f in tube_cells(track):
        for y in range(f - 1, f + 4): occ[(x, y, z)] = 'труба метро'
    for x in range(ST_N[0], ST_N[1] + 1):              # внутренность зала; стены — по месту (построенное не трогаем)
        for z in range(ST_N[2], ST_N[3] + 1):
            for y in range(ST_FEET - 1, ST_FEET + 5): occ[(x, y, z)] = 'станция «Набережная»'
    hit = {}
    for k, who in occ.items():
        b = W.pre.get(k)
        if b and b != 'air' and not b.startswith('water') and b.split(':')[0] not in EARTH and k not in ALLOW_CUT:
            hit.setdefault(who, []).append(k)
    for who, ks in hit.items():
        errs.append(f'{who}: пересекает построенное, {len(ks)} бл., напр. {ks[0]} = {W.pre[ks[0]]}')
    say('пересечения с построенным: ' + ('нет' if not hit else ', '.join(f'{w} {len(k)}' for w, k in hit.items())))
    # 3. лодки
    near = [b for b in BOATS if any(abs(b[0] - x) < 3 and abs(b[1] - z) < 3 for (x, y, z) in occ)]
    say(f'лодки владельца ({len(BOATS)}, марина): ' + ('в стороне' if not near else f'ЗАДЕТЫ {near}'))
    if near: errs.append('объекты задевают лодки')
    # 4. кровля каньона над выемками (низ постройки − верх пустоты ≥ 3)
    low = {}
    for (x, y, z) in occ: low[(x, z)] = min(low.get((x, z), 999), y)
    bad = [(c, W.cave_top(*c), y) for c, y in low.items() if W.cave_top(*c) and y - W.cave_top(*c) - 1 < 3]
    worst = min(((y - t - 1), c) for c, t, y in [(c, W.cave_top(*c), y) for c, y in low.items() if W.cave_top(*c)])
    say(f'кровля каньона: минимум {worst[0]} бл. у {worst[1]}' + (f', МАЛО в {len(bad)} кол.' if bad else ''))
    if bad: errs.append(f'кровля каньона < 3: {bad[:3]}')
    # 5. пешеход: остров → купол; ширина и высота
    feet, stair = walk_graph(gal)
    seen = reach(feet, stair, (-766, 1905))
    ok = DOME_C in seen and (HUB[0] + 2, HUB[2] + 2) in seen
    say(f'пешеход мост → павильон → галерея → купол → станция «Купол»: {"да" if ok else "НЕТ"}, клеток {len(seen)}')
    if not ok: errs.append('купол не достижим с острова')
    wmin = min_width(feet, range(1910, 1937))
    say(f'ширина галереи: {wmin} бл.')
    if wmin < 3: errs.append('галерея уже 3 бл.')
    ceil = gallery_ceiling(gal)
    head = min(min(ceil[a], ceil[b]) - max(gal[a], gal[b]) for a, b in zip(sorted(gal), sorted(gal)[1:]))
    say(f'просвет над ступенями галереи (на переходе между ступенями): {head} бл.')
    if head < 3: errs.append(f'просвет над лестницей галереи {head} < 3')
    # платформа «Набережная» ← променад
    pf = {(x, z): ST_FEET for x in range(ST_N[0], ST_N[1] - 1) for z in range(ST_N[2], ST_N[3] + 1)}
    sst = set()
    for x, z in ST_STAIR: pf[(x, z)] = ST_FEET + (z - ST_N[3]); sst.add((x, z))
    for x in range(-709, -706): pf[(x, 1867)] = 65
    s2 = reach(pf, sst, (-708, 1867))
    ok2 = (-703, 1855) in s2 and pf[(-708, 1866)] == 65
    say(f'пешеход променад (65) → платформа «Набережная» ({ST_FEET}): {"да" if ok2 else "НЕТ"}')
    if not ok2: errs.append('платформа не достижима с променада')
    # 6. путь метро
    st = max(abs(a[2] - b[2]) for a, b in zip(track, track[1:]))
    say(f'метро: длина пути {len(track)} бл., шаг по высоте ≤ {st} на блок, глубина над трубой ≥ '
        f'{SEA - (TUBE_FEET + 3)} бл.; над впадиной X −745…−720 — на опорах до {TUBE_FEET - 1 - min(W.ground(x, TRACK_Z) for x in range(-745, -719))} бл.')
    if st > 1: errs.append('уклон пути метро круче 1:1')
    if verbose: print('\n'.join(lines))
    return errs


def negatives(W):
    """Каждая проверка на заведомо плохом варианте должна упасть."""
    global DOME_RV, TRACK_X, gallery_profile, CEIL_MODE
    res = []
    saved = (DOME_RV, TRACK_X, gallery_profile, CEIL_MODE)
    def run(name, setup, key):
        global DOME_RV, TRACK_X, gallery_profile, CEIL_MODE
        setup(); e = [x for x in checks(W, verbose=False) if key in x]
        DOME_RV, TRACK_X, gallery_profile, CEIL_MODE = saved
        res.append((name, bool(e), e[:1]))
    def s1():
        global DOME_RV; DOME_RV = 10
    def s2():
        global TRACK_X; TRACK_X = -696                      # труба в сваи головы пирса
    def s3():
        global gallery_profile
        g0 = saved[2]
        def bad():
            g = g0(); g[1914] -= 1; return g               # ступень 2 бл.
        gallery_profile = bad
    def s4():
        global CEIL_MODE; CEIL_MODE = 'naive'
    run('купол под водой', s1, 'темно')
    run('труба в сваях пирса', s2, 'пересекает')
    run('ступень галереи 2 бл.', s3, 'не достижим')
    run('свод галереи по своей ступени', s4, 'просвет')
    return res


def draw(W, out):
    X0, X1, Z0, Z1, S = -800, -673, 1844, 1960, 6
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    PH1, PH2 = (68 - 44) * 8 + 40, (68 - 30) * 3 + 40
    img = Image.new('RGB', (mw + 60, mh + 60 + PH1 + PH2 + 40), (250, 250, 247)); dr = ImageDraw.Draw(img, 'RGBA')
    px = lambda x: 40 + (x - X0) * S; pz = lambda z: 30 + (z - Z0) * S
    built = {}
    for (x, y, z), b in W.pre.items():
        if y >= 60 and b != 'air' and not b.startswith('water') and X0 <= x <= X1 and Z0 <= z <= Z1: built[(x, z)] = 1
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            g, w = W.ground(x, z), W.water(x, z)
            if (x, z) in built: c = (175, 165, 150)
            elif w:
                k = max(0, min(1, (SEA - g) / 30)); c = (int(150 - 110 * k), int(200 - 110 * k), int(230 - 80 * k))
            else:
                k = max(0, min(1, (g - 62) / 8)); c = (int(205 - 40 * k), int(200 - 20 * k), int(140 - 40 * k))
            dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=c)
    dr.line([px(X0), pz(1936), px(X1 + 1), pz(1936)], fill=(120, 120, 120), width=1)
    dr.text((px(-698), pz(1936) + 2), 'граница участка Z 1935 / съёмка dome.json', fill=(90, 90, 90), font=F(10))
    cx, cz = DOME_C
    dr.ellipse([px(cx - DOME_RH), pz(cz - DOME_RH), px(cx + DOME_RH + 1), pz(cz + DOME_RH + 1)],
               fill=(120, 200, 120, 200), outline=(20, 110, 140), width=3)
    dr.ellipse([px(cx - 7), pz(cz - 7), px(cx + 8), pz(cz + 8)], outline=(230, 220, 190), width=6)
    dr.rectangle([px(HUB[0]), pz(HUB[2]), px(HUB[1] + 1), pz(HUB[3] + 1)], fill=(240, 238, 232), outline=(20, 110, 140), width=2)
    dr.rectangle([px(PAV[0]), pz(PAV[2]), px(PAV[1] + 1), pz(PAV[3] + 1)], fill=(240, 238, 232), outline=(20, 110, 140), width=2)
    for x, z in ISLE_PATH: dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=(225, 212, 160))
    gal = gallery_profile()
    for z, y in gal.items():
        c = (170, 215, 240) if y == gal.get(z - 1, y) else (90, 160, 200)
        dr.rectangle([px(GAL_X[0] - 1), pz(z), px(GAL_X[1] + 2) - 1, pz(z + 1) - 1], fill=c, outline=(20, 110, 140))
    track = metro_track()
    for x, z, f in tube_cells(track): dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=(170, 215, 240, 220))
    for a, b in zip(track, track[1:]):
        dr.line([px(a[0]) + S // 2, pz(a[1]) + S // 2, px(b[0]) + S // 2, pz(b[1]) + S // 2], fill=(140, 60, 20), width=2)
    dr.rectangle([px(ST_N[0]), pz(ST_N[2]), px(ST_N[1] + 1), pz(ST_N[3] + 1)], fill=(240, 238, 232, 200), outline=(140, 60, 20), width=2)
    for x, z in ST_STAIR: dr.rectangle([px(x), pz(z), px(x + 1) - 1, pz(z + 1) - 1], fill=(200, 120, 60, 160))
    for bx, bz, _ in BOATS: dr.ellipse([px(bx) - 5, pz(bz) - 3, px(bx) + 5, pz(bz) + 3], fill=(160, 40, 40))
    lab = [(-782, 1944, 'КУПОЛ Ø 31, верх 65\nсад, смотровой обход'), (-752, 1952, 'станция «Купол»'), (-752, 1901, 'павильон'),
           (-752, 1918, 'галерея-лестница\n64 → 53'), (-768, 1909, 'остров A'), (-771, 1886, 'мыс, маяк'),
           (-739, 1880, 'марина: лодки'), (-697, 1905, 'ветка метро 2\nстеклянная труба\nна дне, ноги 53'),
           (-735, 1944, 'впадина — труба на опорах'), (-728, 1852, 'ст. «Набережная»\nноги 57, вход с променада'),
           (-695, 1862, 'площадь'), (-698, 1878, 'пирс')]
    for x, z, t in lab: dr.text((px(x), pz(z)), t, fill='black', font=F(11), stroke_width=3, stroke_fill='white')
    for x in range(X0, X1 + 1, 10): dr.text((px(x) - 10, 12), str(x), fill='black', font=F(10))
    for z in range(1850, Z1 + 1, 10): dr.text((2, pz(z) - 6), str(z), fill='black', font=F(10))
    # профиль 1: галерея (по Z), профиль 2: метро (по длине пути)
    def profile(y0, ph, ylow, title, pts, ground, sc=3):
        dr.text((40, y0), title, fill='black', font=F(12))
        base = y0 + ph - 10
        yy = lambda y: base - (y - ylow) * sc
        dr.line([40, yy(SEA), 40 + len(pts) * sc, yy(SEA)], fill=(40, 120, 200), width=1)
        dr.text((42 + len(pts) * sc, yy(SEA) - 6), 'вода 62', fill=(40, 120, 200), font=F(10))
        for i, (g, f) in enumerate(zip(ground, pts)):
            dr.rectangle([40 + i * sc, yy(g), 40 + (i + 1) * sc - 1, yy(ylow)], fill=(150, 130, 100))
            dr.rectangle([40 + i * sc, yy(f + 3), 40 + (i + 1) * sc - 1, yy(f) - 1], fill=(170, 215, 240), outline=(20, 110, 140))
    gz = sorted(gal)
    profile(mh + 50, PH1, 44, 'Профиль: павильон (64) → галерея-лестница → купол (53), по Z 1910…1939, ×8',
            [gal[z] for z in gz], [W.ground(-754, z) for z in gz], sc=8)
    profile(mh + 50 + PH1 + 20, PH2, 30, 'Профиль метро: «Набережная» (57) → рампа 1:1 → труба по дну (53) → поворот у Z 1948 → «Купол», ×3',
            [f for _, _, f in track], [W.ground(x, z) for x, z, _ in track], sc=3)
    os.makedirs(os.path.dirname(out), exist_ok=True); img.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'districts', 'dome-plan-v1.png'))
    a = ap.parse_args()
    W = World(ext=True)
    errs = checks(W)
    neg = negatives(W)
    for name, failed, e in neg:
        print(f'негатив «{name}»: ' + ('ловит' if failed else 'НЕ ЛОВИТ') + (f' ({e[0]})' if e else ''))
        if not failed: errs.append(f'негатив «{name}» не ловит')
    draw(W, a.out)
    print('ОШИБКИ:\n  ' + '\n  '.join(errs) if errs else 'проверки плана чистые')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
