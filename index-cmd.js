'use strict';

process.on('uncaughtException', (e) => console.error('UNCAUGHT:', e));
process.on('unhandledRejection', (e) => console.error('REJECTION:', e));

const fs = require('fs');
const path = require('path');

const config = require('./config');
const { createRawClient } = require('./lib/connect-raw');
const {
  buildFillCommands,
  loadSchema,
  computeBoundingBox,
  buildClearBox,
  buildFoundationBox,
  boxToCommands,
  boxVolume,
  rotateSchema,
  hasDirectionalMetadataBlocks
} = require('./lib/fill-plan');
const { log, sleep } = require('./lib/utils');

// Лимит длины chat-пакета в 1.12.2 (протокольная строка String(256))
const MAX_CHAT_LENGTH = 256;

// Автопереподключение: до 10 попыток подряд добраться до login, пауза
// между ними 3 сек. Счётчик сбрасывается на каждом успешном login -
// это НЕ общий лимит на весь запуск, а лимит на "полосу неудач". Если
// разрыв произошёл после login и схема ещё не отправлена целиком - после
// восстановления связи рассылка продолжается с sentIndex+1 (см. connectAttempt
// ниже), а не с начала.
const MAX_CONNECT_ATTEMPTS = 10;
const RECONNECT_DELAY_MS = 3000;

// Сторожевой таймер: если за это время от сервера не пришло вообще ни
// одного пакета (любого типа, не только keep-alive) - соединение считаем
// мёртвым и рвём сами, не дожидаясь TCP-таймаута ОС (который может быть
// минутами). Без этого зависший сервер выглядит как "код работает, но
// молчит" бесконечно.
const WATCHDOG_TIMEOUT_MS = 15000;

// Небольшая пауза после того, как игрок подтверждённо жив и заспавнен
// (см. waitUntilReadyThenBeginWork ниже), перед тем как начать слать
// команды - даём миру/чанкам вокруг игрока чуть осесть.
const READY_PAUSE_MS = 1000;

// Сколько ждать подтверждения /gamemode 3 (пакет game_state_change,
// reason=3) и /tp (пакет position) - если сервер не ответил за это время,
// скорее всего у бота нет OP. Не привязано к config - это таймаут
// протокольного рукопожатия команды, а не поведенческая настройка.
const GAMEMODE_CONFIRM_TIMEOUT_MS = 5000;
const TELEPORT_CONFIRM_TIMEOUT_MS = 5000;

// Сколько ждать ответов сервера на уже отправленные команды после того,
// как последняя команда ушла, прежде чем считать сводку и завершаться -
// с запасом на сетевую задержку и то, что сервер отвечает не мгновенно.
const FINAL_DRAIN_TIMEOUT_MS = 10000;

/**
 * CLI: node index-cmd.js [схема.json X Y Z] [--prepare] [--foundation-to=Y] [--foundation-material=stone] [--rotate=0|90|180|270]
 *      node index-cmd.js --wipe X1 Y1 Z1 X2 Y2 Z2 [--ground=Y]
 *      node index-cmd.js --retry logs/failed-<схема>-<время>.txt
 * Без позиционных аргументов - стандартный тест "продержаться 60 сек и /setblock".
 * С позиционными X Y Z после имени файла схемы - грузим схему, X Y Z -
 * базовая точка (origin), относительно которой отложены координаты схемы.
 *  --prepare - перед схемой расчистить площадку воздухом (см. buildSchemaCommandList).
 *  --foundation-to=Y - вместе с --prepare залить основание материалом
 *    вниз до этого Y (по умолчанию нет - основание не строится).
 *  --foundation-material=имя[:metadata] - материал основания (по умолчанию stone).
 *  --rotate=0|90|180|270 - поворот схемы вокруг вертикальной оси по часовой
 *    стрелке (если смотреть сверху), по умолчанию 0. Применяется к локальным
 *    координатам схемы до перевода в абсолютные и до схлопывания в боксы
 *    (см. rotateSchema в lib/fill-plan.js). Metadata лестниц, дверей (нижняя
 *    половина), факелов, лестниц-стремянок/сундуков/печей, кнопок и рычага
 *    при повороте пересчитывается; у табличек и рельс - нет (см. isDirectionalMetadataBlock).
 *  --wipe X1 Y1 Z1 X2 Y2 Z2 - режим зачистки (см. buildWipeCommandList):
 *    заливает указанный объём (углы бокса, порядок координат не важен)
 *    воздухом; если задан --ground=Y - всё строго ниже Y заливает stone,
 *    а от Y и выше - воздухом. Несовместим с режимом схемы.
 *  --retry <файл> - повторно шлёт команды из текстового файла (одна
 *    команда на строку - формат тот же, что у logs/failed-*.txt, см.
 *    §11 «Опыт» в BOT.md), той же логикой телепорта/зон и учёта ответов,
 *    что и обычная схема. Несовместим со схемой и --wipe.
 *
 * Перед стройкой (кроме тестового режима без схемы/--wipe/--retry) бот
 * сам встаёт на площадку: /gamemode 3 (наблюдатель) и /tp в центр её
 * габарита на высоту max(Y)+10, чтобы сервер догрузил нужные чанки -
 * см. buildZonePlan/beginWork. Если габарит больше config.tpRenderRadiusBlocks*2,
 * стройка режется на зоны со своим /tp перед каждой.
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

const VALID_ROTATE_FLAG_VALUES = [0, 90, 180, 270];

/**
 * Разбирает и валидирует --rotate. В отличие от кривых позиционных X/Y/Z
 * (которые молча превращают запрос в "не схема, а обычный тестовый режим"),
 * здесь пользователь явно указал флаг - тихо его проигнорировать значило
 * бы построить схему не в той ориентации, которую просили, даже не
 * заметив ошибку. Поэтому недопустимое значение - это fail-fast, как и
 * битый файл схемы в loadSchemaOrExit.
 */
function parseRotateFlag(flags) {
  if (flags.rotate === undefined) return 0;
  const v = Number(flags.rotate);
  if (!VALID_ROTATE_FLAG_VALUES.includes(v)) {
    console.error(`[raw] ОШИБКА: --rotate=${flags.rotate} недопустим - разрешены только 0, 90, 180, 270.`);
    process.exit(1);
  }
  return v;
}

function parseCliSchemaRequest(argv) {
  const { positional, flags } = parseCli(argv);
  if (positional.length < 4) return null;
  const [fileName, xs, ys, zs] = positional;
  const x = Number(xs);
  const y = Number(ys);
  const z = Number(zs);
  if ([x, y, z].some((n) => Number.isNaN(n))) return null;

  const origin = { x: Math.floor(x), y: Math.floor(y), z: Math.floor(z) };
  const prepare = flags.prepare === true || flags.prepare === 'true';
  const rotate = parseRotateFlag(flags);

  let foundationTo = null;
  if (flags['foundation-to'] !== undefined) {
    const v = Number(flags['foundation-to']);
    if (!Number.isNaN(v)) foundationTo = Math.floor(v);
  }

  const foundationMaterial = typeof flags['foundation-material'] === 'string'
    ? flags['foundation-material']
    : 'stone';

  return { fileName, origin, prepare, foundationTo, foundationMaterial, rotate };
}

/**
 * Разбирает --wipe X1 Y1 Z1 X2 Y2 Z2 [--ground=Y]. Возвращает null, если
 * флага --wipe нет вовсе (тогда CLI парсится дальше как схема/тестовый
 * режим). А вот если --wipe указан явно, но аргументы кривые - это
 * fail-fast (как и --rotate выше): молча свалиться в тестовый режим при
 * опечатке в координатах значило бы 60 сек тишины вместо зачистки, и
 * пользователь не сразу поймёт, что вообще ничего не произошло.
 */
function parseCliWipeRequest(argv) {
  const { positional, flags } = parseCli(argv);
  if (flags.wipe !== true && flags.wipe !== 'true') return null;

  if (positional.length < 6) {
    console.error('[raw] ОШИБКА: --wipe требует 6 координат: X1 Y1 Z1 X2 Y2 Z2.');
    process.exit(1);
  }

  const coords = positional.slice(0, 6);
  const nums = coords.map(Number);
  if (nums.some((n) => Number.isNaN(n))) {
    console.error(`[raw] ОШИБКА: --wipe координаты должны быть числами: ${coords.join(' ')}`);
    process.exit(1);
  }
  const [x1, y1, z1, x2, y2, z2] = nums.map(Math.floor);

  let ground = null;
  if (flags.ground !== undefined) {
    const g = Number(flags.ground);
    if (Number.isNaN(g)) {
      console.error(`[raw] ОШИБКА: --ground=${flags.ground} - не число.`);
      process.exit(1);
    }
    ground = Math.floor(g);
  }

  const box = {
    x1: Math.min(x1, x2), x2: Math.max(x1, x2),
    y1: Math.min(y1, y2), y2: Math.max(y1, y2),
    z1: Math.min(z1, z2), z2: Math.max(z1, z2)
  };

  return { box, ground };
}

/**
 * Разбирает --retry <файл>. Файл - результат прошлого запуска (одна
 * команда на строку, см. writeFailedCommandsFile) - пустые строки
 * пропускаются. Как и у --wipe/--rotate, кривые аргументы - fail-fast.
 */
function parseCliRetryRequest(argv) {
  const { positional, flags } = parseCli(argv);
  if (flags.retry !== true && flags.retry !== 'true') return null;

  const filePath = positional[0];
  if (!filePath) {
    console.error('[raw] ОШИБКА: --retry требует путь к файлу с командами.');
    process.exit(1);
  }

  let text;
  try {
    text = fs.readFileSync(filePath, 'utf8');
  } catch (err) {
    console.error(`[raw] ОШИБКА: не удалось прочитать файл --retry "${filePath}": ${err.message}`);
    process.exit(1);
  }

  const commands = text.split(/\r?\n/).map((line) => line.trim()).filter((line) => line.length > 0);
  if (commands.length === 0) {
    console.error(`[raw] ОШИБКА: файл --retry "${filePath}" пуст.`);
    process.exit(1);
  }

  return { filePath, commands };
}

// Протокольный лимит /fill в 1.12.2 (32*32*32). --wipe гонит только
// air/stone (не направленные блоки схем), поэтому режем боксы по этому
// лимиту напрямую, а не по более мелкому config.maxFillVolume - см.
// комментарий у MAX_FILL_VOLUME в lib/fill-plan.js.
const WIPE_MAX_FILL_VOLUME = 32768;

/**
 * Собирает список команд для --wipe: без --ground - один бокс воздуха на
 * весь объём; с --ground=Y - воздух режется на "ниже Y" (stone) и "Y и
 * выше" (air) по границе Y=ground (строго ниже - stone, см. CLI-доку
 * выше). Каждый получившийся бокс режется через splitBox по
 * WIPE_MAX_FILL_VOLUME и превращается в команды - тем же путём, что и
 * расчистка/основание схемы (см. boxToCommands в lib/fill-plan.js).
 */
function buildWipeCommandList({ box, ground }) {
  let boxes;

  if (ground === null) {
    boxes = [{ ...box, name: 'air', metadata: 0 }];
  } else {
    boxes = [];
    if (box.y1 < ground) {
      boxes.push({ ...box, y2: Math.min(box.y2, ground - 1), name: 'stone', metadata: 0 });
    }
    if (box.y2 >= ground) {
      boxes.push({ ...box, y1: Math.max(box.y1, ground), name: 'air', metadata: 0 });
    }
  }

  const commands = boxes.flatMap((b) => boxToCommands(b, WIPE_MAX_FILL_VOLUME));
  const totalVolume = boxes.reduce((sum, b) => sum + boxVolume(b), 0);
  log(`[raw] объём ${totalVolume} блоков -> ${commands.length} команд`);

  return commands;
}

/**
 * Очередь команд с троттлингом: не больше config.commandsPerSecond
 * сообщений в секунду. Отдельная функция, а не просто client.write
 * "как придётся" - схемы построек будущих версий будут кидать в неё
 * десятки/сотни команд подряд, и без троттлинга сервер отключит бота
 * за спам (та же причина, что и placeDelayMs в основном боте).
 */
function createCommandQueue(client, commandsPerSecond, onDispatch) {
  const queue = [];
  const intervalMs = Math.max(1, Math.round(1000 / commandsPerSecond));

  const timer = setInterval(() => {
    if (queue.length === 0) return;
    const message = queue.shift();
    try {
      client.write('chat', { message });
      log(`[raw] -> ${message}`);
      if (onDispatch) onDispatch(message);
    } catch (err) {
      log(`[raw] Ошибка отправки команды "${message}": ${err.message}`);
    }
  }, intervalMs);

  function enqueue(message) {
    if (typeof message !== 'string' || message.length === 0) return;
    if (message.length > MAX_CHAT_LENGTH) {
      log(`[raw] Команда длиннее ${MAX_CHAT_LENGTH} символов (${message.length}) - не отправлена: ${message}`);
      return;
    }
    queue.push(message);
  }

  function stop() {
    clearInterval(timer);
  }

  return { enqueue, stop };
}

/**
 * Склонение русского счётного существительного: 1 команда, 2 команды, 5 команд.
 */
function pluralizeRu(n, one, few, many) {
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}

/**
 * Клиентский chat-пакет несёт JSON чат-компонент (не сырой текст).
 * Без mineflayer/prismarine-chat достаточно грубо склеить text-поля.
 */
function simplifyChatComponent(jsonString) {
  try {
    const root = JSON.parse(jsonString);
    let out = '';
    (function walk(node) {
      if (!node) return;
      if (typeof node === 'string') { out += node; return; }
      if (node.text) out += node.text;
      if (Array.isArray(node.extra)) node.extra.forEach(walk);
    })(root);
    return out || jsonString;
  } catch (err) {
    return jsonString;
  }
}

/**
 * Ответы сервера на /fill и /setblock приходят как чат-компонент вида
 * {"translate":"commands.fill.success","with":[...]}, а не готовым
 * текстом - клиент без загруженного языкового файла не может (и не
 * должен) его "переводить" сам, но нам и не нужен текст: достаточно
 * ключа translate, чтобы понять, что это ЗА ответ. Возвращает ключ или
 * null, если сообщение не похоже на ответ команды (обычный текст,
 * составной компонент без translate и т.п.) - см. §11 «Опыт» в BOT.md,
 * как именно это используется для сопоставления с командой.
 */
function extractTranslateKey(jsonString) {
  try {
    const root = JSON.parse(jsonString);
    if (root && typeof root.translate === 'string') return root.translate;
  } catch (err) {
    // не JSON (сырой текст) - точно не ответ команды
  }
  return null;
}

// См. классификацию в задаче/§11 «Опыт»: успех - обычные success-ключи;
// "без изменений" - fill.failed и setblock.noChange, это НЕ ошибка (уже
// стоит нужный блок или объём и так пуст/полон); всё остальное с ключом,
// начинающимся на "commands." (значит это точно ответ на нашу команду,
// а не случайный чат) - ошибка.
const RESPONSE_SUCCESS_KEYS = new Set(['commands.fill.success', 'commands.setblock.success']);
const RESPONSE_NO_CHANGE_KEYS = new Set(['commands.fill.failed', 'commands.setblock.noChange']);

function classifyResponseKey(translateKey) {
  if (RESPONSE_SUCCESS_KEYS.has(translateKey)) return 'success';
  if (RESPONSE_NO_CHANGE_KEYS.has(translateKey)) return 'noChange';
  if (translateKey.startsWith('commands.')) return 'error';
  return null; // не похоже на ответ именно нашей команде - не трогаем FIFO
}

/**
 * Готовит площадку (опционально, --prepare) и выкладывает уже
 * загруженную и провалидированную схему - строит ПОЛНЫЙ упорядоченный
 * список команд (расчистка, основание, схема) и просто возвращает его,
 * ничего никуда не отправляя. Считается один раз до первой попытки
 * подключения (как и загрузка схемы, см. loadSchemaOrExit) - список не
 * меняется между переподключениями, что и позволяет при разрыве связи
 * просто продолжить рассылку с сохранённого индекса, а не пересчитывать
 * всё заново. origin - абсолютная точка, относительно которой отложены
 * координаты схемы (baseY для основания = origin.y).
 */
function buildSchemaCommandList(schema, { origin, prepare, foundationTo, foundationMaterial }) {
  const result = [];

  if (schema.length === 0) {
    log('[raw] Схема пуста - нечего строить.');
    return result;
  }

  if (prepare) {
    const bbox = computeBoundingBox(schema);

    const clearBox = buildClearBox(bbox, origin);
    const clearCommands = boxToCommands(clearBox);
    const dx = clearBox.x2 - clearBox.x1 + 1;
    const dy = clearBox.y2 - clearBox.y1 + 1;
    const dz = clearBox.z2 - clearBox.z1 + 1;
    log(`[raw] Расчистка площадки ${dx}x${dy}x${dz} (запас 1 по бокам, 3 сверху): ${clearCommands.length} команд`);
    result.push(...clearCommands);

    if (foundationTo !== null) {
      const foundationBox = buildFoundationBox(bbox, origin, foundationTo, foundationMaterial);
      if (foundationBox) {
        const foundationCommands = boxToCommands(foundationBox);
        log(`[raw] Основание ${foundationMaterial} до Y=${foundationTo}: ${foundationCommands.length} команд`);
        result.push(...foundationCommands);
      } else {
        log(`[raw] Основание не нужно: baseY-1 (${origin.y - 1}) уже не ниже --foundation-to (${foundationTo}).`);
      }
    }
  }

  const plan = buildFillCommands(schema, origin);
  const cmdWord = pluralizeRu(plan.solidCommandCount, 'команда', 'команды', 'команд');
  const attWord = pluralizeRu(plan.attachedCount, 'крепление', 'крепления', 'креплений');
  log(`[raw] ${schema.length} блоков -> ${plan.solidCommandCount} ${cmdWord} (одиночных ${plan.singleCommandCount}), плюс ${plan.attachedCount} ${attWord}`);
  result.push(...plan.commands);

  return result;
}

/**
 * Применяет --rotate к уже загруженной схеме ДО подготовки списка команд
 * (см. buildSchemaCommandList) - то есть до расчёта bounding box для
 * расчистки/основания и до жадного схлопывания в боксы, как и просили:
 * поворот должен работать с исходными локальными координатами схемы.
 * Логирует габарит до/после (см. rotateSchema в lib/fill-plan.js: она же
 * пересчитывает metadata лестниц/дверей/факелов/сундуков/печей) и
 * предупреждает, если в схеме есть таблички или рельсы - их ориентацию
 * поворот не пересчитывает (см. isDirectionalMetadataBlock).
 */
function applyRotation(schema, rotate) {
  if (rotate === 0 || schema.length === 0) return schema;

  const before = computeBoundingBox(schema);
  const beforeDims = `${before.maxX - before.minX + 1}x${before.maxZ - before.minZ + 1}`;

  const rotated = rotateSchema(schema, rotate);

  const after = computeBoundingBox(rotated);
  const afterDims = `${after.maxX - after.minX + 1}x${after.maxZ - after.minZ + 1}`;

  log(`[raw] Габарит схемы: ${beforeDims} -> ${afterDims} (поворот ${rotate})`);

  if (hasDirectionalMetadataBlocks(rotated)) {
    log('[raw] ВНИМАНИЕ: в схеме есть таблички и/или рельсы - их ориентацию поворот не пересчитывает, metadata останется как в файле.');
  }

  return rotated;
}

/**
 * Грузит и валидирует схему ДО подключения к серверу (fail-fast): раньше
 * ошибка (файл не найден, битый JSON) тихо ловилась уже после логина,
 * бот молчал и просто ничего не строил - со стороны
 * это выглядело как успешный запуск. Теперь при ошибке процесс сразу
 * завершается с кодом 1 и явным сообщением, где указан полный путь к
 * файлу, который пытались открыть.
 */
function loadSchemaOrExit(fileName) {
  const fullPath = path.resolve(config.schemasDir, path.basename(fileName));
  try {
    return loadSchema(config.schemasDir, fileName);
  } catch (err) {
    console.error(`[raw] ОШИБКА: не удалось загрузить схему.`);
    console.error(`[raw]   файл: ${fullPath}`);
    console.error(`[raw]   причина: ${err.message}`);
    process.exit(1);
  }
}

// Разбирают /fill и /setblock, которые сами же и генерируем (см.
// boxToCommand в lib/fill-plan.js) - формат фиксированный, свой же вывод
// разбираем регуляркой без риска: используется только для геометрии
// телепорта (зоны, габарит, высота), не для чего-то, что может прийти
// от сервера или пользователя.
const FILL_COMMAND_RE = /^\/fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) /;
const SETBLOCK_COMMAND_RE = /^\/setblock (-?\d+) (-?\d+) (-?\d+) /;

function parseCommandBounds(cmd) {
  const fillMatch = cmd.match(FILL_COMMAND_RE);
  if (fillMatch) {
    const x1 = Number(fillMatch[1]); const y1 = Number(fillMatch[2]); const z1 = Number(fillMatch[3]);
    const x2 = Number(fillMatch[4]); const y2 = Number(fillMatch[5]); const z2 = Number(fillMatch[6]);
    return {
      x1: Math.min(x1, x2), x2: Math.max(x1, x2),
      y2: Math.max(y1, y2),
      z1: Math.min(z1, z2), z2: Math.max(z1, z2),
      cx: Math.floor((x1 + x2) / 2), cz: Math.floor((z1 + z2) / 2)
    };
  }
  const setMatch = cmd.match(SETBLOCK_COMMAND_RE);
  if (setMatch) {
    const x = Number(setMatch[1]); const y = Number(setMatch[2]); const z = Number(setMatch[3]);
    return { x1: x, x2: x, y2: y, z1: z, z2: z, cx: x, cz: z };
  }
  return null; // не /fill и не /setblock (не должно случаться для наших команд)
}

/**
 * Считает общий габарит (X/Z) и максимальный Y всего списка команд, плюс
 * представительную точку (x,z) каждой команды (центр для /fill, сама
 * точка для /setblock) - на основе этого строятся зоны телепорта (см.
 * buildZonePlan). Работает для схемы, --wipe и --retry одинаково: не
 * важно, откуда взялись команды, важна только их геометрия.
 */
function computeCommandListBounds(commandList) {
  let minX = Infinity; let maxX = -Infinity;
  let minZ = Infinity; let maxZ = -Infinity;
  let maxY = -Infinity;
  const positions = new Array(commandList.length);

  for (let i = 0; i < commandList.length; i++) {
    const b = parseCommandBounds(commandList[i]);
    if (!b) {
      positions[i] = { x: 0, z: 0 };
      continue;
    }
    positions[i] = { x: b.cx, z: b.cz };
    if (b.x1 < minX) minX = b.x1;
    if (b.x2 > maxX) maxX = b.x2;
    if (b.z1 < minZ) minZ = b.z1;
    if (b.z2 > maxZ) maxZ = b.z2;
    if (b.y2 > maxY) maxY = b.y2;
  }

  return { minX, maxX, minZ, maxZ, maxY, positions };
}

/**
 * Делит commandList на зоны телепорта и, если зон больше одной,
 * ПЕРЕСТРАИВАЕТ список команд так, чтобы команды одной зоны шли подряд
 * (иначе индексы зон не были бы непрерывными диапазонами). Порядок
 * команд ВНУТРИ зоны сохраняется как в исходном списке - а значит и
 * инвариант "твёрдые раньше крепящихся, крепящиеся в порядке файла"
 * (см. §4.2/§4.4 BOT.md) не ломается: и твёрдая, и крепящаяся команда
 * для одной и той же постройки лежат рядом в пространстве и почти
 * наверняка попадут в одну зону, а стабильная группировка не меняет их
 * взаимный порядок.
 *
 * Возвращает { commandList, zones }, где zones - массив
 * { centerX, centerZ, y, startIndex, endIndex } (индексы уже по НОВОМУ,
 * возможно переставленному commandList). Если всё влезает в одну зону -
 * commandList возвращается как есть (не пересобирается), zones - из
 * одного элемента.
 */
function buildZonePlan(commandList) {
  if (commandList.length === 0) return { commandList, zones: [] };

  const { minX, maxX, minZ, maxZ, maxY, positions } = computeCommandListBounds(commandList);
  const teleportY = maxY + 10;
  const diameter = config.tpRenderRadiusBlocks * 2;
  const width = maxX - minX + 1;
  const depth = maxZ - minZ + 1;

  if (width <= diameter && depth <= diameter) {
    return {
      commandList,
      zones: [{
        centerX: Math.floor((minX + maxX) / 2),
        centerZ: Math.floor((minZ + maxZ) / 2),
        y: teleportY,
        startIndex: 0,
        endIndex: commandList.length - 1
      }]
    };
  }

  const buckets = new Map(); // zoneKey -> [индекс, индекс, ...] (по возрастанию - стабильно)
  const zoneOrder = [];
  positions.forEach((p, i) => {
    const zx = Math.floor((p.x - minX) / diameter);
    const zz = Math.floor((p.z - minZ) / diameter);
    const key = `${zx},${zz}`;
    if (!buckets.has(key)) {
      buckets.set(key, []);
      zoneOrder.push(key);
    }
    buckets.get(key).push(i);
  });

  const reordered = [];
  const zones = [];
  for (const key of zoneOrder) {
    const indices = buckets.get(key);
    const startIndex = reordered.length;
    let sumX = 0; let sumZ = 0;
    for (const idx of indices) {
      reordered.push(commandList[idx]);
      sumX += positions[idx].x;
      sumZ += positions[idx].z;
    }
    zones.push({
      centerX: Math.round(sumX / indices.length),
      centerZ: Math.round(sumZ / indices.length),
      y: teleportY,
      startIndex,
      endIndex: reordered.length - 1
    });
  }

  log(`[raw] Габарит ${width}x${depth} больше дальности прорисовки (${diameter}x${diameter}) - стройка разбита на ${zones.length} зон.`);

  return { commandList: reordered, zones };
}

/**
 * Ждёт (опросом каждые pollMs), пока predicate() не станет true, либо
 * пока не истечёт timeoutMs (если задан) - в обоих случаях просто
 * резолвится, без явного различения "дождались" / "не дождались":
 * вызывающий код сам решает, что делать дальше по факту (см. beginWork -
 * там после ожидания просто проверяется реальное состояние).
 */
function waitUntil(predicate, timeoutMs) {
  return new Promise((resolve) => {
    const deadline = timeoutMs ? Date.now() + timeoutMs : null;
    (function check() {
      if (predicate() || (deadline !== null && Date.now() >= deadline)) {
        resolve();
        return;
      }
      setTimeout(check, 200);
    })();
  });
}

/**
 * Отражает КАЖДУЮ запись в stdout/stderr (значит, и все log()/console.*
 * вызовы, откуда бы они ни шли) в файл - без этого пришлось бы находить
 * и дублировать каждый отдельный вызов log() по коду. Возвращает функцию
 * закрытия потока (не используется при обычном exit, но не мешает).
 */
function setupLogFileMirror(logFilePath) {
  fs.mkdirSync(path.dirname(logFilePath), { recursive: true });
  const stream = fs.createWriteStream(logFilePath, { flags: 'a' });

  const originalStdoutWrite = process.stdout.write.bind(process.stdout);
  const originalStderrWrite = process.stderr.write.bind(process.stderr);

  process.stdout.write = (chunk, ...rest) => {
    stream.write(chunk);
    return originalStdoutWrite(chunk, ...rest);
  };
  process.stderr.write = (chunk, ...rest) => {
    stream.write(chunk);
    return originalStderrWrite(chunk, ...rest);
  };

  return () => stream.end();
}

/**
 * Метка запуска для имён logs/<label>-<время>.log и logs/failed-<label>-<время>.txt -
 * из имени схемы, "wipe", или из имени файла --retry (без выдумывания
 * оригинальной схемы обратно - просто "retry-<имя файла>").
 */
function buildRunLabel({ schemaRequest, wipeRequest, retryRequest }) {
  if (schemaRequest) return path.basename(schemaRequest.fileName, '.json');
  if (wipeRequest) return 'wipe';
  if (retryRequest) return `retry-${path.basename(retryRequest.filePath).replace(/\.[^.]*$/, '')}`;
  return 'test';
}

function timestampForFileName() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

/**
 * Автопереподключение (см. константы MAX_CONNECT_ATTEMPTS/RECONNECT_DELAY_MS
 * в начале файла):
 *  - до MAX_CONNECT_ATTEMPTS попыток подряд добраться до 'login', пауза 3 сек между ними;
 *    счётчик attempt сбрасывается на каждом успешном login;
 *  - разрыв ДО login - тихо (без дампа ошибки) пробуем снова, в лог идёт
 *    только номер попытки;
 *  - разрыв ПОСЛЕ login: если commandList есть и ещё не всё отправлено
 *    (sentIndex не дошёл до конца) - переподключаемся и продолжаем рассылку
 *    с sentIndex+1, ничего не пересчитывая и не повторяя уже отправленное;
 *    если всё уже отправлено - это штатное завершение, реконнект не запускаем;
 *  - попытки исчерпаны - понятное сообщение в stderr и exit 1.
 * sentIndex переживает переподключения (объявлен снаружи connectAttempt).
 */
function start() {
  if (!config.host) {
    console.error('[raw] ОШИБКА: MC_HOST не задан. Скопируй .env.example в .env и укажи адрес сервера.');
    process.exit(1);
  }

  // --retry проверяется первым (несовместим со схемой/--wipe), затем
  // --wipe (позиционные координаты которого иначе могли бы случайно
  // распарситься как "имя_файла X Y Z" схемы).
  const retryRequest = parseCliRetryRequest(process.argv);
  const wipeRequest = retryRequest ? null : parseCliWipeRequest(process.argv);
  const schemaRequest = (retryRequest || wipeRequest) ? null : parseCliSchemaRequest(process.argv);
  const loadedSchema = schemaRequest ? loadSchemaOrExit(schemaRequest.fileName) : null;
  const schema = schemaRequest ? applyRotation(loadedSchema, schemaRequest.rotate) : null;

  const runLabel = buildRunLabel({ schemaRequest, wipeRequest, retryRequest });
  const runTimestamp = timestampForFileName();
  setupLogFileMirror(path.join('logs', `${runLabel}-${runTimestamp}.log`));

  const rawCommandList = retryRequest
    ? (log(`[raw] --retry: ${retryRequest.commands.length} команд из "${retryRequest.filePath}"`), retryRequest.commands)
    : (wipeRequest
      ? buildWipeCommandList(wipeRequest)
      : (schemaRequest ? buildSchemaCommandList(schema, schemaRequest) : null));

  // Телепорт-зоны нужны только там, где реально что-то строится - в
  // тестовом режиме (без схемы/--wipe/--retry) площадки нет вообще.
  const needsTeleport = rawCommandList !== null;
  const { commandList, zones } = needsTeleport
    ? buildZonePlan(rawCommandList)
    : { commandList: rawCommandList, zones: [] };

  const failedLogPath = path.join('logs', `failed-${runLabel}-${runTimestamp}.txt`);

  let attempt = 0;
  let sentIndex = -1; // индекс последней команды из commandList, реально отправленной client.write

  // Итоги ответов сервера - живут в этой (внешней) области видимости,
  // а не внутри connectAttempt, поэтому переживают переподключения и
  // сводка в конце получается по ВСЕМУ запуску, а не по последней попытке.
  let successCount = 0;
  let noChangeCount = 0;
  const errorReasonCounts = new Map();
  const failedCommandTexts = [];

  function recordResponse(kind, command, translateKey) {
    if (kind === 'success') { successCount++; return; }
    if (kind === 'noChange') { noChangeCount++; return; }
    failedCommandTexts.push(command);
    errorReasonCounts.set(translateKey, (errorReasonCounts.get(translateKey) || 0) + 1);
  }

  function writeFailedCommandsFileIfAny() {
    if (failedCommandTexts.length === 0) return;
    fs.mkdirSync(path.dirname(failedLogPath), { recursive: true });
    fs.writeFileSync(failedLogPath, failedCommandTexts.join('\n') + '\n');
    log(`[raw] Команды с ошибками (${failedCommandTexts.length}) сохранены в ${failedLogPath} - можно повторить: node index-cmd.js --retry ${failedLogPath}`);
  }

  function printRunSummary() {
    const total = successCount + noChangeCount + failedCommandTexts.length;
    log(`[raw] ИТОГ: ${total} ответов - успешно ${successCount}, без изменений ${noChangeCount}, ошибок ${failedCommandTexts.length}.`);
    if (errorReasonCounts.size > 0) {
      for (const [reason, count] of errorReasonCounts) {
        log(`[raw]   ошибка "${reason}": ${count}`);
      }
    }
    writeFailedCommandsFileIfAny();
  }

  function connectAttempt() {
    attempt++;
    if (attempt > MAX_CONNECT_ATTEMPTS) {
      console.error(`[raw] ОШИБКА: не удалось подключиться после ${MAX_CONNECT_ATTEMPTS} попыток. Останавливаюсь.`);
      process.exit(1);
      return;
    }

    const connectStartedAt = Date.now();
    const client = createRawClient(config);
    let loggedIn = false;
    let disconnectHandled = false;

    function secondsSinceConnect() {
      return ((Date.now() - connectStartedAt) / 1000).toFixed(1);
    }

    // Сторожевой таймер (см. WATCHDOG_TIMEOUT_MS): 'packet' у node-minecraft-protocol
    // стреляет на КАЖДЫЙ входящий пакет любого типа (см. src/client.js -
    // this.emit('packet', ...)), поэтому это самый общий признак "сервер
    // ещё жив" - не завязываемся на конкретный keep_alive/update_time.
    let lastPacketAt = Date.now();
    const watchdogTimer = setInterval(() => {
      if (Date.now() - lastPacketAt >= WATCHDOG_TIMEOUT_MS) {
        log(`[raw] Сторожевой таймер: от сервера нет пакетов ${WATCHDOG_TIMEOUT_MS / 1000} сек - рву соединение.`);
        client.end('watchdog: нет пакетов от сервера');
      }
    }, 1000);
    client.on('packet', () => { lastPacketAt = Date.now(); });

    // FIFO отправленных, но ещё не подтверждённых чатом команд - только
    // для ЭТОГО соединения (после переподключения судьба команд,
    // "зависших" в полёте на старом соединении, неизвестна - см. §11
    // «Опыт» в BOT.md, там же - почему сопоставление именно такое).
    const pendingResponses = [];

    const commands = createCommandQueue(client, config.commandsPerSecond, (message) => {
      pendingResponses.push(message);
      if (commandList === null) return;
      sentIndex++;
      if (sentIndex === commandList.length - 1) {
        log('[raw] Все команды отправлены - жду ответов сервера...');
        waitUntil(() => pendingResponses.length === 0, FINAL_DRAIN_TIMEOUT_MS).then(() => {
          if (pendingResponses.length > 0) {
            // Сервер вообще не ответил (не путать с commands.*.failed/noChange -
            // это ЯВНЫЙ ответ "ничего не изменилось", а тут ответа нет совсем -
            // ровно симптом гипотезы про незагруженные чанки, см. §11 «Опыт»).
            // Раз не знаем, выполнилась ли команда, безопаснее считать её
            // ошибкой и положить в файл повтора, чем молча забыть.
            log(`[raw] Не дождался ответа на ${pendingResponses.length} команд(ы) за ${FINAL_DRAIN_TIMEOUT_MS / 1000} сек - считаю ошибкой.`);
            while (pendingResponses.length > 0) {
              recordResponse('error', pendingResponses.shift(), 'нет ответа от сервера');
            }
          }
          printRunSummary();
          client.end();
        });
      }
    });

    function handleDisconnect(detail) {
      if (disconnectHandled) return;
      disconnectHandled = true;
      clearInterval(watchdogTimer);
      commands.stop();

      if (!loggedIn) {
        // "молча" - без дампа ошибки, только номер попытки
        log(`[raw] Не удалось подключиться (попытка ${attempt}/${MAX_CONNECT_ATTEMPTS}): ${detail}`);
        setTimeout(connectAttempt, RECONNECT_DELAY_MS);
        return;
      }

      log(`[raw] Разрыв соединения на ${secondsSinceConnect()} сек после подключения: ${detail}`);

      if (commandList !== null && sentIndex >= commandList.length - 1) {
        log('[raw] Схема уже полностью отправлена - штатное завершение, без переподключения.');
        process.exit(0);
        return;
      }

      if (commandList !== null) {
        log(`[raw] Работа не закончена (отправлено ${sentIndex + 1}/${commandList.length}) - переподключаюсь.`);
      }

      setTimeout(connectAttempt, RECONNECT_DELAY_MS);
    }

    // Любая ошибка сериализации/десериализации пакета (protodef) всплывает
    // сюда как обычное событие 'error' (см. node_modules/minecraft-protocol/
    // src/client.js: this.deserializer.on('error', ...) -> this.emit('error', e))
    // - логируем и НЕ даём процессу упасть (никаких throw/rethrow).
    client.on('error', (err) => {
      if (loggedIn) console.log('ERROR:', err);
      handleDisconnect(err && err.message ? err.message : String(err));
    });

    client.on('kicked', (reason) => {
      if (loggedIn) console.log('KICKED:', JSON.stringify(reason));
      handleDisconnect(`kicked: ${JSON.stringify(reason)}`);
    });

    client.on('end', (reason) => {
      if (loggedIn) console.log('END:', reason);
      handleDisconnect(`end: ${reason || ''}`);
    });

    // Ответы на /fill и /setblock приходят сюда же, как обычный чат (см.
    // extractTranslateKey/classifyResponseKey выше и §11 «Опыт» в BOT.md -
    // там подробно расписано, как именно сопоставление сделано и какие у
    // него границы применимости).
    client.on('chat', (packet) => {
      const translateKey = extractTranslateKey(packet.message);
      const kind = translateKey ? classifyResponseKey(translateKey) : null;

      if (kind && pendingResponses.length > 0) {
        const command = pendingResponses.shift();
        recordResponse(kind, command, translateKey);
      }

      const text = simplifyChatComponent(packet.message);
      if (text.trim()) log(`[chat] ${text}`);
    });

    // Живёт весь сеанс (не только сразу после login): если бот умрёт
    // посреди работы (упал, попал под моб/лаву), сервер держит его на
    // экране смерти, пока не придёт client_command actionId=0 (respawn) -
    // без этого он там висит навсегда.
    client.on('update_health', (packet) => {
      if (packet.health <= 0) {
        client.write('client_command', { actionId: 0 });
        log('[raw] бот мёртв, возрождаюсь');
      }
    });

    /**
     * Переключает бота в режим наблюдателя (spectator, id 3) - полёт без
     * коллизий, не упадёт и не задохнётся при телепорте в толщу камня.
     * Требует OP; если сервер не подтвердил смену режима (пакет
     * game_state_change, reason=3) за GAMEMODE_CONFIRM_TIMEOUT_MS -
     * понятная ошибка вместо тихого зависания.
     */
    function ensureSpectatorMode() {
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          client.removeListener('game_state_change', onChange);
          reject(new Error(`Не удалось переключиться в режим наблюдателя (/gamemode 3) за ${GAMEMODE_CONFIRM_TIMEOUT_MS} мс - похоже, у бота нет прав OP.`));
        }, GAMEMODE_CONFIRM_TIMEOUT_MS);

        function onChange(packet) {
          if (packet.reason !== 3 || Math.round(packet.gameMode) !== 3) return;
          clearTimeout(timer);
          client.removeListener('game_state_change', onChange);
          resolve();
        }

        client.on('game_state_change', onChange);
        const message = '/gamemode 3';
        client.write('chat', { message });
        log(`[raw] -> ${message}`);
      });
    }

    /**
     * Телепортирует бота в (x,y,z) через /tp и ждёт подтверждения от
     * сервера - пакета 'position' (см. §4.5/§10.1.2 - это тот же пакет,
     * что и в проверке готовности после login). По протоколу 1.12.2
     * сервер ждёт в ответ 'teleport_confirm' с тем же teleportId - без
     * него телепорт формально не завершён; raw-клиент (в отличие от
     * mineflayer) это не делает сам, поэтому отправляем явно. Требует
     * OP; без подтверждения за TELEPORT_CONFIRM_TIMEOUT_MS - понятная
     * ошибка.
     */
    function teleportTo(x, y, z) {
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          client.removeListener('position', onPosition);
          reject(new Error(`Не удалось телепортироваться в (${x}, ${y}, ${z}) за ${TELEPORT_CONFIRM_TIMEOUT_MS} мс - похоже, у бота нет прав OP на /tp.`));
        }, TELEPORT_CONFIRM_TIMEOUT_MS);

        function onPosition(packet) {
          clearTimeout(timer);
          client.removeListener('position', onPosition);
          client.write('teleport_confirm', { teleportId: packet.teleportId });
          resolve();
        }

        client.on('position', onPosition);
        const message = `/tp ${config.username} ${x} ${y} ${z}`;
        client.write('chat', { message });
        log(`[raw] -> ${message}`);
      });
    }

    /**
     * То, ради чего всё затевалось: телепортирует бота на площадку зона
     * за зоной (см. buildZonePlan) и заполняет очередь командами (или
     * планирует тестовый /setblock, если commandList === null). Раньше
     * это делалось прямо в обработчике 'login', теперь только после
     * того, как waitUntilReadyThenBeginWork подтвердит, что игрок
     * реально заспавнен (а не висит на экране смерти).
     */
    async function beginWork() {
      if (commandList !== null) {
        if (sentIndex >= commandList.length - 1) {
          log('[raw] Схема уже полностью отправлена - завершаю работу.');
          process.exit(0);
          return;
        }

        try {
          await ensureSpectatorMode();
        } catch (err) {
          // Если соединение уже разорвано (а не просто "нет OP") - это не
          // фатальная ошибка, а обычный разрыв: handleDisconnect уже
          // поставил переподключение в очередь, здесь просто выходим,
          // не трогая мёртвый client и не завершая процесс.
          if (disconnectHandled) return;
          console.error(`[raw] ОШИБКА: ${err.message}`);
          process.exit(1);
          return;
        }
        if (disconnectHandled) return;

        // "Связь восстановлена" имеет смысл сказать один раз за весь
        // beginWork (т.е. один раз на успешный login) - если написать это
        // внутри цикла по зонам, сообщение будет всплывать на КАЖДОМ
        // переходе к следующей зоне, даже без единого разрыва соединения.
        if (sentIndex >= 0) {
          log(`[raw] Связь восстановлена, продолжаю с команды ${sentIndex + 2} из ${commandList.length}.`);
        }

        for (const zone of zones) {
          if (disconnectHandled) return;
          if (sentIndex >= zone.endIndex) continue; // зона уже вся отправлена (после переподключения)

          try {
            await teleportTo(zone.centerX, zone.y, zone.centerZ);
          } catch (err) {
            if (disconnectHandled) return; // см. комментарий выше про ensureSpectatorMode
            console.error(`[raw] ОШИБКА: ${err.message}`);
            process.exit(1);
            return;
          }
          if (disconnectHandled) return;
          await sleep(config.tpChunkLoadWaitMs);
          if (disconnectHandled) return;

          const resumeFrom = Math.max(zone.startIndex, sentIndex + 1);
          for (let i = resumeFrom; i <= zone.endIndex; i++) commands.enqueue(commandList[i]);

          await waitUntil(() => disconnectHandled || sentIndex >= zone.endIndex, null);
        }
        return;
      }

      log('[raw] Держим соединение 60 сек, затем отправим тестовый /setblock...');
      setTimeout(() => {
        log(`[raw] 60 сек продержались (${secondsSinceConnect()} сек с начала подключения). Отправляю тестовую команду.`);
        commands.enqueue('/setblock 61 72 242 minecraft:stone');
      }, 60000);
    }

    /**
     * login сам по себе ничего не говорит о том, жив ли игрок - если бот
     * умер в прошлом запуске и отключился мёртвым, после повторного login
     * сервер держит его на экране смерти, 'position' не приходит вовсе, а
     * 'update_health' приходит с health<=0. Поэтому ждём первое из двух:
     * 'position' (игрок реально заспавнен) или update_health с health>0
     * (тоже означает "жив"). Если же первый update_health <= 0 - это
     * смерть: respawn уже отправлен постоянным слушателем выше, а здесь
     * просто продолжаем ждать (не считаем это сигналом готовности) -
     * настоящий 'position' придёт следом за респавном. Когда сигнал
     * получен - ещё пауза READY_PAUSE_MS и только затем beginWork().
     */
    function waitUntilReadyThenBeginWork() {
      let ready = false;

      function onReady() {
        if (ready) return;
        ready = true;
        client.removeListener('position', onPosition);
        client.removeListener('update_health', onHealth);
        setTimeout(beginWork, READY_PAUSE_MS);
      }

      function onPosition() {
        onReady();
      }

      function onHealth(packet) {
        if (packet.health > 0) onReady();
        // health <= 0 - постоянный слушатель выше уже отправил respawn,
        // здесь просто ждём дальше настоящего 'position'.
      }

      client.on('position', onPosition);
      client.on('update_health', onHealth);
    }

    // 'login' (join_game) - самая ранняя точка, где версия уже точно
    // определена autoVersionForge и forge-рукопожатие прошло (см. предыдущую
    // диагностику в основном боте: на 'connect' версия ещё undefined).
    client.once('login', () => {
      loggedIn = true;
      attempt = 0; // успех - счётчик попыток сбрасывается
      log(`[raw] Вход выполнен. version=${client.version} protocolVersion=${client.rawOptions.protocolVersion}`);
      waitUntilReadyThenBeginWork();
    });
  }

  connectAttempt();
}

start();
