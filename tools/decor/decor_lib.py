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

def check_water(schema, terrain, warnings=None):
    """
    Возвращает список строк-ошибок. Правило 1.12 (DECOR.md §0, «Опыт»):
    - `water` (спокойная вода) после /fill или /setblock НЕ течёт, пока рядом
      ничего не изменится. Годится для бассейнов; `water` над воздухом повиснет -
      это ошибка (для струй нужен `flowing_water:0`).
    - `flowing_water:0` сразу начинает течь. Если под ним воздух - струя должна
      упасть в воду схемы (иначе ошибка). Если под ним опора - это задуманный
      каскад: растекание не моделируется, в warnings (если передан список)
      пишется предупреждение «каскад - поведение подтверждается на сервере».
    """
    errors = []
    for (x, y, z), spec in schema.items():
        name, _meta = parse_block(spec)
        bare = _bare(name)
        if bare == 'flowing_water':
            below = block_at(schema, terrain, x, y - 1, z)
            if not _is_air(below):
                if warnings is not None:
                    warnings.append(f'({x},{y},{z}) flowing_water: каскад от свободного источника - '
                                    f'растекание не моделируется, поведение подтверждается на сервере')
                continue
            cy = y - 1
            while True:
                cy -= 1
                cell_name = _bare(parse_block(block_at(schema, terrain, x, cy, z))[0])
                if cell_name != 'air':
                    break
            if cell_name not in ('water', 'flowing_water'):
                errors.append(f'({x},{y},{z}) flowing_water: струя падает на твёрдое и растечётся '
                              f'(первый не-воздух на ({x},{cy},{z}) - {cell_name})')
            continue
        if bare != 'water':
            continue
        if _is_air(block_at(schema, terrain, x, y - 1, z)):
            errors.append(f'({x},{y},{z}) water: спокойная вода над воздухом повиснет '
                          f'(после /fill не течёт) - для струи нужен flowing_water:0')
            continue

        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = block_at(schema, terrain, x + dx, y, z + dz)
            if _is_air(n):
                errors.append(f'({x},{y},{z}) water: утечка в направлении ({dx},0,{dz})')
    return errors


# ------------------------------------------------------------------
# check_supports - опоры
# ------------------------------------------------------------------

# торч/кнопки/рычаг на стене: metadata 1-4 = КУДА СМОТРИТ блок (1 восток,
# 2 запад, 3 юг, 4 север), опора - С ОБРАТНОЙ стороны (torch:1 висит на
# восточной грани блока, стоящего западнее). Проверено на схемах, которые
# стояли на сервере: house.json (torch:3/torch:4), npp-final.json
# (stone_button:3) - опора везде с обратной стороны. Раньше здесь было
# направление "как есть" (по старой формулировке BOT.md §6.4) - это был баг.
_DIR4 = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
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

    if bare == 'cocoa':
        # биты 0-1 - facing (0 юг, 1 запад, 2 север, 3 восток) = направление К стволу;
        # биты 2-3 - возраст. Опора - тропическое бревно (log:3/7/11) по направлению facing.
        dx, dz = {0: (0, 1), 1: (-1, 0), 2: (0, -1), 3: (1, 0)}[meta & 3]
        return (dx, 0, dz, 'jungle_log')

    if bare in BELOW_SUPPORT_NAMES:
        return (0, -1, 0, 'solid')

    if bare == 'double_plant':
        return (0, -1, 0, 'solid') if meta < 8 else None

    if bare.endswith('_door'):
        return (0, -1, 0, 'solid') if meta < 8 else None

    if bare in ('stone_button', 'wooden_button'):
        meta = meta & 7  # бит 8 - "нажата"
        if meta == 5:
            return (0, -1, 0, 'solid')
        if meta == 0:
            return (0, 1, 0, 'solid')
        if meta in _DIR4:
            dx, dz = _DIR4[meta]
            return (dx, 0, dz, 'solid')
        return None

    if bare == 'lever':
        meta = meta & 7  # бит 8 - "включён"
        if meta in (5, 6):
            return (0, -1, 0, 'solid')   # на полу
        if meta in (0, 7):
            return (0, 1, 0, 'solid')    # на потолке
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


SEND_ORDER_JS = os.path.join(_HERE, 'send_order.js')


def read_falling_block_names(fill_plan_path=None):
    return _read_js_set('FALLING_BLOCK_NAMES', fill_plan_path)


def get_send_order(schema, file_order):
    """
    Реальный порядок отправки команд ботом: пишет схему во временный файл
    в порядке file_order и вызывает node tools/decor/send_order.js (он зовёт
    buildFillCommands из lib/fill-plan.js - логика движка не дублируется).
    Возвращает dict {(x,y,z): номер_команды}. Клетки одной команды (/fill)
    получают один номер - они встают одновременно.
    """
    import subprocess
    import tempfile
    entries = [{'x': k[0], 'y': k[1], 'z': k[2], 'block': schema[k]} for k in file_order]
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(entries, f)
        tmp = f.name
    try:
        out = subprocess.run(['node', SEND_ORDER_JS, tmp], capture_output=True, text=True,
                             encoding='utf-8', check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        detail = getattr(e, 'stderr', '') or str(e)
        raise RuntimeError('не удалось получить порядок отправки через node send_order.js '
                           '(нужны node и node_modules репозитория, `npm install`): ' + detail)
    finally:
        os.unlink(tmp)
    data = json.loads(out)
    return {tuple(int(v) for v in key.split(',')): idx for key, idx in data['order'].items()}


def _check_pairs(schema, send):
    errors, warnings = [], []
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
        ok_type = (_bare(top_name) == _bare(name)) and (
            (kind == 'bed' and top_meta == meta + 8) or (kind != 'bed' and top_meta >= 8)
        )
        if not ok_type:
            errors.append(f'({x},{y},{z}) {name}: в {top_key} не {label} ({top_spec})')
            continue

        i_low, i_top = send.get((x, y, z)), send.get(top_key)
        if i_low is None or i_top is None:
            continue
        if kind in ('door', 'bed'):
            if i_top != i_low + 1:
                errors.append(f'({x},{y},{z}) {name}: {label} не следующей командой после '
                              f'{low_label} (команды {i_low} и {i_top})')
        else:  # double_plant
            neigh = {(x + a, y + b, z + c) for a, b, c in
                     ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0))}
            hit = [k for k in neigh if k in send and i_low < send[k] < i_top]
            if hit:
                warnings.append(f'({x},{y},{z}) {name}: между низом (команда {i_low}) и верхом '
                                f'({i_top}) ставятся соседи {sorted(hit)} - низ сирени может '
                                f'отвалиться до установки верха')
    return errors, warnings


def _check_falling(schema, send, terrain):
    """Падающие блоки: опора снизу - твёрдая и ставится раньше или той же командой."""
    errors = []
    falling = read_falling_block_names()
    attached_names = read_attached_block_names()
    liquid_names = read_liquid_block_names()
    for (x, y, z), spec in schema.items():
        name, _m = parse_block(spec)
        if _bare(name) not in falling:
            continue
        skey = (x, y - 1, z)
        if skey not in schema:
            if _is_air(terrain(*skey)):
                errors.append(f'({x},{y},{z}) {name}: падающий блок без опоры (под ним воздух)')
            continue
        sname = parse_block(schema[skey])[0]
        sb = _bare(sname)
        if sb == 'air' or sb in liquid_names or is_attached_block(sname, attached_names):
            errors.append(f'({x},{y},{z}) {name}: под падающим блоком не твёрдое ({schema[skey]})')
        elif send.get(skey, -1) > send.get((x, y, z), -1):
            errors.append(f'({x},{y},{z}) {name}: опора {skey} ставится позже '
                          f'(команда {send[skey]} > {send[(x, y, z)]}) - блок упадёт')
    return errors


def check_supports(schema, file_order, terrain):
    """
    Возвращает (errors, warnings). Порядок проверяется по РЕАЛЬНОМУ порядку
    отправки команд ботом (get_send_order), а не по порядку файла.
    """
    errors, warnings = [], []
    send = get_send_order(schema, file_order)

    for (x, y, z), spec in schema.items():
        name, meta = parse_block(spec)
        rule = support_rule(name, meta)
        if rule is None:
            continue
        dx, dy, dz, required = rule
        skey = (x + dx, y + dy, z + dz)
        in_schema = skey in schema
        support_bare = _bare(parse_block(schema[skey] if in_schema else terrain(*skey))[0])

        if required == 'jungle_log':
            sname, smeta = parse_block(schema[skey] if in_schema else terrain(*skey))
            if not (_bare(sname) == 'log' and (smeta & 3) == 3):
                errors.append(f'({x},{y},{z}) {name}: какао держится только на тропическом бревне '
                              f'(log:3), а в {skey} - {sname}:{smeta}')
            elif in_schema and send.get(skey, -1) > send.get((x, y, z), -1):
                errors.append(f'({x},{y},{z}) {name}: бревно-опора {skey} ставится позже')
            continue

        if required == 'water':
            if in_schema and support_bare == 'water':
                if send.get(skey, -1) > send.get((x, y, z), -1):
                    warnings.append(
                        f'({x},{y},{z}) {name}: вода-опора {skey} ставится ботом позже '
                        f'(финальный проход воды, BOT.md §4.4) - до доработки бота может отвалиться')
            else:
                errors.append(f'({x},{y},{z}) {name}: нужна вода в {skey}, а там {support_bare}')
            continue

        if support_bare in ('air', 'water', 'lava') or (
                in_schema and is_attached_block(parse_block(schema[skey])[0])):
            errors.append(f'({x},{y},{z}) {name}: нет опоры в {skey} ({support_bare})')
            continue
        if in_schema and send.get(skey, -1) > send.get((x, y, z), -1):
            errors.append(f'({x},{y},{z}) {name}: опора {skey} ставится позже '
                          f'(команда {send[skey]} > {send[(x, y, z)]})')

    e, w = _check_pairs(schema, send)
    errors.extend(e)
    warnings.extend(w)
    errors.extend(_check_falling(schema, send, terrain))
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
