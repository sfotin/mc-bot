'use strict';

process.on('uncaughtException', (e) => console.error('UNCAUGHT:', e));
process.on('unhandledRejection', (e) => console.error('REJECTION:', e));

const fs = require('fs');
const path = require('path');
const { Vec3 } = require('vec3');

// Патчит prismarine-item раньше, чем его подхватит require('mineflayer') -
// см. index.js/lib/patch-items.js: без этого mineflayer падает на
// неизвестных (модовых) предметах в пакетах инвентаря при спавне.
require('./lib/patch-items');

const config = require('./config');
const { createBot } = require('./lib/connect');
const { log } = require('./lib/utils');

// Высота наблюдения (см. задание) - режим наблюдателя, полёт без коллизий,
// достаточно высоко, чтобы не упираться в рельеф/постройки.
const SURVEY_FLY_Y = 150;

// Мир 1.12.2 - блоки Y от 0 до 255 (см. lib/utils.js? нет - см. mineflayer
// bot.game.height=256, bot.game.minY=0 по умолчанию для доверсийных миров).
const WORLD_MIN_Y = 0;
const WORLD_MAX_Y = 255;

// Размер одной "плитки" сетки телепортов в чанках. Сервер шлёт клиенту
// только чанки в пределах СВОЕЙ дальности прорисовки (view-distance),
// значение которой мы не знаем и не можем узнать по протоколу 1.12.2 -
// поэтому берём заведомо небольшую плитку (64 блока = 4 чанка), с большим
// запасом умещающуюся в дальность прорисовки почти любого сервера, вместо
// того чтобы угадывать точное число. waitForColumns ниже всё равно ждёт
// именно нужные чанки, а не какой-то фиксированный радиус.
const TILE_CHUNKS = 4;
const TILE_BLOCKS = TILE_CHUNKS * 16;

const CHUNK_LOAD_TIMEOUT_MS = 20000;
const GAMEMODE_CONFIRM_TIMEOUT_MS = 5000;
const TELEPORT_CONFIRM_TIMEOUT_MS = 5000;

const WATER_NAMES = new Set(['water', 'flowing_water']);

/**
 * CLI: node survey.js X1 Z1 X2 Z2 [--name=имя]
 * Бокс по двум углам в любом порядке (какой угол первый/второй - неважно).
 * --name - имя выходного файла survey/<имя>.json, по умолчанию "survey".
 */
function parseCli(argv) {
  const args = argv.slice(2);
  const positional = [];
  const flags = {};
  for (const arg of args) {
    if (arg.startsWith('--')) {
      const eq = arg.indexOf('=');
      if (eq === -1) flags[arg.slice(2)] = true;
      else flags[arg.slice(2, eq)] = arg.slice(eq + 1);
    } else {
      positional.push(arg);
    }
  }
  return { positional, flags };
}

function parseSurveyRequest(argv) {
  const { positional, flags } = parseCli(argv);
  if (positional.length < 4) {
    console.error('Использование: node survey.js X1 Z1 X2 Z2 [--name=имя]');
    process.exit(1);
  }

  const coords = positional.slice(0, 4);
  const nums = coords.map(Number);
  if (nums.some((n) => Number.isNaN(n))) {
    console.error(`ОШИБКА: координаты должны быть числами: ${coords.join(' ')}`);
    process.exit(1);
  }
  const [x1, z1, x2, z2] = nums.map(Math.floor);

  const x0 = Math.min(x1, x2);
  const z0 = Math.min(z1, z2);
  const w = Math.max(x1, x2) - x0 + 1;
  const h = Math.max(z1, z2) - z0 + 1;

  const name = typeof flags.name === 'string' ? flags.name : 'survey';

  return { x0, z0, w, h, name };
}

/**
 * Ждёт одно наступление event на emitter, для которого (если задан) predicate
 * возвращает true; иначе - таймаут timeoutMs, промис отклоняется с понятной
 * причиной. Слушатель навешивается СИНХРОННО до возврата (исполнитель
 * промиса выполняется сразу), поэтому вызывать безопасно непосредственно
 * перед отправкой команды, которая должна вызвать это событие.
 */
function waitForEvent(emitter, event, timeoutMs, predicate) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      emitter.removeListener(event, onEvent);
      reject(new Error(`таймаут ожидания события "${event}" (${timeoutMs} мс)`));
    }, timeoutMs);

    function onEvent(...args) {
      if (predicate && !predicate(...args)) return;
      clearTimeout(timer);
      emitter.removeListener(event, onEvent);
      resolve(args);
    }

    emitter.on(event, onEvent);
  });
}

/**
 * Ждёт, пока в bot.world появятся ВСЕ чанк-колонны, покрывающие прямоугольник
 * [x0,x1]x[z0,z1] (блочные координаты, границы включительно). Если часть не
 * пришла за timeoutMs - не бросает, а возвращает список непришедших чанков
 * (в чанковых координатах "cx,cz"), чтобы вызывающий код мог пометить эти
 * колонны как незагруженные и продолжить (см. §4.6.1 в survey.js).
 */
function waitForColumns(bot, x0, x1, z0, z1, timeoutMs) {
  const pending = new Set();
  const cx0 = x0 >> 4;
  const cx1 = x1 >> 4;
  const cz0 = z0 >> 4;
  const cz1 = z1 >> 4;
  for (let cx = cx0; cx <= cx1; cx++) {
    for (let cz = cz0; cz <= cz1; cz++) {
      if (!bot.world.getColumnAt(new Vec3(cx * 16, 0, cz * 16))) {
        pending.add(`${cx},${cz}`);
      }
    }
  }
  if (pending.size === 0) return Promise.resolve([]);

  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      bot.world.removeListener('chunkColumnLoad', onLoad);
      resolve([...pending]);
    }, timeoutMs);

    function onLoad(columnCorner) {
      const key = `${columnCorner.x >> 4},${columnCorner.z >> 4}`;
      if (pending.delete(key) && pending.size === 0) {
        clearTimeout(timer);
        bot.world.removeListener('chunkColumnLoad', onLoad);
        resolve([]);
      }
    }
    bot.world.on('chunkColumnLoad', onLoad);
  });
}

/**
 * Верхний блок колонны (x,z), пропуская воздух и воду: top (Y), block (имя,
 * "unknown" для нераспознанных модовых блоков) и water (Y поверхности воды,
 * если сверху есть вода, иначе null). Листва НЕ пропускается - она и есть
 * искомая поверхность, выгружается как обычный блок под своим именем.
 */
function surveyColumn(bot, x, z) {
  let waterY = null;
  for (let y = WORLD_MAX_Y; y >= WORLD_MIN_Y; y--) {
    const block = bot.blockAt(new Vec3(x, y, z));
    const name = block ? (block.name || 'unknown') : 'air';
    if (name === 'air') continue;
    if (WATER_NAMES.has(name)) {
      if (waterY === null) waterY = y;
      continue;
    }
    return { top: y, block: name, water: waterY };
  }
  return { top: null, block: null, water: waterY };
}

/**
 * Переключает бота в режим наблюдателя (spectator, id 3) - полёт без
 * коллизий, идеально для облёта рельефа сверху. Требует OP; если сервер не
 * подтвердил смену режима (событие 'game' с gameMode==='spectator') за
 * GAMEMODE_CONFIRM_TIMEOUT_MS - бросает понятную ошибку.
 */
async function ensureSpectatorMode(bot) {
  if (bot.game.gameMode === 'spectator') return;
  const confirmed = waitForEvent(bot, 'game', GAMEMODE_CONFIRM_TIMEOUT_MS, () => bot.game.gameMode === 'spectator');
  bot.chat('/gamemode 3');
  try {
    await confirmed;
  } catch (err) {
    throw new Error('Не удалось переключиться в режим наблюдателя (/gamemode 3) - похоже, у бота нет прав OP.');
  }
}

/**
 * Телепортирует бота в (x,y,z) через /tp и ждёт подтверждения от сервера
 * (событие 'forcedMove' у mineflayer - оно стреляет на входящий пакет
 * "Player Position And Look", которым сервер отвечает на /tp). Требует OP;
 * без подтверждения за TELEPORT_CONFIRM_TIMEOUT_MS - понятная ошибка.
 */
async function teleportTo(bot, x, y, z) {
  const moved = waitForEvent(bot, 'forcedMove', TELEPORT_CONFIRM_TIMEOUT_MS);
  bot.chat(`/tp ${bot.username} ${x} ${y} ${z}`);
  try {
    await moved;
  } catch (err) {
    throw new Error(`Не удалось телепортироваться в (${x}, ${y}, ${z}) - похоже, у бота нет прав OP на /tp.`);
  }
}

/**
 * Основной проход съёмки: делит бокс на плитки TILE_BLOCKS x TILE_BLOCKS,
 * на каждой телепортирует бота в её центр на высоту SURVEY_FLY_Y, ждёт
 * загрузки нужных чанков и сканирует все колонны плитки (см. surveyColumn).
 * Возвращает итоговый объект схемы рельефа (см. формат в BOT.md).
 */
async function runSurvey(bot, request) {
  const { x0, z0, w, h, name } = request;
  const x1 = x0 + w - 1;
  const z1 = z0 + h - 1;

  await ensureSpectatorMode(bot);

  const top = new Array(w * h).fill(null);
  const blockNames = new Array(w * h).fill(null);
  const water = new Array(w * h).fill(null);

  let unloadedCount = 0;
  let underwaterCount = 0;
  let minTop = Infinity;
  let maxTop = -Infinity;

  const tileXStarts = [];
  for (let tx = x0; tx <= x1; tx += TILE_BLOCKS) tileXStarts.push(tx);
  const tileZStarts = [];
  for (let tz = z0; tz <= z1; tz += TILE_BLOCKS) tileZStarts.push(tz);
  const totalTiles = tileXStarts.length * tileZStarts.length;
  let tileIndex = 0;

  for (const tz of tileZStarts) {
    const tzEnd = Math.min(tz + TILE_BLOCKS - 1, z1);
    for (const tx of tileXStarts) {
      tileIndex++;
      const txEnd = Math.min(tx + TILE_BLOCKS - 1, x1);
      const centerX = Math.floor((tx + txEnd) / 2);
      const centerZ = Math.floor((tz + tzEnd) / 2);

      log(`[survey] Плитка ${tileIndex}/${totalTiles}: X ${tx}..${txEnd}, Z ${tz}..${tzEnd} -> телепорт (${centerX}, ${SURVEY_FLY_Y}, ${centerZ})`);
      await teleportTo(bot, centerX, SURVEY_FLY_Y, centerZ);

      const missing = await waitForColumns(bot, tx, txEnd, tz, tzEnd, CHUNK_LOAD_TIMEOUT_MS);
      const missingChunks = new Set(missing);
      if (missingChunks.size > 0) {
        log(`[survey] ВНИМАНИЕ: не загрузились чанки (${missingChunks.size}): ${missing.join('; ')}`);
      }

      for (let z = tz; z <= tzEnd; z++) {
        for (let x = tx; x <= txEnd; x++) {
          const idx = (z - z0) * w + (x - x0);
          if (missingChunks.has(`${x >> 4},${z >> 4}`)) {
            unloadedCount++;
            continue;
          }
          const col = surveyColumn(bot, x, z);
          top[idx] = col.top;
          blockNames[idx] = col.block;
          water[idx] = col.water;
          if (col.top !== null) {
            if (col.top < minTop) minTop = col.top;
            if (col.top > maxTop) maxTop = col.top;
          }
          if (col.water !== null) underwaterCount++;
        }
      }
    }
  }

  const result = { x0, z0, w, h, top, block: blockNames, water };

  const surveyDir = path.resolve(__dirname, 'survey');
  fs.mkdirSync(surveyDir, { recursive: true });
  const outPath = path.join(surveyDir, `${name}.json`);
  fs.writeFileSync(outPath, JSON.stringify(result));

  log(`[survey] Готово: ${outPath} (${w}x${h} = ${w * h} колонн)`);
  log(`[survey] Высота: мин=${minTop === Infinity ? 'н/д' : minTop}, макс=${maxTop === -Infinity ? 'н/д' : maxTop}`);
  log(`[survey] Колонн под водой: ${underwaterCount}`);
  log(`[survey] Незагруженных колонн: ${unloadedCount}`);

  return result;
}

function start() {
  if (!config.host) {
    console.error('ОШИБКА: MC_HOST не задан. Скопируй .env.example в .env и укажи адрес сервера.');
    process.exit(1);
  }

  const request = parseSurveyRequest(process.argv);
  log(`[survey] Съёмка ${request.w}x${request.h} блоков от (${request.x0}, ${request.z0}), имя "${request.name}"`);

  const bot = createBot(config);

  bot.once('spawn', async () => {
    try {
      await runSurvey(bot, request);
      process.exit(0);
    } catch (err) {
      console.error(`[survey] ОШИБКА: ${err.message}`);
      process.exit(1);
    }
  });

  bot.on('kicked', (reason) => {
    console.error('KICKED:', JSON.stringify(reason));
    process.exit(1);
  });

  bot.on('error', (err) => {
    console.error('ERROR:', err);
    process.exit(1);
  });
}

start();
