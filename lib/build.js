'use strict';

const { Vec3 } = require('vec3');
const { goals } = require('mineflayer-pathfinder');
const { sleep, log } = require('./utils');

// Смещения соседних блоков в порядке предпочтения: сначала снизу
// (естественная стойка при постройке), затем по сторонам, затем сверху.
const NEIGHBOR_OFFSETS = [
  new Vec3(0, -1, 0),
  new Vec3(1, 0, 0),
  new Vec3(-1, 0, 0),
  new Vec3(0, 0, 1),
  new Vec3(0, 0, -1),
  new Vec3(0, 1, 0)
];

// Первый слот хотбара (диапазон инвентаря 36-44) - сюда кладём текущий
// материал через bot.creative.setInventorySlot.
const MATERIAL_SLOT = 36;
const MATERIAL_QUICKBAR_INDEX = MATERIAL_SLOT - 36;

// Небольшая пауза после setInventorySlot, чтобы сервер применил смену слота
// до того, как бот попробует поставить блок.
const SLOT_SETTLE_DELAY_MS = 250;

function isReplaceable(block) {
  if (!block) return true;
  return block.boundingBox === 'empty';
}

function findPlacementReference(bot, targetPos) {
  for (const offset of NEIGHBOR_OFFSETS) {
    const neighborPos = targetPos.minus(offset);
    const neighborBlock = bot.blockAt(neighborPos);
    if (neighborBlock && neighborBlock.boundingBox === 'block') {
      const faceVector = offset; // targetPos = neighborPos + offset
      return { referenceBlock: neighborBlock, faceVector };
    }
  }
  return null;
}

async function moveNear(bot, pos, range) {
  const goal = new goals.GoalNear(pos.x, pos.y, pos.z, range);
  await bot.pathfinder.goto(goal);
}

/**
 * Разбирает запись схемы вида "stone" или "stone:1" (в 1.12.2 варианты
 * блока - например, разные породы дерева или камня - различаются
 * одним и тем же id, но разной metadata).
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

function getMcData(bot) {
  if (!bot._mcDataCache) {
    bot._mcDataCache = require('minecraft-data')(bot.version);
  }
  return bot._mcDataCache;
}

function getItemClass(bot) {
  if (!bot._itemClassCache) {
    bot._itemClassCache = require('prismarine-item')(bot.version);
  }
  return bot._itemClassCache;
}

function isCreative(bot) {
  return !!(bot.game && bot.game.gameMode === 'creative');
}

function warnNotCreative(bot) {
  if (bot._nonCreativeWarned) return;
  bot._nonCreativeWarned = true;
  const mode = (bot.game && bot.game.gameMode) || 'неизвестен';
  const msg = `Режим игры "${mode}" - не creative, bot.creative.setInventorySlot недоступен. ` +
    'Буду искать нужные блоки в инвентаре (survival-режим).';
  log(msg);
  bot.chat(msg);
}

/**
 * Убеждается, что в руке у бота лежит именно нужный материал (name+metadata).
 * Если в руке уже он - ничего не делает. Если нет и бот в creative - кладёт
 * предмет в фиксированный слот хотбара (36) через bot.creative.setInventorySlot
 * и выбирает его через bot.setQuickBarSlot; это происходит только при смене
 * материала (кэш bot._materialCache), а не перед каждой установкой блока.
 * В survival ищет такой предмет в инвентаре (запасной путь).
 */
async function ensureHeldMaterial(bot, name, metadata) {
  const mcData = getMcData(bot);
  const blockData = mcData.blocksByName[name];
  if (!blockData) {
    return { ok: false, reason: `неизвестный блок "${name}" для версии ${bot.version}` };
  }
  const id = blockData.id;

  const held = bot.heldItem;
  if (held && held.type === id && (held.metadata || 0) === metadata) {
    return { ok: true };
  }

  if (isCreative(bot)) {
    const cache = bot._materialCache;
    if (cache && cache.id === id && cache.metadata === metadata) {
      // Материал уже лежит в слоте хотбара - просто выбрать его, без setInventorySlot
      bot.setQuickBarSlot(MATERIAL_QUICKBAR_INDEX);
      return { ok: true };
    }

    const Item = getItemClass(bot);
    const item = new Item(id, 64, metadata);

    try {
      await bot.creative.setInventorySlot(MATERIAL_SLOT, item);
    } catch (err) {
      return { ok: false, reason: `bot.creative.setInventorySlot не сработал: ${err.message}` };
    }

    await sleep(SLOT_SETTLE_DELAY_MS);

    bot.setQuickBarSlot(MATERIAL_QUICKBAR_INDEX);
    bot._materialCache = { id, metadata };
    return { ok: true };
  }

  warnNotCreative(bot);

  const item = bot.inventory.items().find((i) => i.type === id && (i.metadata || 0) === metadata);
  if (!item) {
    const suffix = metadata ? `:${metadata}` : '';
    return { ok: false, reason: `блок ${name}${suffix} не найден в инвентаре` };
  }
  try {
    await bot.equip(item, 'hand');
    return { ok: true };
  } catch (err) {
    return { ok: false, reason: `не удалось взять предмет в руку: ${err.message}` };
  }
}

/**
 * Ставит один блок blockSpec ("stone" или "stone:1") в точке pos
 * (Vec3, абсолютные координаты). Возвращает { ok, skipped?, reason? }.
 */
async function placeBlockAt(bot, pos, blockSpec, options = {}) {
  const range = options.range || 4;
  const { name, metadata } = parseBlockSpec(blockSpec);

  const existing = bot.blockAt(pos);
  if (existing && existing.name === name && (existing.metadata || 0) === metadata) {
    return { ok: true, skipped: true, reason: 'уже стоит нужный блок' };
  }
  if (existing && existing.boundingBox === 'block') {
    return { ok: false, reason: `место занято блоком ${existing.name}` };
  }

  try {
    await moveNear(bot, pos, range);
  } catch (err) {
    return { ok: false, reason: `не удалось подойти к точке: ${err.message}` };
  }

  const placement = findPlacementReference(bot, pos);
  if (!placement) {
    return { ok: false, reason: 'нет соседнего блока, на который можно опереться' };
  }

  const material = await ensureHeldMaterial(bot, name, metadata);
  if (!material.ok) {
    return material;
  }

  try {
    await bot.placeBlock(placement.referenceBlock, placement.faceVector);
    return { ok: true };
  } catch (err) {
    return { ok: false, reason: `ошибка установки: ${err.message}` };
  }
}

/**
 * Выкладывает схему (массив {x,y,z,block}) относительно точки origin.
 * schema сортируется по высоте (y), чтобы бот строил снизу вверх.
 */
async function buildSchema(bot, schema, origin, config) {
  const items = schema.slice().sort((a, b) => a.y - b.y);
  const total = items.length;
  let placed = 0;
  let skipped = 0;
  let failed = 0;

  if (!isCreative(bot)) {
    warnNotCreative(bot);
  }

  bot.chat(`Начинаю постройку: ${total} блоков от точки ${origin.x} ${origin.y} ${origin.z}`);

  for (let i = 0; i < items.length; i++) {
    const entry = items[i];
    const pos = origin.offset(entry.x, entry.y, entry.z);

    const result = await placeBlockAt(bot, pos, entry.block, {
      range: config.gotoRangeBlocks + 3
    });

    if (result.ok && !result.skipped) {
      placed++;
      log(`[${i + 1}/${total}] Установлен ${entry.block} в (${pos.x}, ${pos.y}, ${pos.z})`);
    } else if (result.ok && result.skipped) {
      skipped++;
      log(`[${i + 1}/${total}] Пропущен ${entry.block} в (${pos.x}, ${pos.y}, ${pos.z}): ${result.reason}`);
    } else {
      failed++;
      log(`[${i + 1}/${total}] ОШИБКА ${entry.block} в (${pos.x}, ${pos.y}, ${pos.z}): ${result.reason}`);
      bot.chat(`Не удалось поставить блок ${entry.block} в (${pos.x}, ${pos.y}, ${pos.z}): ${result.reason}`);
    }

    if (i < items.length - 1) {
      await sleep(config.placeDelayMs);
    }
  }

  bot.chat(`Постройка завершена: поставлено ${placed}, пропущено ${skipped}, ошибок ${failed} из ${total}.`);
  log(`Постройка завершена: поставлено ${placed}, пропущено ${skipped}, ошибок ${failed} из ${total}.`);
}

module.exports = { placeBlockAt, buildSchema, findPlacementReference, parseBlockSpec };
