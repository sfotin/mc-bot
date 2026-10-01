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
    World(built_before('имя.json'))   # мир до этой схемы — для её генератора
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
    ('oldtown-2-streets.json', (-724, 63, 1780)),
    ('oldtown-1-fix-1.json', (-705, 65, 1799)),         # выход из воды, видимость Соборного пруда
    ('oldtown-3-build.json', (-687, 59, 1819)),         # как построено: v1 + fix-1 + дверь владельца башня → чердак
    ('oldtown-4-market.json', (-687, 59, 1796)),
    ('oldtown-5-tavern.json', (-687, 59, 1838)),
    ('oldtown-3-fix-2.json', (-674, 69, 1821)),         # ратуша без церковных черт
    ('oldtown-6-library.json', (-719, 60, 1792)),       # v1: колонны портика и скамейки висят (исправление oldtown-6-fix-1)
    ('oldtown-7-gallery.json', (-708, 60, 1819)),
    ('oldtown-6-fix-1.json', (-706, 65, 1795)),         # портик Y 66, скамейки на мощении
    ('oldtown-8-k1.json', (-724, 60, 1780)),
    ('oldtown-8-k2.json', (-724, 60, 1792)),
    ('oldtown-8-k3.json', (-724, 60, 1819)),
    ('oldtown-8-k4.json', (-724, 60, 1842)),
    ('oldtown-8-k5.json', (-687, 60, 1780)),
    ('oldtown-8-k6.json', (-675, 60, 1840)),
    ('oldtown-7-fix-1.json', (-707, 65, 1827)),         # ступенька у южной двери, площадка у западной
    ('oldtown-8-fix-1.json', (-722, 64, 1818)),         # подходы к дверям К3, К4, К6
    ('city-1-streets.json', (-800, 64, 1776)),          # Сити, этапы 1–2: улицы
    ('city-1-parks.json', (-799, 52, 1778)),            # Сити, этап 3 (фонтан «Сити» §5.3 — после city-1-fix-1)
    ('city-1-fix-1.json', (-741, 68, 1821)),            # фонтан «Сити» вместо отклонённого
    ('city-4-opener.json', (-766, 60, 1797)),           # Т1 «Открывашка» (плиты у дверей владелец доставил сам)
    ('city-5-gate.json', (-756, 60, 1830)),             # Т2 «Ворота», вертолётная площадка, вертолёт (снят city-8-fix-1)
    ('city-5-bridge.json', (-739, 60, 1795)),           # Т3 «Мост» (Биржа)
    ('city-6-sail.json', (-797, 60, 1821)),             # Т4 «Парус»
    ('city-7-spiral.json', (-785, 60, 1777)),           # Т6 «Спираль»
    ('city-7-decks.json', (-766, 63, 1777)),            # Т7 «Три башни»
    ('city-7-ring.json', (-766, 60, 1843)),             # Т8 «Подкова»
    ('city-6-pebbles.json', (-800, 60, 1793)),          # Т5 «Галька» ×3
    ('city-6-summit.json', (-800, 69, 1782)),           # «Вершина» и шар (шар снят city-8-fix-1)
    ('city-8-fix-1.json', (-800, 158, 1782)),           # Сити, этап 8: снят шар и прежний вертолёт, вертолёт вдвое больше
    ('city-8-balloons.json', (-762, 78, 1793)),         # четыре шара
    ('park-1-ground.json', (-662, 47, 1745)),           # Парк, этап 1: улицы, озеро, аллеи (камыш, кувшинки, лодки — владелец вручную)
    ('park-1-build.json', (-655, 60, 1775)),            # объекты парка
    ('park-2-zoo.json', (-655, 60, 1744)),              # Парк, этап 2: зоопарк (животных владелец поставил сам)
    ('hill-1-ground.json', (-624, 63, 1773)),           # Холм E: проспект до X −593, площадь, лестницы, откосы
    ('hill-1-tower.json', (-617, 60, 1779)),            # телебашня и её внутреннее (стремянки на фонарях колонны отлетели — fix-1)
    ('hill-1-fix-1.json', (-624, 79, 1777)),            # Холм E, исправление: скамейки, рамы дверей, стремянка, свет, стеклянная «тарелка»
    ('mount-1-ground.json', (-624, 70, 1728)),          # Гора F, этап 1 (по съёмке 2026-09-30 отличий 129 бл.: снег на площади,
    ('mount-1-tower.json', (-624, 63, 1758)),           #   часть ротонды и стекла вершины, кровля и южная стена приюта — правки владельца);
    ('mount-1-build.json', (-624, 60, 1735)),           #   концепция отклонена — всё, кроме Горной площади, сносится (CITY.md §7.7, ред. 2)
    ('mount-2-demolish.json', (-626, 60, 1728)),        # Гора F, этап 2: снос этапа 1, забор лам
    ('mount-2-track.json', (-662, 62, 1642)),           # Гора F, этап 2: ледовая трасса 470 бл. (ущелья, тоннели, виадук)
    ('mount-2-start.json', (-610, 77, 1735)),           # Гора F, этап 2: лестница к старту, павильон, трибуна, арка
)
# Ручные правки владельца в Сити после city-1 (не описаны, в модели мира нет) — перед работой рядом уточнить.
# Ручные правки владельца после oldtown-7/8-fix-1 (по скриншотам, блоков нет — в модели мира их нет,
# перед работой рядом уточнить у владельца, docs/HANDOFF.md §1): переулок у южного ряда К3
# X −712…−706, Z 1838…1841; подход к двери там же X −711…−709, Z 1838; подход к двери восточного
# дома К6 у воды X −666…−664, Z 1848…1849 (проход и ограждение от воды).


def built_before(schema):
    """BUILT до схемы schema (не включая её) — мир, в котором схема проектировалась.
    Генератор уже построенной схемы берёт мир отсюда, иначе после добавления
    схемы в BUILT он перестаёт воспроизводить сам себя."""
    names = [b[0] for b in BUILT]
    return BUILT[:names.index(schema)] if schema in names else BUILT


class World:
    def __init__(self, built=BUILT, repo=REPO, ext=False):
        d = json.load(open(os.path.join(repo, 'docs', 'terrain', 'site.json')))
        self._d = d
        self._W, self._X0, self._Z0 = d['w'], d['x0'], d['z0']
        self._cv = json.load(open(os.path.join(repo, 'docs', 'terrain', 'caves.json')))
        # вне участка — съёмка окрестностей горы F (docs/terrain/mount.json, снята 2026-09-30 с построенным;
        # только для колонн вне участка site.json, где ничего не построено). Включается ext=True: генераторы,
        # написанные раньше, читали колонны за краем участка «как есть» (индекс уходил в соседнюю строку) —
        # без ext их поведение не меняется и построенные схемы воспроизводятся.
        self._ext = []
        for tf, cf in (('mount.json', 'mount-caves.json'),):
            tp = os.path.join(repo, 'docs', 'terrain', tf)
            if ext and os.path.exists(tp):
                self._ext.append((json.load(open(tp)), json.load(open(os.path.join(repo, 'docs', 'terrain', cf)))))
        self.pre = {}
        for fn, o in built:
            for e in json.load(open(os.path.join(repo, 'schemas', fn))):
                self.pre[(e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])] = e['block']

    def _i(self, x, z): return (z - self._Z0) * self._W + x - self._X0

    def inside(self, x, z): return 0 <= x - self._X0 < self._W and 0 <= z - self._Z0 < self._d['h']

    def _src(self, x, z):
        """(данные рельефа, индекс колонны, пустоты): участок, иначе съёмка окрестностей; вне всего — ошибка."""
        if self.inside(x, z): return self._d, self._i(x, z), self._cv
        for d, cv in self._ext:
            if 0 <= x - d['x0'] < d['w'] and 0 <= z - d['z0'] < d['h']:
                return d, (z - d['z0']) * d['w'] + x - d['x0'], cv
        if self._ext: raise IndexError(f'нет рельефа для колонны ({x}, {z})')
        return self._d, self._i(x, z), self._cv          # прежнее поведение (без ext)

    def ground(self, x, z): d, i, _ = self._src(x, z); return d['ground'][i]

    def ground_block(self, x, z): d, i, _ = self._src(x, z); return d['groundBlock'][i]

    def top(self, x, z): d, i, _ = self._src(x, z); return d['top'][i]

    def water(self, x, z): d, i, _ = self._src(x, z); return d['water'][i]

    def block(self, x, y, z):
        if (x, y, z) in self.pre: return self.pre[(x, y, z)]
        d, i, _ = self._src(x, z); g = d['ground'][i]; w = d['water'][i]; t = d['top'][i]
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
        _, _, c = self._src(x, z); i = (z - c['z0']) * c['w'] + x - c['x0']
        a, m = c['air'][i] or 0, c['minAir'][i]
        return m + a - 1 if a and m is not None else None


if __name__ == '__main__':
    W = World()
    print('построенных схем', len(BUILT), '| блоков в модели', len(W.pre))
    print('проверка: маяк', W.block(-771, 93, 1888), '| пирс', W.block(-690, 64, 1875), '| рельеф (-740,1800)', W.surf(-740, 1800))
