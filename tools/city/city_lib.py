"""Общие функции генераторов башен Сити (этапы 5–7): этажи-призмы по форме плана, фасад,
перекрытия, свет, стремянки (автоматически — к каждой части каждого этажа), электрощитовая и
серверная МЭ с кабельной шахтой, двери, дорожки с высотами (шаг 0.5), проверки.

    from city_lib import *
"""
import math
import os
import sys
from collections import deque

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO, BUILT, built_before  # noqa: E402,F401
from oldtown_lib import door_approach_issues, floating_over_paving, col, CL  # noqa: E402,F401
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
LADDER_META = {(0, -1): 3, (0, 1): 2, (-1, 0): 5, (1, 0): 4}   # стремянка крепится к блоку со стороны (dx, dz)
DOOR_IN = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}       # meta двери -> внутрь
PAVE = {'double_stone_slab', 'stone_slab', 'quartz_block', 'glass', 'stonebrick', 'concrete', 'sandstone'}


def pave_top(W, x, z):
    """Ходовой уровень построенного мощения (улицы, площади): пропускает фонари, деревья, скамейки."""
    for y in range(W.surf(x, z) + 2, W.surf(x, z) - 8, -1):
        b = W.block(x, y, z)
        n, m = (b.split(':') + ['0'])[:2]
        if b == 'quartz_block:1' or (b == 'stone_slab:7' and W.block(x, y - 1, z) == 'sea_lantern'): continue
        if n in PAVE or (n == 'stone' and m in ('4', '5', '6')):
            half = n == 'stone_slab' and int(m) < 8
            return y + (0.5 if half else 1.0)
        if b in ('ground', 'grass') or 'water' in b: return None
    return None


class Tower:
    """Башня по форме occ(x, y, z) в габарите box=(x0, x1, z0, z1): перекрытия f0, f0+4, … (не выше top−5),
    кровля — top. Фасадные клетки, за которыми грунт выше пола, — бетон, а не стекло."""

    def __init__(self, W, name, occ, box, f0, top, glass='stained_glass:3', band='concrete:0', floor='concrete:0',
                 lobby='quartz_block', roof_walk=False, glass_fn=None, exact=False):
        self.W, self.name, self.occ, self.box, self.f0, self.top = W, name, occ, box, f0, top
        self.glass, self.band, self.floor, self.lobby, self.roof_walk = glass, band, floor, lobby, roof_walk
        self.glass_fn, self.exact = glass_fn, exact
        ys = []
        y = f0
        while y <= top - 5: ys.append(y); y += 4
        ys.append(top)
        self.ys = ys                           # перекрытия: ys[0] — пол 1-го этажа, ys[-1] — кровля
        x0, x1, z0, z1 = box
        self.FP = []
        for k in range(len(ys) - 1):
            ym = (ys[k] + ys[k + 1]) // 2
            self.FP.append({(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if occ(x, ym, z)})
        self.cells = {}
        self.reserved = set()                  # клетки (x, z) этажа 0 (двери) — не для стремянок
        self.res_k = {}                        # этаж -> клетки комнат (x, z)
        self.doors, self.ladders, self.rooms, self.targets = [], [], [], {}

    def put(self, x, y, z, b): self.cells[(x, y, z)] = b

    def storeys(self): return len(self.ys) - 1

    def shell(self):
        if self.exact: return self.shell_exact()
        W, put = self.W, self.put
        FP, ys = self.FP, self.ys
        for (x, z) in FP[0]:                   # основание: камень от грунта до пола
            for y in range(W.surf(x, z) + 1, self.f0): put(x, y, z, 'stone')
        for k in range(self.storeys()):
            slab = FP[k] | (FP[k - 1] if k else set())
            for (x, z) in slab:
                edge = any((x + a, z + b) not in slab for a, b in N4)
                put(x, ys[k], z, self.band if edge else (self.lobby if k == 0 else self.floor))
            for (x, z) in FP[k]:
                edge = [(x + a, z + b) for a, b in N4 if (x + a, z + b) not in FP[k]]
                for y in range(ys[k] + 1, ys[k + 1]):
                    if edge:
                        buried = any(W.surf(*n) >= y for n in edge)
                        g = self.glass_fn(x, y, z) if self.glass_fn else self.glass
                        put(x, y, z, self.band if buried else g)
                    else:
                        put(x, y, z, 'air')
        last = FP[-1]
        for (x, z) in last:                    # кровля и парапет
            put(x, self.top, z, self.band)
            if any((x + a, z + b) not in last for a, b in N4): put(x, self.top + 1, z, 'stone_slab:7')
        # свет: морские фонари в перекрытиях сеткой 4×4
        for k in range(1, self.storeys()):
            both = FP[k] & FP[k - 1]
            for (x, z) in both:
                if x % 4 == 0 and z % 4 == 0 and all((x + a, z + b) in both for a, b in N4):
                    put(x, ys[k], z, 'sea_lantern')
        for (x, z) in FP[0]:
            if x % 4 == 0 and z % 4 == 0 and all((x + a, z + b) in FP[0] for a, b in N4) and self.storeys() == 1:
                put(x, self.top, z, 'sea_lantern')

    def shell_exact(self):
        """Оболочка точно по форме на каждой высоте (кривые — кольцо, спираль, наклон): грань сбоку —
        стекло, верх/низ сечения — бетон, на уровнях перекрытий внутри — пол, остальное — воздух."""
        W, put = self.W, self.put
        x0, x1, z0, z1 = self.box
        sec = {y: {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if self.occ(x, y, z)}
               for y in range(self.f0, self.top + 1)}
        sec[self.f0] |= self.FP[0]
        self.sec = sec
        slabs = set(self.ys)
        for (x, z) in sec[self.f0]:
            for y in range(W.surf(x, z) + 1, self.f0): put(x, y, z, 'stone')
        for y in range(self.f0, self.top + 1):
            cur, up, dn = sec[y], sec.get(y + 1, set()), sec.get(y - 1, set())
            for (x, z) in cur:
                side = [(x + a, z + b) for a, b in N4 if (x + a, z + b) not in cur]
                if y in slabs or (x, z) not in up or (x, z) not in dn:
                    if y == self.f0: put(x, y, z, self.band if side else self.lobby)
                    elif y in slabs and not side and (x, z) in up: put(x, y, z, self.floor)
                    else: put(x, y, z, self.band)
                elif side:
                    buried = any(W.surf(*n) >= y for n in side)
                    put(x, y, z, self.band if buried else (self.glass_fn(x, y, z) if self.glass_fn else self.glass))
                else:
                    put(x, y, z, 'air')
        top = sec[self.top]
        for (x, z) in top:
            if any((x + a, z + b) not in top for a, b in N4): put(x, self.top + 1, z, 'stone_slab:7')
        for k in range(1, self.storeys()):
            y = self.ys[k]
            for (x, z) in sec[y]:
                if x % 4 == 0 and z % 4 == 0 and all((x + a, z + b) in sec[y] and (x + a, z + b) in sec[y + 1] for a, b in N4):
                    put(x, y, z, 'sea_lantern')

    def door(self, x, z, meta, kind='birch_door'):
        """Наружная дверь на 1-м этаже (в фасадной клетке), плита изнутри."""
        y = self.f0 + 1
        self.put(x, y, z, f'{kind}:{meta}'); self.put(x, y + 1, z, f'{kind}:8')
        ix, iz = x + DOOR_IN[meta][0], z + DOOR_IN[meta][1]
        self.put(ix, y, iz, 'stone_pressure_plate')
        self.doors.append((x, y, z, meta)); self.reserved |= {(x, z), (ix, iz)}

    def room(self, name, rect, door, k=0, shaft=None, opening=None):
        """Комната rect=(x0, x1, z0, z1) (внутренность) на этаже k: стены из белого бетона по кольцу вокруг
        (кроме фасада), дверь door=(x, z, meta) в стене, плиты с обеих сторон; shaft=(x, z) — кабельная шахта
        1×1 от Y 60 с люком iron_trapdoor:8 в полу; opening=[(x, y_ofs, z)] — проёмы 1×1 в стенах."""
        x0, x1, z0, z1 = rect
        y0 = self.ys[k]
        ring = {(x, z) for x in range(x0 - 1, x1 + 2) for z in range(z0 - 1, z1 + 2)} - \
            {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
        fpk = self.FP[k]
        for (x, z) in ring:
            if (x, z) in fpk and all((x + a, z + b) in fpk for a, b in N4):
                for y in range(y0 + 1, y0 + 4): self.put(x, y, z, self.band)
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                for y in range(y0 + 1, y0 + 4): self.put(x, y, z, 'air')
                self.res_k.setdefault(k, set()).add((x, z))
        dx_, dz_, meta = door
        self.put(dx_, y0 + 1, dz_, f'birch_door:{meta}'); self.put(dx_, y0 + 2, dz_, 'birch_door:8')
        a, b = DOOR_IN[meta]
        for s in (1, -1): self.put(dx_ + s * a, y0 + 1, dz_ + s * b, 'stone_pressure_plate')
        self.res_k.setdefault(k, set()).update({(dx_, dz_), (dx_ + a, dz_ + b), (dx_ - a, dz_ - b)} | ring)
        for (ox, oy, oz) in (opening or []): self.put(ox, y0 + oy, oz, 'air')
        if shaft:
            sx, sz = shaft
            bot = max(60, (self.W.cave_top(sx, sz) or 0) + 4)        # дно шахты — не ближе 3 блоков к пустоте
            for y in range(bot, self.ys[0]): self.put(sx, y, sz, 'air')
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    if (a, b) != (0, 0):
                        for y in range(bot - 1, self.ys[0]):
                            kk = (sx + a, y, sz + b)
                            if self.cells.get(kk, self.W.block(*kk)) in ('air', 'plant', 'water'): self.put(*kk, 'stonebrick')
            for kk in range(k + 1):
                self.put(sx, self.ys[kk], sz, 'iron_trapdoor:8')
        self.rooms.append((name, rect, k))
        self.targets[name] = ((x0 + x1) // 2, y0 + 1, (z0 + z1) // 2)

    def walk_fp(self, k):
        """Клетки этажа k, где есть пол и высота для человека (у точной оболочки — по сечениям)."""
        if k >= self.storeys(): return set(self.FP[-1]) if not self.exact else set(self.sec[self.top])
        if not self.exact: return set(self.FP[k])
        y = self.ys[k]
        return self.sec[y] & self.sec.get(y + 1, set()) & self.sec.get(y + 2, set())

    def plan_ladders(self):
        """Стремянки: каждая связная часть каждого этажа (и кровля при roof_walk) — от достигнутой части
        этажа ниже; предпочтение — продолжать ту же колонну. Возвращает число недостижимых частей."""
        FP, ys = self.FP, self.ys
        levels = [self.walk_fp(k) for k in range(self.storeys())]
        if self.roof_walk: levels.append(self.walk_fp(self.storeys()))
        interior = lambda s: {c for c in s if all((c[0] + a, c[1] + b) in s for a, b in N4)}

        def comps(s):
            s = set(s); out = []
            while s:
                c = s.pop(); q = [c]; comp = {c}
                while q:
                    p = q.pop()
                    for a, b in N4:
                        n = (p[0] + a, p[1] + b)
                        if n in s: s.remove(n); comp.add(n); q.append(n)
                out.append(comp)
            return out
        reached = {0: set()}
        for c in comps(interior(levels[0])):
            if any((d[0] + DOOR_IN[d[3]][0], d[2] + DOOR_IN[d[3]][1]) in c for d in self.doors): reached[0] |= c
        cols = []
        lost = 0
        for k in range(1, len(levels)):
            reached[k] = set()
            below = reached[k - 1] & interior(levels[k - 1])
            for c in comps(interior(levels[k])):
                cand = []
                rb = self.res_k.get(k - 1, set()) | (self.reserved if k == 1 else set())
                ra = rb | self.res_k.get(k, set())
                for (x, z) in c:
                    if (x, z) not in below or (x, z) in ra or (x, z) in self.ladders: continue
                    for (a, b) in N4:
                        att = (x + a, z + b)
                        if att in levels[k - 1] and att in levels[k] and att not in ra and att not in cols:
                            cand.append(((0 if (x, z) in cols else 1), abs(x - sum(p[0] for p in c) / len(c)) +
                                         abs(z - sum(p[1] for p in c) / len(c)), x, z, a, b))
                if not cand: lost += 1; continue
                _, _, x, z, a, b = min(cand)
                y_lo, y_hi = ys[k - 1] + 1, ys[k]
                for y in range(y_lo, y_hi + 1):
                    self.put(x + a, y, z + b, self.band)
                    self.put(x, y, z, f'ladder:{LADDER_META[(a, b)]}')
                self.ladders.append((x + a, z + b)); cols.append((x, z))
                reached[k] |= c
        self.reached = reached
        return lost

    def level_targets(self):
        """Цели проходимости: по клетке в каждой связной части каждого этажа."""
        FP, ys = self.FP, self.ys
        out = {}
        levels = [(k, self.walk_fp(k), ys[k]) for k in range(self.storeys())]
        if self.roof_walk: levels.append((self.storeys(), self.walk_fp(self.storeys()), self.top))
        for k, f, y in levels:
            inner = {c for c in f if all((c[0] + a, c[1] + b) in f for a, b in N4)}
            s = set(inner); i = 0
            while s:
                c = min(s); q = [c]; comp = {c}; s.discard(c)
                while q:
                    p = q.pop()
                    for a, b in N4:
                        n = (p[0] + a, p[1] + b)
                        if n in s: s.remove(n); comp.add(n); q.append(n)
                free = [p for p in sorted(comp) if self.cells.get((p[0], y + 1, p[1]), 'air') == 'air'
                        and self.cells.get((p[0], y, p[1]), '').split(':')[0] not in ('ladder', 'iron_trapdoor')]
                if free: out[f'{self.name}: этаж {k}' + (f', часть {i + 1}' if i else '')] = (free[0][0], y + 1, free[0][1])
                i += 1
        return out


def path_heights(W, cells, fixed, skip=()):
    """Высоты дорожек (шаг 0.5): сглаженный рельеф, стык с построенным мощением и порогами дверей
    (fixed {(x, z): h}) — не больше 0.5 на клетку; только опускание, затем проверка."""
    cells = set(cells)
    anchors = dict(fixed)
    for c in cells:
        for a, b in N4:
            n = (c[0] + a, c[1] + b)
            if n in cells or n in anchors or n in skip: continue
            t = pave_top(W, *n)
            if t is not None: anchors[n] = t
    H = {c: round((W.surf(*c) + 1) * 2) / 2 for c in cells if c not in fixed}
    for c, h in fixed.items():
        if c in cells: H[c] = h
    for _ in range(4):
        H = {c: (H[c] if c in fixed else round((H[c] * 2 + sum(H.get((c[0] + a, c[1] + b), H[c]) for a, b in N4)) / 6 * 2) / 2)
             for c in H}
    for a, h0 in anchors.items():                   # конусы от якорей
        d = {a: 0}; q = deque([a])
        while q:
            p = q.popleft()
            for u, v in N4:
                n = (p[0] + u, p[1] + v)
                if n in H and n not in d: d[n] = d[p] + 1; q.append(n)
        for c, k in d.items():
            if c in H and c not in fixed: H[c] = min(max(H[c], h0 - 0.5 * k), h0 + 0.5 * k)
    for _ in range(300):
        ch = False
        for c in H:
            if c in fixed: continue
            m = min([H[(c[0] + a, c[1] + b)] + 0.5 for a, b in N4 if (c[0] + a, c[1] + b) in H] +
                    [anchors[(c[0] + a, c[1] + b)] + 0.5 for a, b in N4 if (c[0] + a, c[1] + b) in anchors])
            if H[c] > m: H[c] = m; ch = True
        if not ch: break
    for _ in range(300):                             # подъём к фиксированным (пороги дверей) — не ниже соседа − 0.5
        ch = False
        for c in H:
            if c in fixed: continue
            nb = [H[(c[0] + a, c[1] + b)] for a, b in N4 if (c[0] + a, c[1] + b) in H] + \
                 [anchors[(c[0] + a, c[1] + b)] for a, b in N4 if (c[0] + a, c[1] + b) in anchors and (c[0] + a, c[1] + b) not in H]
            lo, hi = max(nb) - 0.5, min(nb) + 0.5
            if lo <= hi and H[c] < lo: H[c] = lo; ch = True
        if not ch: break
    bad = [(c, n) for c in H for a, b in N4 for n in [(c[0] + a, c[1] + b)]
           if (n in H and abs(H[c] - H[n]) > 0.5) or (n in anchors and n not in H and abs(H[c] - anchors[n]) > 0.5)]
    return H, anchors, bad


def pave_cells(W, cells, H, full='double_stone_slab:8', slab='stone_slab', out=None):
    out = {} if out is None else out
    for (x, z), h in H.items():
        g = W.surf(x, z)
        top = int(h) - 1 if h == int(h) else int(h)
        if h == int(h): out[(x, top, z)] = full
        else: out[(x, top - 1, z)] = full; out[(x, top, z)] = slab
        for y in range(g + 1, top - (0 if h == int(h) else 1)): out[(x, y, z)] = 'stone'
        y = top + 1
        while y <= max(g, top) + 4 and (y <= g or W.block(x, y, z) == 'plant'): out[(x, y, z)] = 'air'; y += 1
    return out


def save_schema(cells, out):
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    o = (min(xs), min(ys), min(zs))
    rel = {(x - o[0], y - o[1], z - o[2]): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, out, order)
    return o, rel, order, (max(xs) - o[0] + 1, max(ys) - o[1] + 1, max(zs) - o[2] + 1)
