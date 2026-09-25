"""
Общий код чтения файла региона Minecraft 1.12.2 (формат Anvil, .mca):
минимальный NBT-ридер, доступ к секциям блоков одного чанка и разбор
бокса участка в границы одного региона. Используется terrain_from_region.py
и terrain_caves.py - здесь ничего специфичного для рельефа/пустот нет.
"""
import struct
import zlib


def read_nbt(buf):
    """Минимальный NBT-ридер (без сжатия внешнего слоя - его снимает
    вызывающий код через zlib, см. read_chunk_sections)."""
    p = [0]

    def rd(fmt):
        v = struct.unpack_from('>' + fmt, buf, p[0])
        p[0] += struct.calcsize('>' + fmt)
        return v[0]

    def rstr():
        n = rd('H')
        s = buf[p[0]:p[0] + n].decode('utf-8', 'replace')
        p[0] += n
        return s

    def payload(t):
        if t == 1: return rd('b')
        if t == 2: return rd('h')
        if t == 3: return rd('i')
        if t == 4: return rd('q')
        if t == 5: return rd('f')
        if t == 6: return rd('d')
        if t == 7:
            n = rd('i')
            v = buf[p[0]:p[0] + n]
            p[0] += n
            return v
        if t == 8: return rstr()
        if t == 9:
            et = rd('b')
            n = rd('i')
            return [payload(et) for _ in range(n)]
        if t == 10:
            d = {}
            while True:
                tt = rd('b')
                if tt == 0: return d
                name = rstr()
                d[name] = payload(tt)
        if t == 11:
            n = rd('i')
            v = struct.unpack_from('>%di' % n, buf, p[0])
            p[0] += 4 * n
            return list(v)
        if t == 12:
            n = rd('i')
            v = struct.unpack_from('>%dq' % n, buf, p[0])
            p[0] += 8 * n
            return list(v)
        raise ValueError('tag %d' % t)

    t = rd('b')
    rstr()
    return payload(t)


def region_of_chunk(cx, cz):
    """Координаты файла региона (RX,RZ), покрывающего чанк (cx,cz) - 32x32
    чанка на файл, деление с округлением вниз (>> 5 - целочисленный floor
    и для отрицательных чисел, в отличие от JS >> 4/>> 5 с 32-битным knock)."""
    return cx >> 5, cz >> 5


def resolve_box(box):
    """box = (x1,z1,x2,z2) в любом порядке. Возвращает (X0,Z0,W,H,RX,RZ,
    cx0,cx1,cz0,cz1). Бросает понятную ошибку, если бокс требует больше
    одного файла региона (несколько регионов разом не читаем)."""
    bx1, bz1, bx2, bz2 = box
    X0, X1 = sorted((bx1, bx2))
    Z0, Z1 = sorted((bz1, bz2))
    W = X1 - X0 + 1
    H = Z1 - Z0 + 1

    cx0, cx1 = X0 >> 4, X1 >> 4
    cz0, cz1 = Z0 >> 4, Z1 >> 4

    regions = {region_of_chunk(cx, cz) for cx in (cx0, cx1) for cz in (cz0, cz1)}
    if len(regions) != 1:
        raise SystemExit(
            f'ОШИБКА: бокс X {X0}..{X1} Z {Z0}..{Z1} (чанки X {cx0}..{cx1}, Z {cz0}..{cz1}) '
            f'охватывает несколько файлов региона {sorted(regions)} - один .mca не читает.'
        )
    RX, RZ = regions.pop()
    return X0, Z0, W, H, RX, RZ, cx0, cx1, cz0, cz1


def load_region(path):
    """Читает файл региона в память целиком - размер фиксированный (до
    8 КБ на локейшн-таблицу + сами чанки), для одного .mca это разумно."""
    with open(path, 'rb') as f:
        return f.read()


def read_chunk_sections(data, cx, cz, rx, rz):
    """Секции блоков одного чанка (cx,cz) внутри региона (rx,rz):
    {sectionY: (BlocksBytes, AddBytesOrNone)}, или None, если чанк ещё не
    сгенерирован (пустая локейшн-запись)."""
    lx, lz = cx - rx * 32, cz - rz * 32
    i = lz * 32 + lx
    off = struct.unpack('>I', data[i * 4:i * 4 + 4])[0]
    sec = off >> 8
    if sec == 0:
        return None
    length = struct.unpack('>I', data[sec * 4096:sec * 4096 + 4])[0]
    comp = data[sec * 4096 + 4]
    raw = data[sec * 4096 + 5: sec * 4096 + 4 + length]
    root = read_nbt(zlib.decompress(raw) if comp == 2 else raw)
    lvl = root['Level']
    assert lvl['xPos'] == cx and lvl['zPos'] == cz
    sections = {}
    for s in lvl.get('Sections', []):
        sections[s['Y']] = (s['Blocks'], s.get('Add'))
    return sections


def block_id_at(sections, x, y, z):
    """Числовой id блока (с учётом Add-полубайта >255) в локальных
    координатах чанка (x,z в 0..15). 0 (air), если секция Y//16 пустая."""
    s = sections.get(y >> 4)
    if not s:
        return 0
    B, A = s
    k = ((y & 15) << 8) | (z << 4) | x
    v = B[k]
    if A:
        a = A[k >> 1]
        v |= ((a >> 4) if k & 1 else (a & 15)) << 8
    return v


def max_section_height(sections):
    """Верхняя граница Y, до которой имеет смысл сканировать чанк - выше
    самой верхней непустой секции гарантированно воздух."""
    return (max(sections) + 1) * 16 - 1 if sections else 0
