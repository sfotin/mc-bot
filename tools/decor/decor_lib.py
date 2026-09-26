"""
decor_lib.py - общая библиотека для генераторов декора (tools/decor/) и
decor_check.py. Только стандартная библиотека Python 3.

Схема здесь - dict {(x,y,z): "имя[:meta]"} (более поздняя запись по тому же
ключу просто затирает раннюю - обычная семантика dict). Функции этого
модуля НЕ хранят собственный порядок вставки как "истину" - порядок записи
в файл считает compute_order() по явным правилам (см. save()), а не порядок
операций put() в генераторе.

Список крепящихся блоков (ATTACHED_BLOCK_NAMES) читается прямо из
lib/fill-plan.js (см. read_attached_block_names) - не дублируется здесь
руками, чтобы не разъехаться с ботом.
"""
import json
import os
import re
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILL_PLAN_PATH = os.path.normpath(os.path.join(_HERE, '..', '..', 'lib', 'fill-plan.js'))


def _bare(name):
    return name[len('minecraft:'):] if name.startswith('minecraft:') else name


def parse_block(spec):
    """"stone" -> ("stone", 0); "stone:3" -> ("stone", 3). Как parseBlockSpec в lib/fill-plan.js."""
    idx = spec.rfind(':')
    if idx > 0:
        name, meta_s = spec[:idx], spec[idx + 1:]
        if meta_s.isdigit():
            return name, int(meta_s)
    return spec, 0


# ------------------------------------------------------------------
# Чтение списков блоков напрямую из lib/fill-plan.js (не хардкодить)
# ------------------------------------------------------------------

_js_set_cache = {}


def _read_js_set(const_name, fill_plan_path=None):
    path = fill_plan_path or DEFAULT_FILL_PLAN_PATH
    cache_key = (path, const_name)
    if cache_key in _js_set_cache:
        return _js_set_cache[cache_key]
    with open(path, encoding='utf-8') as f:
        text = f.read()
    m = re.search(const_name + r"\s*=\s*new Set\(\[(.*?)\]\)", text, re.S)
    if not m:
        raise RuntimeError(f'не удалось найти {const_name} в {path}')
    names = set(re.findall(r"'([^']+)'", m.group(1)))
    _js_set_cache[cache_key] = names
    return names


def read_attached_block_names(fill_plan_path=None):
    """ATTACHED_BLOCK_NAMES из lib/fill-plan.js (без суффиксного правила _door/_torch)."""
    return _read_js_set('ATTACHED_BLOCK_NAMES', fill_plan_path)


def read_liquid_block_names(fill_plan_path=None):
    return _read_js_set('LIQUID_BLOCK_NAMES', fill_plan_path)


def is_attached_block(name, attached_names=None, fill_plan_path=None):
    """Копия isAttachedBlock из lib/fill-plan.js (тот же список + суффиксы)."""
    bare = _bare(name)
    names = attached_names if attached_names is not None else read_attached_block_names(fill_plan_path)
    if bare in names:
        return True
    return bare.endswith('_door') or bare.endswith('_torch')


def is_liquid_block(name, liquid_names=None, fill_plan_path=None):
    bare = _bare(name)
    names = liquid_names if liquid_names is not None else read_liquid_block_names(fill_plan_path)
    return bare in names


# ------------------------------------------------------------------
# Местность (terrain) - предположение о том, что вне схемы
# ------------------------------------------------------------------

def make_terrain(kind):
    """
    "below" - всё вне схемы при y<0 твёрдое (schema ставится поверх готовой
    площадки на y=0 и выше). "y0" - всё вне схемы при y<=0 твёрдое (схема
    заменяет собой слой y=0 - грунт/мостовую). Прочее вне схемы - воздух.
    Возвращает terrain(x,y,z) -> "stone"|"air" (без учёта x,z - местность
    предполагается ровной и однородной за пределами схемы).
    """
    if kind == 'below':
        def terrain(x, y, z):
            return 'stone' if y < 0 else 'air'
    elif kind == 'y0':
        def terrain(x, y, z):
            return 'stone' if y <= 0 else 'air'
    else:
        raise ValueError('terrain должен быть "below" или "y0", получено: ' + repr(kind))
    return terrain


def block_at(schema, terrain, x, y, z):
    """Блок в (x,y,z): из схемы, если там есть запись, иначе из terrain()."""
    key = (x, y, z)
    if key in schema:
        return schema[key]
    return terrain(x, y, z)


def _is_air(spec):
    return parse_block(spec)[0] == 'air'


def _is_water_name(bare):
    return bare == 'water'


# ------------------------------------------------------------------
# check_water - правило 1.12 для воды
# ------------------------------------------------------------------

def check_water(schema, terrain):
    """Возвращает список строк-ошибок (без предупреждений - тут их не бывает)."""
    errors = []
    for (x, y, z), spec in schema.items():
        name, _meta = parse_block(spec)
        if _bare(name) != 'water':
            continue

        below = block_at(schema, terrain, x, y - 1, z)
        if _is_air(below):
            # струя падает - ищем первый не-воздух ниже
            cy = y - 1
            cell_name = 'air'
            while True:
                cy -= 1
                cell = block_at(schema, terrain, x, cy, z)
                cell_name = _bare(parse_block(cell)[0])
                if cell_name != 'air':
                    break
            if cell_name != 'water':
                errors.append(
                    f'({x},{y},{z}) water: струя падает на твёрдое и растечётся '
                    f'(первый не-воздух на ({x},{cy},{z}) - {cell_name})'
                )
        else:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = block_at(schema, terrain, x + dx, y, z + dz)
                if _is_air(n):
                    errors.append(f'({x},{y},{z}) water: утечка в направлении ({dx},0,{dz})')
    return errors


# ------------------------------------------------------------------
# check_supports - опоры
# ------------------------------------------------------------------

# торч/кнопки/рычаг: metadata = "сторона крепления" НАПРЯМУЮ (BOT.md §6.4) -
# компас 1-4 = восток,запад,юг,север - это и есть направление к опоре.
_DIR4 = {1: (1, 0), 2: (-1, 0), 3: (0, 1), 4: (0, -1)}
# ladder/wall_sign (DECOR.md §1): metadata = КУДА СМОТРИТ блок (facing), опора -
# С ОБРАТНОЙ стороны (2 север,3 юг,4 запад,5 восток - facing; опора наоборот).
_LADDER_DIR = {2: (0, 1), 3: (0, -1), 4: (1, 0), 5: (-1, 0)}
# tripwire_hook (DECOR.md §1): metadata = куда торчит (facing), крепится к
# блоку С ОБРАТНОЙ СТОРОНЫ (0 юг,1 запад,2 север,3 восток - facing; опора наоборот).
# Проверено на реальном примере (DECOR.md §2.9 - кран tripwire_hook:0 у стены
# сзади): с прямой (нереверсированной) картой опора уходила в пустоту.
_HOOK_DIR = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
# кровать: ноги->изголовье, смещение по направлению facing (0 юг,1 запад,2 север,3 восток)
_BED_DIR = {0: (0, 1), 1: (-1, 0), 2: (0, -1), 3: (1, 0)}

NO_SUPPORT_NEEDED_EXACT = {
    'trapdoor', 'iron_trapdoor', 'tripwire', 'skull', 'end_rod',
    'brewing_stand', 'cauldron', 'hopper', 'bed',
    'glass', 'stained_glass', 'glass_pane', 'stained_glass_pane',
    'fence_gate',
}

BELOW_SUPPORT_NAMES = {
    'carpet', 'flower_pot', 'red_flower', 'yellow_flower', 'tallgrass', 'sapling', 'fire',
}


def _no_support_needed(bare):
    if bare in NO_SUPPORT_NEEDED_EXACT:
        return True
    return bare == 'fence' or bare.endswith('_fence')


def support_rule(name, meta):
    """
    Возвращает (dx, dy, dz, required) - куда смотреть за опорой и что там
    должно быть ("solid" или "water" - для waterlily), либо None, если для
    этого блока правило неприменимо (не требует опоры, либо это верхняя
    половина парного блока - для неё опора не проверяется этой функцией,
    см. _check_pairs).
    """
    bare = _bare(name)

    if _no_support_needed(bare):
        return None

    if bare == 'waterlily':
        return (0, -1, 0, 'water')

    if bare in BELOW_SUPPORT_NAMES:
        return (0, -1, 0, 'solid')

    if bare == 'double_plant':
        return (0, -1, 0, 'solid') if meta < 8 else None

    if bare.endswith('_door'):
        return (0, -1, 0, 'solid') if meta < 8 else None

    if bare in ('stone_button', 'wooden_button'):
        if meta == 5:
            return (0, -1, 0, 'solid')
        if meta == 0:
            return (0, 1, 0, 'solid')
        if meta in _DIR4:
            dx, dz = _DIR4[meta]
            return (dx, 0, dz, 'solid')
        return None

    if bare == 'lever':
        if meta in _DIR4:
            dx, dz = _DIR4[meta]
            return (dx, 0, dz, 'solid')
        return None

    if bare == 'torch' or bare.endswith('_torch'):
        if meta == 5:
            return (0, -1, 0, 'solid')
        if meta in _DIR4:
            dx, dz = _DIR4[meta]
            return (dx, 0, dz, 'solid')
        return None

    if bare in ('ladder', 'wall_sign'):
        if meta in _LADDER_DIR:
            dx, dz = _LADDER_DIR[meta]
            return (dx, 0, dz, 'solid')
        return None

    if bare == 'tripwire_hook':
        if meta in _HOOK_DIR:
            dx, dz = _HOOK_DIR[meta]
            return (dx, 0, dz, 'solid')
        return None

    if bare.endswith('_pressure_plate'):
        return (0, -1, 0, 'solid')

    return None


def _pair_info(name, meta):
    """
    Если (name,meta) - НИЖНЯЯ половина парного блока (дверь/double_plant/bed),
    возвращает (kind, top_offset). Иначе None. top_offset - (dx,dy,dz) до
    второй половины, expected_top_meta - какая metadata там ожидается.
    """
    bare = _bare(name)
    if bare.endswith('_door') and meta < 8:
        return ('door', (0, 1, 0))
    if bare == 'double_plant' and meta < 8:
        return ('double_plant', (0, 1, 0))
    if bare == 'bed' and meta < 8 and meta in _BED_DIR:
        dx, dz = _BED_DIR[meta]
        return ('bed', (dx, 0, dz))
    return None


def _check_pairs(schema, file_order):
    errors = []
    index_of = {k: i for i, k in enumerate(file_order)}
    for (x, y, z), spec in schema.items():
        name, meta = parse_block(spec)
        info = _pair_info(name, meta)
        if info is None:
            continue
        kind, (dx, dy, dz) = info
        top_key = (x + dx, y + dy, z + dz)
        top_spec = schema.get(top_key)
        label = {'door': 'верх двери', 'double_plant': 'верх double_plant', 'bed': 'изголовье'}[kind]
        low_label = {'door': 'низ двери', 'double_plant': 'низ double_plant', 'bed': 'ноги кровати'}[kind]

        if top_spec is None:
            errors.append(f'({x},{y},{z}) {name}: нет пары ({low_label} без {label} в {top_key})')
            continue

        top_name, top_meta = parse_block(top_spec)
        top_bare = _bare(top_name)
        expect_bare = _bare(name)
        ok_type = (top_bare == expect_bare) and (
            (kind == 'bed' and top_meta == meta + 8) or (kind != 'bed' and top_meta >= 8)
        )
        if not ok_type:
            errors.append(f'({x},{y},{z}) {name}: в {top_key} не {label} ({top_spec})')
            continue

        i_low = index_of.get((x, y, z))
        i_top = index_of.get(top_key)
        if i_low is None or i_top is None:
            continue
        if i_top != i_low + 1:
            errors.append(f'({x},{y},{z}) {name}: {label} не сразу после {low_label} в файле (индексы {i_low},{i_top})')
    return errors


def check_supports(schema, file_order, terrain):
    """Возвращает (errors, warnings) - списки строк."""
    errors = []
    warnings = []
    attached_names = read_attached_block_names()
    index_of = {k: i for i, k in enumerate(file_order)}

    for (x, y, z), spec in schema.items():
        name, meta = parse_block(spec)
        rule = support_rule(name, meta)
        if rule is None:
            continue
        dx, dy, dz, required = rule
        skey = (x + dx, y + dy, z + dz)
        support_from_schema = skey in schema
        support_spec = schema[skey] if support_from_schema else terrain(*skey)
        support_bare = _bare(parse_block(support_spec)[0]) if support_from_schema else _bare(support_spec)

        if required == 'water':
            if support_from_schema and support_bare == 'water':
                warnings.append(
                    f'({x},{y},{z}) {name}: опора (вода в {skey}) - в текущем движке бота вода '
                    f'идёт отдельным финальным проходом ПОСЛЕ этого блока (см. BOT.md §4.4/§10.4.8) - '
                    f'до доработки бота может отвалиться'
                )
            else:
                errors.append(f'({x},{y},{z}) {name}: нужна вода в {skey}, а там {support_bare}')
            continue

        # required == 'solid'
        if support_bare in ('air', 'water'):
            errors.append(f'({x},{y},{z}) {name}: нет опоры в {skey} ({support_bare})')
            continue

        if support_from_schema and not is_attached_block(name, attached_names):
            i_self = index_of.get((x, y, z))
            i_sup = index_of.get(skey)
            if i_self is not None and i_sup is not None and i_sup > i_self:
                errors.append(
                    f'({x},{y},{z}) {name}: опора {skey} стоит позже в файле '
                    f'(индекс {i_sup} > {i_self}) - бот ставит этот блок твёрдым проходом'
                )

    errors.extend(_check_pairs(schema, file_order))
    return errors, warnings


# ------------------------------------------------------------------
# compute_order / save - порядок записи в файл (см. §1 задания)
# ------------------------------------------------------------------

def compute_order(schema):
    """
    Порядок: 1) обычные блоки; 2) блоки, которым нужна опора (см.
    support_rule) - после обычных; 3) пары (двери, double_plant, кровати -
    кровати последними среди твёрдых); 4) fire и waterlily - самыми
    последними. Внутри каждой группы - относительный порядок как при обходе
    schema.items() (Python dict хранит порядок вставки).
    """
    keys = list(schema.keys())
    handled = set()

    fire_waterlily = []
    for k in keys:
        name, _meta = parse_block(schema[k])
        if _bare(name) in ('fire', 'waterlily'):
            fire_waterlily.append(k)
            handled.add(k)

    door_pairs = []
    plant_pairs = []
    bed_pairs = []
    for k in keys:
        if k in handled:
            continue
        name, meta = parse_block(schema[k])
        info = _pair_info(name, meta)
        if info is None:
            continue
        kind, (dx, dy, dz) = info
        top_key = (k[0] + dx, k[1] + dy, k[2] + dz)
        bucket = {'door': door_pairs, 'double_plant': plant_pairs, 'bed': bed_pairs}[kind]
        bucket.append((k, top_key))
        handled.add(k)
        if top_key in schema:
            handled.add(top_key)

    below_support = []
    for k in keys:
        if k in handled:
            continue
        name, meta = parse_block(schema[k])
        if support_rule(name, meta) is not None:
            below_support.append(k)
            handled.add(k)

    regular = [k for k in keys if k not in handled]

    order = []
    order.extend(regular)
    order.extend(below_support)
    for bottom, top in door_pairs:
        order.append(bottom)
        if top in schema:
            order.append(top)
    for bottom, top in plant_pairs:
        order.append(bottom)
        if top in schema:
            order.append(top)
    for legs, head in bed_pairs:
        order.append(legs)
        if head in schema:
            order.append(head)
    order.extend(fire_waterlily)
    return order


def save(schema, path, order):
    """Пишет JSON-массив {x,y,z,block} в порядке order (см. compute_order)."""
    entries = []
    for (x, y, z) in order:
        if x < 0 or y < 0 or z < 0:
            raise ValueError(f'координаты схемы должны быть неотрицательными: ({x},{y},{z})')
        entries.append({'x': x, 'y': y, 'z': z, 'block': schema[(x, y, z)]})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, separators=(',', ':'))
    return entries


def entries_to_schema(entries):
    """JSON-список {x,y,z,block} -> (schema dict, file_order) - для decor_check.py."""
    schema = {}
    order = []
    for e in entries:
        key = (e['x'], e['y'], e['z'])
        if key not in schema:
            order.append(key)
        schema[key] = e['block']
    return schema, order


# ------------------------------------------------------------------
# plan - поэтажный план ASCII
# ------------------------------------------------------------------

def plan(schema, legend=None, out=None):
    """Печатает (и возвращает) поэтажный план: по слою на каждый y, строки z
    (север -> юг, т.е. по возрастанию z), столбцы x. "." - нет записи."""
    out = out if out is not None else sys.stdout
    xs = [k[0] for k in schema]
    ys = [k[1] for k in schema]
    zs = [k[2] for k in schema]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)

    lines = []
    for y in range(miny, maxy + 1):
        lines.append(f'y={y}:')
        for z in range(minz, maxz + 1):
            row = []
            for x in range(minx, maxx + 1):
                spec = schema.get((x, y, z))
                if spec is None:
                    row.append('.')
                    continue
                ch = None
                if legend:
                    ch = legend.get(spec)
                    if ch is None:
                        name = parse_block(spec)[0]
                        ch = legend.get(name)
                row.append(ch if ch else '?')
            lines.append(''.join(row))
        lines.append('')

    text = '\n'.join(lines)
    print(text, file=out)
    return text


# ------------------------------------------------------------------
# report
# ------------------------------------------------------------------

def report(schema, order, errors, warnings, label=None, out=None):
    """Печатает число записей/Counter/габарит/ошибки/предупреждения.
    Возвращает число ошибок (0 - схема чистая)."""
    out = out if out is not None else sys.stdout
    if label:
        print(f'=== {label} ===', file=out)

    xs = [k[0] for k in schema]
    ys = [k[1] for k in schema]
    zs = [k[2] for k in schema]
    counter = Counter(schema[k] for k in order) if order else Counter(schema.values())

    print(f'записей: {len(schema)}', file=out)
    print(f'габарит: {max(xs) - min(xs) + 1}x{max(ys) - min(ys) + 1}x{max(zs) - min(zs) + 1}', file=out)
    print(f'материалы: {dict(counter)}', file=out)
    print('Проходимость (BOT.md §12) к декору не применяется - это не здания.', file=out)

    if warnings:
        print(f'ПРЕДУПРЕЖДЕНИЯ ({len(warnings)}):', file=out)
        for w in warnings:
            print(f'  {w}', file=out)
    else:
        print('ПРЕДУПРЕЖДЕНИЙ: 0', file=out)

    if errors:
        print(f'ОШИБКИ ({len(errors)}):', file=out)
        for e in errors:
            print(f'  {e}', file=out)
    else:
        print('ОШИБОК: 0', file=out)

    return len(errors)
