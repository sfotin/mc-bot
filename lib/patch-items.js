'use strict';

/**
 * Патчит prismarine-item ДО того, как его подхватят mineflayer/prismarine-registry
 * (поэтому этот файл требуется первым в index.js, раньше require('mineflayer')).
 *
 * На модовых серверах (Applied Energistics, IndustrialCraft и т.п.) в пакетах
 * инвентаря/окон прилетают id предметов, которых нет в стандартном
 * minecraft-data. prismarine-item в таком случае либо бросает исключение,
 * либо отдаёт неинформативный объект name: 'unknown' без указания id, по
 * которому вообще невозможно понять, что не так. Здесь вместо этого всегда
 * создаётся заглушка: name вида "unknown_<id>", displayName "Unknown Item".
 *
 * Патчатся две точки, потому что они не покрывают друг друга:
 *  - конструктор Item (через Proxy с ловушкой construct) - работает для
 *    любого внешнего `new Item(...)`, сделанного кодом, получившим этот
 *    класс через require('prismarine-item')(version/registry) ПОСЛЕ патча
 *    (mineflayer, minecraft-protocol-forge, наш lib/build.js и т.д.);
 *  - Item.fromNotch - десериализация предметов, присланных сервером
 *    (обновления слотов инвентаря и т.п.). Внутри исходного fromNotch
 *    новый Item всегда создаётся через внутреннюю (непроксированную)
 *    ссылку на класс из замыкания prismarine-item, поэтому Proxy на
 *    конструктор её не перехватывает - нужен отдельный патч.
 */

const PRISMARINE_ITEM_PATH = require.resolve('prismarine-item');
const originalLoader = require(PRISMARINE_ITEM_PATH);

const warnedIds = new Set();

function warnUnknownId(id) {
  if (warnedIds.has(id)) return;
  warnedIds.add(id);
  console.log(`[patch-items] Неизвестный id предмета: ${id} - подставлена заглушка unknown_${id}`);
}

function stubifyIfUnknown(item) {
  if (!item) return item;
  if (item.name === 'unknown' || item.name == null) {
    const id = item.type;
    warnUnknownId(id);
    item.name = `unknown_${id}`;
    item.displayName = 'Unknown Item';
    if (!item.stackSize) item.stackSize = 1;
  }
  return item;
}

function patchedLoader(registryOrVersion) {
  const OriginalItem = originalLoader(registryOrVersion);
  const originalFromNotch = OriginalItem.fromNotch;

  const PatchedItem = new Proxy(OriginalItem, {
    construct(target, args) {
      let instance;
      try {
        instance = Reflect.construct(target, args);
      } catch (err) {
        // На случай, если конкретная версия prismarine-item всё же бросает
        // assert/ошибку на неизвестном id - строим минимальную заглушку сами,
        // без падения процесса.
        const [type, count, metadata] = args;
        warnUnknownId(type);
        instance = Object.create(target.prototype);
        instance.type = type;
        instance.count = count;
        instance.metadata = metadata || 0;
        instance.nbt = null;
        instance.name = `unknown_${type}`;
        instance.displayName = 'Unknown Item';
        instance.stackSize = 1;
        return instance;
      }
      return stubifyIfUnknown(instance);
    }
  });

  PatchedItem.fromNotch = function (...args) {
    try {
      const item = originalFromNotch.apply(OriginalItem, args);
      return stubifyIfUnknown(item);
    } catch (err) {
      const networkItem = args[0] || {};
      const type = networkItem.itemId ?? networkItem.blockId ?? networkItem.network_id ?? null;
      warnUnknownId(type);
      return {
        type,
        count: networkItem.itemCount ?? networkItem.count ?? 1,
        metadata: networkItem.itemDamage ?? networkItem.metadata ?? 0,
        nbt: null,
        name: `unknown_${type}`,
        displayName: 'Unknown Item',
        stackSize: 1
      };
    }
  };

  return PatchedItem;
}

module.exports = patchedLoader;

// Подменяем то, что уже лежит в require-кэше по этому пути: любой дальнейший
// require('prismarine-item') (внутри mineflayer, minecraft-protocol-forge,
// наших lib/*) получит именно patchedLoader, независимо от того, кто и
// когда вызовет require() повторно - кэш общий на весь процесс.
require.cache[PRISMARINE_ITEM_PATH].exports = patchedLoader;
