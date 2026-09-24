'use strict';

// Не тянем lib/build.js: он транзитивно требует vec3/mineflayer-pathfinder,
// а index-cmd.js/lib/connect-raw.js принципиально не используют mineflayer -
// поэтому здесь своя маленькая копия разбора "stone"/"stone:1", без лишних
// зависимостей.
const fs = require('fs');
const path = require('path');
const config = require('../config');

// Протокольный лимит /fill в 1.12.2 - 32768 блоков (32*32*32), но такие
// большие /fill подвешивают модовый сервер и бота выкидывает по таймауту,
// поэтому режем боксы по config.maxFillVolume (заметно меньше протокольного
// лимита), а не по нему самому.
const MAX_FILL_VOLUME = config.maxFillVolume;

/**
 * Разбирает запись схемы вида "stone" или "stone:1" (в 1.12.2 варианты
 * блока различаются одним id, но разной metadata).
 */
function parseBlockSpec(spec) {
  const idx = spec.lastIndexOf(':');
  if (idx > 0) {
    const namePart = spec.slice(0, idx);
    const metaNum = Number(spec.slice(idx + 1));
    if (Number.isInteger(metaNum) && metaNum >= 0) {
      return { name: namePart, metadata: metaNum };
    }
  }
  return { name: spec, metadata: 0 };
}

/**
 * Загружает и валидирует схему постройки из папки schemasDir.
 * Разрешаем только имя файла (path.basename), без выхода за пределы папки.
 */
function loadSchema(schemasDir, fileName) {
  const safeName = path.basename(fileName);
  const fullPath = path.resolve(schemasDir, safeName);
  const raw = fs.readFileSync(fullPath, 'utf8');
  const data = JSON.parse(raw);
  if (!Array.isArray(data)) {
    throw new Error('схема должна быть JSON-массивом объектов {x,y,z,block}');
  }
  for (const entry of data) {
    if (typeof entry.x !== 'number' || typeof entry.y !== 'number' ||
        typeof entry.z !== 'number' || typeof entry.block !== 'string') {
      throw new Error('каждый элемент схемы должен иметь числовые x,y,z и строковый block');
    }
  }
  return data;
}

// Блоки, которые крепятся к соседнему блоку/грани или требуют под собой
// уже готовую твёрдую опору (кнопки, рычаг, лестницы-стремянки, лианы,
// нажимные плиты, крюк растяжки) - /fill их не ставит надёжно (ориентация/
// место крепления теряются при массовой заливке, а без опоры блок просто
// не встанет), поэтому они всегда идут отдельным проходом через /setblock,
// после всех "твёрдых" блоков. Сюда же добавлены water/lava: они должны
// литься после того, как встанут борта (стены, дно) - иначе жидкость
// растечётся до того, как ёмкость будет готова.
const ATTACHED_BLOCK_NAMES = new Set([
  'torch', 'wooden_door', 'ladder', 'lever', 'stone_button', 'wooden_button',
  'sign', 'rail', 'vine', 'water', 'lava',
  'stone_pressure_plate', 'wooden_pressure_plate', 'tripwire_hook'
]);

function isAttachedBlock(name) {
  const bare = name.startsWith('minecraft:') ? name.slice('minecraft:'.length) : name;
  if (ATTACHED_BLOCK_NAMES.has(bare)) return true;
  return bare.endsWith('_door') || bare.endsWith('_torch');
}

/**
 * Делит схему на solid (мёржится в боксы) и attached (крепящиеся блоки -
 * идут по одному, как есть, в исходном порядке файла). Порядок elements
 * в каждой из групп сохраняется как в исходной схеме.
 */
function splitSchemaByAttachment(schema) {
  const solid = [];
  const attached = [];
  for (const entry of schema) {
    const { name } = parseBlockSpec(entry.block);
    if (isAttachedBlock(name)) attached.push(entry);
    else solid.push(entry);
  }
  return { solid, attached };
}

/**
 * attached-блоки не мёржатся и не сортируются - каждый идёт своим
 * /setblock с сохранением metadata (ориентация/состояние крепления).
 */
function buildAttachedCommands(attachedEntries, origin) {
  return attachedEntries.map((entry) => {
    const { name, metadata } = parseBlockSpec(entry.block);
    const x = entry.x + origin.x;
    const y = entry.y + origin.y;
    const z = entry.z + origin.z;
    return `/setblock ${x} ${y} ${z} ${name} ${metadata}`;
  });
}

const VALID_ROTATIONS = new Set([0, 90, 180, 270]);

/**
 * Блоки, чья metadata кодирует направление/ориентацию, но пересчёт для
 * которых пока не реализован (таблички, рельсы - у них ориентация кодируется
 * иначе, чем в четырёх поддержанных ниже категориях). rotateSchema для них
 * только двигает координаты, ориентация остаётся как в файле.
 */
function isDirectionalMetadataBlock(name) {
  const bare = name.startsWith('minecraft:') ? name.slice('minecraft:'.length) : name;
  if (bare === 'sign' || bare === 'rail') return true;
  return bare.endsWith('_sign') || bare.endsWith('_rail');
}

function hasDirectionalMetadataBlocks(schema) {
  return schema.some((entry) => isDirectionalMetadataBlock(parseBlockSpec(entry.block).name));
}

// Для каждой из поддержанных категорий - циклический порядок значений
// metadata по часовой стрелке (если смотреть сверху). Поворот на 90/180/270 -
// это сдвиг на 1/2/3 позиции по этому циклу.
const STAIR_DIRECTION_CYCLE = [0, 2, 1, 3]; // восток, юг, запад, север
// восток, юг, запад, север - тот же формат 1/2/3/4 использует torch/redstone_torch
// (5 = пол, не крутится), а также кнопки (0 = потолок, 5 = пол) и рычаг
// (0,5,6,7 - на полу/потолке, не крутятся) - см. recalcMetadataForRotation.
const TORCH_DIRECTION_CYCLE = [1, 3, 2, 4];
const FACING_DIRECTION_CYCLE = [2, 5, 3, 4]; // север, восток, юг, запад (лестницы-стремянки/сундуки/печи)
const DOOR_DIRECTION_CYCLE = [0, 1, 2, 3]; // восток, юг, запад, север (нижняя половина)

const ROTATION_SHIFT = { 90: 1, 180: 2, 270: 3 };

function rotateInCycle(cycle, value, rotate) {
  const idx = cycle.indexOf(value);
  if (idx === -1) return value; // значение вне цикла (например, 5 у факела) - не трогаем
  const shift = ROTATION_SHIFT[rotate];
  return cycle[(idx + shift) % cycle.length];
}

const LADDER_CHEST_FURNACE_NAMES = new Set([
  'ladder', 'chest', 'trapped_chest', 'ender_chest', 'furnace', 'lit_furnace'
]);

/**
 * Пересчитывает metadata блока под поворот на 90/180/270 (см. правила по
 * категориям выше). Для дверей пересчитывается только нижняя половина
 * (бит 0x8 не установлен) - верхняя половина (петля/redstone) от поворота
 * не зависит и остаётся как есть. Для всех остальных блоков (в т.ч. рельс
 * и табличек - см. isDirectionalMetadataBlock) metadata не трогаем.
 */
function recalcMetadataForRotation(name, metadata, rotate) {
  const bare = name.startsWith('minecraft:') ? name.slice('minecraft:'.length) : name;

  if (bare.endsWith('_stairs')) {
    const dir = metadata & 0x3;
    return (metadata & ~0x3) | rotateInCycle(STAIR_DIRECTION_CYCLE, dir, rotate);
  }
  if (bare === 'torch' || bare.endsWith('redstone_torch')) {
    return rotateInCycle(TORCH_DIRECTION_CYCLE, metadata, rotate);
  }
  if (bare === 'stone_button' || bare === 'wooden_button' || bare === 'lever') {
    return rotateInCycle(TORCH_DIRECTION_CYCLE, metadata, rotate);
  }
  if (LADDER_CHEST_FURNACE_NAMES.has(bare)) {
    return rotateInCycle(FACING_DIRECTION_CYCLE, metadata, rotate);
  }
  if (bare.endsWith('_door')) {
    const isUpperHalf = (metadata & 0x8) !== 0;
    if (isUpperHalf) return metadata;
    const dir = metadata & 0x3;
    return (metadata & ~0x3) | rotateInCycle(DOOR_DIRECTION_CYCLE, dir, rotate);
  }
  return metadata;
}

/**
 * Поворачивает локальные координаты схемы (x,z) вокруг вертикальной оси
 * на 0/90/180/270 градусов по часовой стрелке (если смотреть сверху), Y не
 * трогает. Габарит схемы SX = maxX+1, SZ = maxZ+1 считается из исходных
 * координат (ожидается, что схема начинается с x=0,z=0, как обычные файлы
 * схем). После поворота координаты нормализуются к нулю, чтобы точка
 * запуска (origin) снова оказалась углом с минимальными X и Z. Заодно
 * пересчитывается metadata направленных блоков (см. recalcMetadataForRotation);
 * для блоков вне поддержанных категорий metadata остаётся как в файле
 * (см. isDirectionalMetadataBlock).
 */
function rotateSchema(schema, rotate) {
  if (!VALID_ROTATIONS.has(rotate)) {
    throw new Error(`недопустимый поворот ${rotate} - допустимо 0, 90, 180, 270`);
  }
  if (rotate === 0 || schema.length === 0) return schema;

  let maxX = -Infinity;
  let maxZ = -Infinity;
  for (const entry of schema) {
    if (entry.x > maxX) maxX = entry.x;
    if (entry.z > maxZ) maxZ = entry.z;
  }
  const SX = maxX + 1;
  const SZ = maxZ + 1;

  const rotated = schema.map((entry) => {
    let x2;
    let z2;
    if (rotate === 90) {
      x2 = SZ - 1 - entry.z;
      z2 = entry.x;
    } else if (rotate === 180) {
      x2 = SX - 1 - entry.x;
      z2 = SZ - 1 - entry.z;
    } else { // 270
      x2 = entry.z;
      z2 = SX - 1 - entry.x;
    }

    const { name, metadata } = parseBlockSpec(entry.block);
    const newMetadata = recalcMetadataForRotation(name, metadata, rotate);
    const block = newMetadata === metadata ? entry.block : `${name}:${newMetadata}`;

    return { ...entry, x: x2, z: z2, block };
  });

  let minX = Infinity;
  let minZ = Infinity;
  for (const entry of rotated) {
    if (entry.x < minX) minX = entry.x;
    if (entry.z < minZ) minZ = entry.z;
  }
  if (minX === 0 && minZ === 0) return rotated;
  return rotated.map((entry) => ({ ...entry, x: entry.x - minX, z: entry.z - minZ }));
}

function cellKey(x, y, z) {
  return `${x},${y},${z}`;
}

/**
 * Жадно схлопывает схему (массив {x,y,z,block}, координаты относительные)
 * в минимальное число параллелепипедов одного типа: сначала расширяем
 * бокс по X, потом по Z (весь X-диапазон должен совпасть), потом по Y
 * (весь X*Z прямоугольник должен совпасть). Возвращает боксы В ЛОКАЛЬНЫХ
 * координатах схемы (без применения origin).
 */
function buildBoxes(schema) {
  const cells = new Map();
  const order = [];

  for (const entry of schema) {
    const { name, metadata } = parseBlockSpec(entry.block);
    const key = cellKey(entry.x, entry.y, entry.z);
    cells.set(key, { x: entry.x, y: entry.y, z: entry.z, name, metadata });
    order.push(key);
  }

  function cellAt(x, y, z) {
    return cells.get(cellKey(x, y, z));
  }

  function sameType(a, b) {
    return a.name === b.name && a.metadata === b.metadata;
  }

  const boxes = [];

  for (const key of order) {
    const start = cells.get(key);
    if (!start) continue; // уже вошёл в предыдущий бокс

    // 1) расширяем по X
    let x2 = start.x;
    for (;;) {
      const next = cellAt(x2 + 1, start.y, start.z);
      if (next && sameType(next, start)) x2++;
      else break;
    }

    // 2) расширяем по Z - весь диапазон [start.x, x2] должен совпасть по типу
    let z2 = start.z;
    for (;;) {
      const nz = z2 + 1;
      let rowOk = true;
      for (let x = start.x; x <= x2; x++) {
        const c = cellAt(x, start.y, nz);
        if (!c || !sameType(c, start)) { rowOk = false; break; }
      }
      if (rowOk) z2 = nz;
      else break;
    }

    // 3) расширяем по Y - весь прямоугольник [start.x,x2]x[start.z,z2] должен совпасть
    let y2 = start.y;
    for (;;) {
      const ny = y2 + 1;
      let layerOk = true;
      for (let x = start.x; x <= x2 && layerOk; x++) {
        for (let z = start.z; z <= z2; z++) {
          const c = cellAt(x, ny, z);
          if (!c || !sameType(c, start)) { layerOk = false; break; }
        }
      }
      if (layerOk) y2 = ny;
      else break;
    }

    // помечаем занятое пространство как использованное
    for (let x = start.x; x <= x2; x++) {
      for (let y = start.y; y <= y2; y++) {
        for (let z = start.z; z <= z2; z++) {
          cells.delete(cellKey(x, y, z));
        }
      }
    }

    boxes.push({
      x1: start.x, y1: start.y, z1: start.z,
      x2, y2, z2,
      name: start.name, metadata: start.metadata
    });
  }

  return boxes;
}

function boxVolume(box) {
  return (box.x2 - box.x1 + 1) * (box.y2 - box.y1 + 1) * (box.z2 - box.z1 + 1);
}

/**
 * Режет бокс, если он превышает лимит объёма: делит пополам самую длинную
 * сторону и повторяет рекурсивно, пока каждый кусок не впишется в лимит
 * /fill. По умолчанию лимит - MAX_FILL_VOLUME (config.maxFillVolume), но
 * вызывающий код может передать свой (например, index-cmd.js для --wipe
 * использует протокольный лимит 32768 - там только air/stone, а не
 * направленные блоки, так что резать мельче не нужно).
 */
function splitBox(box, maxVolume = MAX_FILL_VOLUME) {
  if (boxVolume(box) <= maxVolume) return [box];

  const dx = box.x2 - box.x1 + 1;
  const dy = box.y2 - box.y1 + 1;
  const dz = box.z2 - box.z1 + 1;

  if (dx >= dy && dx >= dz && dx > 1) {
    const mid = box.x1 + Math.floor(dx / 2) - 1;
    return [
      ...splitBox({ ...box, x2: mid }, maxVolume),
      ...splitBox({ ...box, x1: mid + 1 }, maxVolume)
    ];
  }
  if (dz >= dy && dz > 1) {
    const mid = box.z1 + Math.floor(dz / 2) - 1;
    return [
      ...splitBox({ ...box, z2: mid }, maxVolume),
      ...splitBox({ ...box, z1: mid + 1 }, maxVolume)
    ];
  }
  if (dy > 1) {
    const mid = box.y1 + Math.floor(dy / 2) - 1;
    return [
      ...splitBox({ ...box, y2: mid }, maxVolume),
      ...splitBox({ ...box, y1: mid + 1 }, maxVolume)
    ];
  }
  // dx=dy=dz=1 (volume=1) сюда никогда не попадёт - выше уже отфильтровано
  return [box];
}

function translateBox(box, origin) {
  return {
    x1: box.x1 + origin.x, y1: box.y1 + origin.y, z1: box.z1 + origin.z,
    x2: box.x2 + origin.x, y2: box.y2 + origin.y, z2: box.z2 + origin.z,
    name: box.name, metadata: box.metadata
  };
}

function boxToCommand(box) {
  if (box.x1 === box.x2 && box.y1 === box.y2 && box.z1 === box.z2) {
    return `/setblock ${box.x1} ${box.y1} ${box.z1} ${box.name} ${box.metadata}`;
  }
  return `/fill ${box.x1} ${box.y1} ${box.z1} ${box.x2} ${box.y2} ${box.z2} ${box.name} ${box.metadata}`;
}

/**
 * Собирает итоговый план команд для схемы: делит на solid/attached (см.
 * splitSchemaByAttachment), жадно схлопывает ТОЛЬКО solid в боксы,
 * разрезает боксы больше 32768 блоков, переводит в абсолютные координаты
 * относительно origin и форматирует в команды /fill и /setblock; attached
 * блоки идут после, по одному, как есть, в порядке из файла.
 */
function buildFillCommands(schema, origin) {
  const { solid, attached } = splitSchemaByAttachment(schema);

  const boxes = buildBoxes(solid);
  const splitBoxes = boxes.flatMap(splitBox);
  const solidCommands = splitBoxes
    .map((box) => translateBox(box, origin))
    .map(boxToCommand);
  const singleCommandCount = splitBoxes
    .filter((box) => box.x1 === box.x2 && box.y1 === box.y2 && box.z1 === box.z2)
    .length;

  const attachedCommands = buildAttachedCommands(attached, origin);

  return {
    commands: [...solidCommands, ...attachedCommands],
    commandCount: solidCommands.length + attachedCommands.length,
    boxCount: boxes.length,
    solidCommandCount: solidCommands.length,
    singleCommandCount,
    attachedCount: attached.length
  };
}

/**
 * Габаритный параллелепипед схемы в ЛОКАЛЬНЫХ координатах (как есть в
 * JSON, без origin). Точки с "air" учитываются как обычные точки схемы -
 * они часть габарита. Непустая схема гарантирована вызывающим кодом.
 */
function computeBoundingBox(schema) {
  if (schema.length === 0) {
    throw new Error('схема пуста - нет точек для расчёта габаритов');
  }
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const entry of schema) {
    if (entry.x < minX) minX = entry.x;
    if (entry.x > maxX) maxX = entry.x;
    if (entry.y < minY) minY = entry.y;
    if (entry.y > maxY) maxY = entry.y;
    if (entry.z < minZ) minZ = entry.z;
    if (entry.z > maxZ) maxZ = entry.z;
  }
  return { minX, maxX, minY, maxY, minZ, maxZ };
}

/**
 * Бокс расчистки: габарит схемы + запас (1 блок по бокам X/Z, 3 сверху
 * по Y; снизу без запаса - там будет основание). Сразу в АБСОЛЮТНЫХ
 * координатах (с учётом origin), заполняется воздухом.
 */
function buildClearBox(bbox, origin) {
  return {
    x1: bbox.minX - 1 + origin.x, x2: bbox.maxX + 1 + origin.x,
    y1: bbox.minY + origin.y, y2: bbox.maxY + 3 + origin.y,
    z1: bbox.minZ - 1 + origin.z, z2: bbox.maxZ + 1 + origin.z,
    name: 'air', metadata: 0
  };
}

/**
 * Бокс основания: footprint схемы (без запаса, X/Z как в bbox) от
 * (baseY - 1) вниз до foundationToY, materialSpec - строка вида "stone"
 * или "stone:1". baseY - это origin.y (базовая точка, переданная при
 * запуске). Возвращает null, если основание не нужно (foundationToY уже
 * не ниже уровня, на котором стоит схема).
 */
function buildFoundationBox(bbox, origin, foundationToY, materialSpec) {
  const { name, metadata } = parseBlockSpec(materialSpec);
  const topY = origin.y - 1;
  if (foundationToY > topY) return null;
  return {
    x1: bbox.minX + origin.x, x2: bbox.maxX + origin.x,
    y1: foundationToY, y2: topY,
    z1: bbox.minZ + origin.z, z2: bbox.maxZ + origin.z,
    name, metadata
  };
}

/**
 * Разрезает произвольный (уже абсолютный) бокс по лимиту /fill и
 * форматирует в команды - общий путь для расчистки/основания/схемы/--wipe.
 * maxVolume необязателен - см. splitBox.
 */
function boxToCommands(box, maxVolume) {
  return splitBox(box, maxVolume).map(boxToCommand);
}

module.exports = {
  buildBoxes,
  splitBox,
  boxVolume,
  buildFillCommands,
  loadSchema,
  parseBlockSpec,
  computeBoundingBox,
  buildClearBox,
  buildFoundationBox,
  boxToCommands,
  isAttachedBlock,
  splitSchemaByAttachment,
  buildAttachedCommands,
  rotateSchema,
  isDirectionalMetadataBlock,
  hasDirectionalMetadataBlocks
};
