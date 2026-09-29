"""Общие функции генераторов Старого города (этапы 4+): мощение квартала по улицам,
стандартные проверки, превью, исправляющая схема (--fix-from).

    from oldtown_lib import *
"""
import json
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO, built_before  # noqa: E402,F401
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

LAMP_PARTS = ('quartz_block:1', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')
RESERVE = lambda x, z: -696 <= x <= -684 or 1812 <= z <= 1820      # резерв трасс, CITY.md §7.3
DOOR_PLATE = {'stone': 'stone_pressure_plate', 'wood': 'wooden_pressure_plate'}


def street_top(W, x, z):
    """Верх покрытия построенной улицы/площади (без фонарей) или None для грунта и воды."""
    y = W.surf(x, z)
    b = W.block(x, y, z)
    while b in LAMP_PARTS: y -= 1; b = W.block(x, y, z)
    if b in ('ground', 'grass') or b.startswith('water') or W.block(x, y + 1, z) == 'water': return None
    slab = b.split(':')[0] in ('stone_slab', 'wooden_slab', 'stone_slab2') and int((b.split(':') + ['0'])[1]) < 8
    return y + (0.5 if slab else 1.0)


def paving_heights(W, cells, base=65.0, extra_anchors=None, ring=None):
    """Высоты мощения (шаг 0.5): base, стянутая конусами (0.5 на клетку) к соседним построенным
    улицам и к extra_anchors {(x,z): h}. ring — где искать улицы (по умолчанию 1 клетка вокруг)."""
    cells = set(cells)
    anchors = dict(extra_anchors or {})
    look = ring or {(x + a, z + b) for x, z in cells for a in (-1, 0, 1) for b in (-1, 0, 1)} - cells
    for c in look:
        if c in anchors: continue
        t = street_top(W, *c)
        if t is not None: anchors[c] = t
    H = {}
    for c in cells:
        lo = max(a - 0.5 * (abs(c[0] - p[0]) + abs(c[1] - p[1])) for p, a in anchors.items())
        hi = min(a + 0.5 * (abs(c[0] - p[0]) + abs(c[1] - p[1])) for p, a in anchors.items())
        H[c] = min(max(base, lo), hi)
    return H, anchors


class Schema:
    """Накопитель блоков в абсолютных координатах поверх мира W."""
    def __init__(self, W):
        self.W = W; self.cells = {}

    def put(self, x, y, z, b): self.cells[(x, y, z)] = b

    def plant_top(self, x, z):
        y = self.W.surf(x, z) + 1
        while self.W.block(x, y, z) == 'plant': y += 1
        return y - 1

    def pave(self, H, mat):
        """Мощение по высотам H; mat(x, z) -> (полный блок, полублок)."""
        for (x, z), h in H.items():
            g = self.W.surf(x, z); full, slab = mat(x, z)
            if h == int(h):
                ty = int(h) - 1
                for y in range(g + 1, ty): self.put(x, y, z, 'stone')
                self.put(x, ty, z, full); top = ty
            else:
                k = int(h)
                for y in range(g + 1, k - 1): self.put(x, y, z, 'stone')
                self.put(x, k - 1, z, full); self.put(x, k, z, slab); top = k
            for y in range(top + 1, max(self.plant_top(x, z), g) + 1): self.put(x, y, z, 'air')

    def ground_to(self, x, z, y_top, top_block):
        """Грунт/фундамент колонны до y_top (включительно), сверху top_block, выше — расчистка."""
        g = self.W.surf(x, z)
        for y in range(g + 1, y_top): self.put(x, y, z, 'stone')
        self.put(x, y_top, z, top_block)
        for y in range(y_top + 1, max(self.plant_top(x, z), g) + 1): self.put(x, y, z, 'air')

    def gable_x(self, x0, x1, z0, z1, y0, mat='brick_stairs', skip=lambda x, z: False):
        """Двускатная кровля, конёк вдоль Z: ряды ступенек от X-краёв к середине, начиная с y0."""
        w = x1 - x0 + 1
        for i in range((w + 1) // 2):
            for z in range(z0, z1 + 1):
                for x, m in ((x0 + i, 0), (x1 - i, 1)):
                    if not skip(x, z): self.put(x, y0 + i, z, f'{mat}:{m}')
        return (w + 1) // 2

    def gable_z(self, x0, x1, z0, z1, y0, mat='brick_stairs', skip=lambda x, z: False):
        """Двускатная кровля, конёк вдоль X."""
        w = z1 - z0 + 1
        for i in range((w + 1) // 2):
            for x in range(x0, x1 + 1):
                for z, m in ((z0 + i, 2), (z1 - i, 3)):
                    if not skip(x, z): self.put(x, y0 + i, z, f'{mat}:{m}')
        return (w + 1) // 2

    def door(self, x, y, z, meta, kind='wooden_door', hinge=8):
        self.put(x, y, z, f'{kind}:{meta}'); self.put(x, y + 1, z, f'{kind}:{hinge}')


def save(sch, out):
    cells = sch.cells
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    o = (min(xs), min(ys), min(zs))
    rel = {(x - o[0], y - o[1], z - o[2]): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, out, order)
    print('origin', *o, '| габарит', max(xs) - o[0] + 1, max(ys) - o[1] + 1, max(zs) - o[2] + 1, '| записей', len(cells))
    return o, rel, order


def fns(W, cells, o):
    def final(x, y, z):
        b = cells.get((x, y, z)) or W.block(x, y, z)
        return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)

    def terrain_rel(x, y, z):
        b = W.block(x + o[0], y + o[1], z + o[2])
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
    return final, terrain_rel


def std_checks(W, cells, o, rel, order, H, anchors):
    final, terrain_rel = fns(W, cells, o)
    errs = dl.check_water(rel, terrain_rel)
    se, wr = dl.check_supports(rel, order, terrain_rel)
    print('опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок', len(errs) + len(se), '| предупреждений', len(wr))
    for m in (errs + se + wr)[:10]: print('  ', m)
    be = dl.check_bench_front(rel, terrain_rel)
    print('скамейки (место для ног): ошибок', len(be), be[:3])
    jump = sum(1 for c in H for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1)) if n in H and abs(H[c] - H[n]) > 0.5)
    edge = sum(1 for c in H for a in anchors if abs(c[0] - a[0]) + abs(c[1] - a[1]) == 1 and abs(H[c] - anchors[a]) > 0.5)
    print('мощение: клеток', len(H), dict(sorted(Counter(H.values()).items())), '| перепад соседей > 0.5 —', jump, '| со стыком улиц > 0.5 —', edge)
    fl = floating_over_paving(final, cells, H)
    print('висящие над мощением (под предметом воздух или нижний полублок):', len(fl), fl[:6])
    lo = {}
    for (x, y, z) in cells: lo[(x, z)] = min(lo.get((x, z), 999), y)
    roofs = [y - W.cave_top(x, z) - 1 for (x, z), y in lo.items() if W.cave_top(x, z) is not None]
    print('кровля каньона под схемой: мин.', min(roofs) if roofs else '—', '(норма >= 3) | в резерве трасс ниже Y 60 —',
          sum(1 for k, b in cells.items() if b != 'air' and k[1] < 60 and RESERVE(k[0], k[2])))
    return final


def floating_over_paving(final, cells, H):
    """Предметы на мощении (скамейки, урны, колонны, фонари, кашпо, прилавки): блок схемы над
    мощением, под которым воздух или нижний полублок — висит (так было у библиотеки v1)."""
    import math
    out = []
    for (x, z), h in H.items():
        top = math.ceil(h) - 1                       # верхний блок мощения (полный или полублок)
        for y in range(top + 1, top + 3):             # стоит на мощении или висит на 1 блок выше (навесы выше — не в счёт)
            b = cells.get((x, y, z))
            if not b or b == 'air': continue
            below = final(x, y - 1, z)
            nm, meta = (below.split(':') + ['0'])[:2]
            half = nm in ('stone_slab', 'wooden_slab', 'stone_slab2') and int(meta) < 8
            if below == 'air' or half: out.append((x, y, z, b))
            break
    return out


def base_y(S, H, x, z, block='stonebrick'):
    """Y для предмета на мощении: на полном блоке — над ним; на полублоке — полублок заменяется
    полным блоком, предмет ставится на него."""
    h = H[(x, z)]
    if h == int(h): return int(h)
    S.put(x, int(h), z, block)
    return int(h) + 1


DOOR_OUT = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}      # meta двери (открывается внутрь) -> наружу
STAIR_UP = {(0, -1): 3, (0, 1): 2, (-1, 0): 1, (1, 0): 0}      # ступенька «вверх» в направлении (dx, dz)


def _top(final, x, z, y_hi):
    """Верх ходовой поверхности клетки не выше y_hi: (высота, блок)."""
    for y in range(y_hi, y_hi - 6, -1):
        b = final(x, y, z)
        if b in ('air', 'plant') or b.endswith('pressure_plate'): continue
        nm, meta = (b.split(':') + ['0'])[:2]
        half = nm in ('stone_slab', 'wooden_slab', 'stone_slab2') and int(meta) < 8
        return y + (0.5 if half else 1.0), b
    return None, None


def door_approach_issues(final, doors):
    """Наружные двери: клетка перед дверью — мощение вровень с порогом или ступенька (stairs вверх к
    двери); за ней — мощение не выше ступени и без бордюра/газона. doors — [(x, y, z, meta)]."""
    out = []
    for x, y, z, m in doors:
        dx, dz = DOOR_OUT[m]
        c1 = (x + dx, z + dz); c2 = (x + 2 * dx, z + 2 * dz)
        if any(final(c1[0], yy, c1[1]) not in ('air', 'plant') for yy in range(y + 2, y + 8)): continue   # под навесом
        t1, b1 = _top(final, c1[0], c1[1], y)
        nm = (b1 or '').split(':')[0]
        stair_ok = nm.endswith('_stairs') and b1 == f"{nm}:{STAIR_UP[(-dx, -dz)]}" and t1 == y
        if b1 in ('ground', 'grass', 'dirt', None): out.append(((x, y, z), 'перед дверью газон/грунт')); continue
        if not (t1 == y or stair_ok): out.append(((x, y, z), f'перед дверью {t1 - y:+} — не вровень и не ступенька')); continue
        tread = y - 0.5 if stair_ok else y
        t2, b2 = _top(final, c2[0], c2[1], y + 1)
        if b2 in ('ground', 'grass', 'dirt', None) or t2 > tread + 0.5 or t2 < tread - 1:
            out.append(((x, y, z), f'за ступенью {b2} {t2}'))
    return out


def outdoor_doors(final, cells):
    return [(x, y, z, int(b.split(':')[1])) for (x, y, z), b in cells.items()
            if b.split(':')[0].endswith('_door') and int(b.split(':')[1]) < 8]


def door_approach(S, final, door, meta, L, end_top=None):
    """Подход к наружной двери: L клеток наружу от порога — ступеньки (по 1 блоку) и мощение вровень,
    до клетки L+1 (улица). Бордюр/газон/трава на пути убираются."""
    x, y, z = door
    dx, dz = DOOR_OUT[meta]
    ex, ez = x + (L + 1) * dx, z + (L + 1) * dz
    tE, bE = (end_top, None) if end_top is not None else _top(final, ex, ez, y + 1)
    cobble = (bE or '').split(':')[0] in ('cobblestone', 'mossy_cobblestone', 'stone_slab') and (bE or '').startswith(('cobble', 'mossy', 'stone_slab:3'))
    stair, full = ('stone_stairs', 'cobblestone') if cobble else ('stone_brick_stairs', 'stonebrick')
    cur = y
    for i in range(1, L + 1):
        cx, cz = x + i * dx, z + i * dz
        g = S.W.surf(cx, cz)
        if cur - tE >= 0.5:
            S.put(cx, cur - 1, cz, f'{stair}:{STAIR_UP[(-dx, -dz)]}'); base = cur - 2; nxt = cur - 1
        else:
            S.put(cx, cur - 1, cz, full); base = cur - 2; nxt = cur
        for yy in range(min(g + 1, base + 1), base + 1):
            if final(cx, yy, cz) in ('air', 'plant', 'water'): S.put(cx, yy, cz, 'stone')
        for yy in range(cur, cur + 3): S.put(cx, yy, cz, 'air')
        cur = nxt


def pave_unreached(S, H, seen):
    """Клетки мощения без стоянки на их высоте; клетки, занятые декором над мощением, не считаются."""
    import math
    out = []
    for (x, z), h in H.items():
        if any(S.cells.get((x, y, z), 'air') != 'air' for y in range(math.ceil(h), math.ceil(h) + 3)): continue
        if not dl.reached(seen, x, h, z): out.append((x, z))
    return out


def walk_report(final, start, box, targets):
    seen = dl.walk_reachable(final, start, box[0], box[1], box[2])
    bad = 0
    for k, (x, y, z) in targets.items():
        ok = dl.reached(seen, x, y, z); bad += 0 if ok else 1
        print(f'  проходимость → {k}: {ok}')
    return seen, bad


def door_plates(sch, doors):
    """Нажимные плиты у дверей изнутри (CITY.md §6): doors — [(x, y, z, (dx, dz) внутрь, материал пола, обе стороны?)]."""
    for x, y, z, (dx, dz), floor, both in doors:
        p = DOOR_PLATE[floor]
        sch.put(x + dx, y, z + dz, p)
        if both: sch.put(x - dx, y, z - dz, p)


def write_fix(W, cells, built_path, built_origin, out, user_edits=None):
    """Исправляющая схема к построенной: блоки проекта, отличающиеся от того, что стоит сейчас
    (построенная схема поверх мира до неё); зоны правок владельца не трогаются."""
    user_edits = user_edits or {}
    old = json.load(open(built_path))
    oldabs = {(e['x'] + built_origin[0], e['y'] + built_origin[1], e['z'] + built_origin[2]): e['block'] for e in old}

    def was(k):
        if k in oldabs: return oldabs[k]
        b0 = W.block(*k)
        return 'air' if b0 in ('air', 'plant') else b0
    fix = {k: b for k, b in cells.items() if was(k) != b and k not in user_edits}
    gone = [k for k in oldabs if k not in cells and k not in user_edits]
    # блоки построенной, которых нет в проекте: где до схемы был воздух — убрать; где грунт —
    # оставить (твёрдое вместо грунта не меняет облика и опор)
    gone_air = [k for k in gone if W.block(*k) in ('air', 'plant') and oldabs[k] != 'air']
    for k in gone_air: fix[k] = 'air'
    left = [k for k in gone if k not in gone_air]
    ok = all((fix.get(k) or user_edits.get(k) or was(k)) == b for k, b in cells.items())
    print('исправление к построенной: блоков', len(fix), dict(Counter(b.split(':')[0] for b in fix.values())),
          '| убрано лишнего:', len(gone_air), '| оставлено вместо грунта:', len(left))
    print('построенная + исправление + правки владельца = текущий проект:', ok)
    if out is False: return fix
    if out and fix:
        fx = [k[0] for k in fix]; fy = [k[1] for k in fix]; fz = [k[2] for k in fix]
        fo = (min(fx), min(fy), min(fz))
        frel = {(x - fo[0], y - fo[1], z - fo[2]): b for (x, y, z), b in fix.items()}
        forder = dl.compute_order(frel)
        dl.save(frel, out, forder)

        def fterr(x, y, z):
            k = (x + fo[0], y + fo[1], z + fo[2])
            b = was(k)
            return 'stone' if b == 'ground' else b
        fe = dl.check_water(frel, fterr); fs, fw = dl.check_supports(frel, forder, fterr)
        print('исправление: origin', *fo, '| записей', len(frel), '| опоры/вода/порядок: ошибок', len(fe) + len(fs), '| предупреждений', len(fw))
    return fix


def save_fix(W, fix, out, was=None):
    """Записать исправляющую схему (абсолютные координаты) и проверить её поверх построенного мира."""
    fx = [k[0] for k in fix]; fy = [k[1] for k in fix]; fz = [k[2] for k in fix]
    fo = (min(fx), min(fy), min(fz))
    frel = {(x - fo[0], y - fo[1], z - fo[2]): b for (x, y, z), b in fix.items()}
    forder = dl.compute_order(frel)
    dl.save(frel, out, forder)

    def fterr(x, y, z):
        k = (x + fo[0], y + fo[1], z + fo[2])
        b = was(k) if was else W.block(*k)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
    fe = dl.check_water(frel, fterr); fs, fw = dl.check_supports(frel, forder, fterr)
    print('исправление: origin', *fo, '| записей', len(frel), '| опоры/вода/порядок: ошибок', len(fe) + len(fs), '| предупреждений', len(fw))


def fix_diff(new_cells, built_rel, built_origin, skip=lambda x, y, z: False):
    """Исправляющая схема: блоки нового варианта, отличающиеся от построенного (абсолютные)."""
    old = {(e['x'] + built_origin[0], e['y'] + built_origin[1], e['z'] + built_origin[2]): e['block'] for e in built_rel}
    out = {}
    for k, b in new_cells.items():
        if skip(*k): continue
        if old.get(k) != b and not (b == 'air' and k not in old and False): out[k] = b
    for k, b in old.items():
        if k not in new_cells and not skip(*k): out[k] = 'air'
    return out


CL = {'stonebrick': (122, 122, 122), 'stone': (125, 125, 125), 'double_stone_slab': (168, 168, 168),
      'stone_slab': (175, 175, 175), 'quartz_block': (236, 233, 226), 'concrete': (228, 228, 228),
      'brick_stairs': (150, 70, 55), 'brick_block': (140, 65, 50), 'stone_slab:4': (150, 70, 55),
      'glass_pane': (190, 220, 235), 'sea_lantern': (215, 240, 235), 'glowstone': (240, 220, 140), 'gold_block': (235, 200, 60),
      'dark_oak_fence': (70, 50, 30), 'fence': (150, 120, 70), 'dark_oak_door': (70, 50, 30), 'wooden_door': (150, 120, 70),
      'birch_stairs': (210, 195, 140), 'trapdoor': (150, 120, 70), 'hardened_clay': (160, 90, 60),
      'leaves': (70, 130, 50), 'grass': (95, 150, 60), 'cauldron': (60, 60, 60), 'iron_bars': (90, 90, 90),
      'ladder': (160, 125, 80), 'stone_brick_stairs': (122, 122, 122), 'iron_trapdoor': (200, 200, 200),
      'concrete:15': (25, 25, 25), 'stone:4': (225, 225, 225), 'stone:6': (140, 145, 145), 'stonebrick:3': (122, 122, 122),
      'wooden_slab': (110, 80, 50), 'spruce_stairs': (110, 80, 50), 'planks': (110, 80, 50), 'sandstone': (218, 208, 160),
      'sandstone_stairs': (218, 208, 160), 'stone_slab:1': (218, 208, 160), 'stained_hardened_clay': (160, 85, 45),
      'wool:11': (50, 60, 160), 'wool:0': (240, 240, 240), 'wool:14': (160, 40, 40), 'wool:1': (230, 130, 40),
      'wool:4': (230, 210, 60), 'wool:5': (110, 180, 40), 'melon_block': (120, 160, 40), 'pumpkin': (220, 140, 30),
      'hay_block': (200, 170, 40), 'log2': (60, 45, 30), 'stained_glass_pane': (160, 120, 200),
      'concrete:5': (100, 170, 25), 'concrete:13': (75, 95, 35), 'wool:13': (85, 110, 30), 'bookshelf': (140, 100, 60),
      'enchanting_table': (60, 30, 40), 'anvil': (60, 60, 60), 'quartz_stairs': (236, 233, 226),
      'water': (70, 130, 215), 'glass': (200, 225, 240), 'birch_door': (215, 200, 150), 'dark_oak_stairs': (70, 50, 30),
      'stone_pressure_plate': (140, 140, 140), 'wooden_pressure_plate': (150, 120, 70), 'flower_pot': (150, 80, 60)}


def col(b):
    if b in CL: return CL[b]
    return CL.get(b.split(':')[0], (185, 180, 172))


def preview(path, final, box, views, title):
    """box — (X0, X1, Z0, Z1) вида сверху; views — [(подпись, fn(u, y) -> блок|None, n_cols, (y0, y1))]."""
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F_ = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    X0, X1, Z0, Z1 = box; S = 10; S2 = 8
    top_w = (X1 - X0 + 1) * S
    widths = [n * S2 for _, _, n, _ in views]
    hmax = max((ys[1] - ys[0] + 1) * S2 for *_, ys in views)
    W_ = 20 + top_w + sum(w + 25 for w in widths)
    img = Image.new('RGB', (W_, max((Z1 - Z0 + 1) * S, hmax) + 50), 'white'); dr = ImageDraw.Draw(img)
    dr.text((10, 4), title, fill='black', font=F_(12))
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 110
            while y > 55 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            c = (130, 160, 90) if b in ('ground', 'stone') else (70, 130, 215) if b == 'water' else col(b)
            dr.rectangle([10 + (x - X0) * S, 22 + (z - Z0) * S, 10 + (x - X0 + 1) * S - 1, 22 + (z - Z0 + 1) * S - 1], fill=c)
    ox = 30 + top_w
    for (label, fn, n, (y0, y1)), w in zip(views, widths):
        dr.text((ox, 22), label, fill='black', font=F_(11))
        for u in range(n):
            for y in range(y0, y1 + 1):
                b = fn(u, y)
                if not b or b == 'air': continue
                yy = 40 + (y1 - y) * S2
                c = (150, 140, 110) if b == 'stone' else col(b)
                n_ = b.split(':')[0]
                half = (n_ in ('stone_slab', 'wooden_slab') and int((b.split(':') + ['0'])[1]) < 8)
                dr.rectangle([ox + u * S2, yy + (S2 // 2 if half else 0), ox + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
        ox += w + 25
    img.save(path)
    print('превью', path)


def elevation(final, axis, fixed, rng, depth_rng):
    """Вид снаружи: axis 'x' — смотрим вдоль X (колонки по Z), 'z' — вдоль Z (колонки по X)."""
    cols = list(rng)

    def fn(u, y):
        c = cols[u]
        for d in depth_rng:
            b = final(d, y, c) if axis == 'x' else final(c, y, d)
            if b not in ('air', 'ground', 'water'): return b
        return None
    return fn, len(cols)


def section(final, axis, fixed, rng):
    cols = list(rng)

    def fn(u, y):
        b = final(fixed, y, cols[u]) if axis == 'x' else final(cols[u], y, fixed)
        return None if b == 'air' else b
    return fn, len(cols)
