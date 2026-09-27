"""Модель мира участка для генераторов города: рельеф docs/terrain/site.json +
все построенные на сервере схемы (в порядке постройки) + кровля каньона.

Единый реестр построенного - BUILT. Новые генераторы берут мир отсюда, а не
держат свой список (в генераторах набережной и мыса список исторически свой).
После постройки новой схемы на сервере - добавить её в BUILT (как построено:
если владелец правил на месте - сначала привести схему к построенному, см.
docs/HANDOFF.md, «Ручные правки»).

    from world_model import World
    W = World()
    W.block(x, y, z)   # 'ground' | 'water' | 'plant' | 'air' | имя блока схемы
    W.surf(x, z)       # верх твёрдого (не вода/трава)
    W.cave_top(x, z)   # верхняя оценка кровли каньона или None
"""
import json
import os

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

# (схема, origin) - в порядке постройки на сервере. 1b/1c не входят: их результат целиком перекрыт 1d.
BUILT = (
    ('embankment-1-earthworks.json', (-776, 56, 1847)),
    ('embankment-1d-beach-rebuild.json', (-756, 47, 1860)),
    ('embankment-2-promenade.json', (-775, 63, 1848)),
    ('decor-fountain-13-med.json', (-696, 64, 1852)),     # v2; на месте доработан вручную (DECOR.md §5.2)
    ('embankment-3-pier-cafe.json', (-713, 48, 1869)),
    ('embankment-4-ferris-wheel.json', (-685, 62, 1862)),
    ('cape-1-earthworks.json', (-778, 56, 1874)),
    ('cape-2-5-build.json', (-792, 60, 1859)),            # как построено, включая fix-2 и fix-3
    ('oldtown-1-earthworks.json', (-706, 60, 1780)),
)


class World:
    def __init__(self, built=BUILT, repo=REPO):
        d = json.load(open(os.path.join(repo, 'docs', 'terrain', 'site.json')))
        self._d = d
        self._W, self._X0, self._Z0 = d['w'], d['x0'], d['z0']
        self._cv = json.load(open(os.path.join(repo, 'docs', 'terrain', 'caves.json')))
        self.pre = {}
        for fn, o in built:
            for e in json.load(open(os.path.join(repo, 'schemas', fn))):
                self.pre[(e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])] = e['block']

    def _i(self, x, z): return (z - self._Z0) * self._W + x - self._X0

    def ground(self, x, z): return self._d['ground'][self._i(x, z)]

    def water(self, x, z): return self._d['water'][self._i(x, z)]

    def block(self, x, y, z):
        if (x, y, z) in self.pre: return self.pre[(x, y, z)]
        i = self._i(x, z); g = self._d['ground'][i]; w = self._d['water'][i]; t = self._d['top'][i]
        if y <= g: return 'ground'
        if w is not None and y <= w: return 'water'
        if t is not None and g < y <= t: return 'plant'
        return 'air'

    @staticmethod
    def solid(b): return b not in ('air', 'water', 'plant') and not b.startswith('flowing_water')

    def surf(self, x, z, ymax=120, ymin=20):
        for y in range(ymax, ymin, -1):
            if self.solid(self.block(x, y, z)): return y

    def cave_top(self, x, z):
        c = self._cv; i = (z - c['z0']) * c['w'] + x - c['x0']
        a, m = c['air'][i] or 0, c['minAir'][i]
        return m + a - 1 if a and m is not None else None


if __name__ == '__main__':
    W = World()
    print('построенных схем', len(BUILT), '| блоков в модели', len(W.pre))
    print('проверка: маяк', W.block(-771, 93, 1888), '| пирс', W.block(-690, 64, 1875), '| рельеф (-740,1800)', W.surf(-740, 1800))
