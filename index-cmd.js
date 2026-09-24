'use strict';

process.on('uncaughtException', (e) => console.error('UNCAUGHT:', e));
process.on('unhandledRejection', (e) => console.error('REJECTION:', e));

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
const { log } = require('./lib/utils');

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

/**
 * CLI: node index-cmd.js [схема.json X Y Z] [--prepare] [--foundation-to=Y] [--foundation-material=stone] [--rotate=0|90|180|270]
 *      node index-cmd.js --wipe X1 Y1 Z1 X2 Y2 Z2 [--ground=Y]
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

  // --wipe проверяется первым и, если указан, отключает разбор схемы:
  // позиционные координаты --wipe (шесть чисел) иначе могли бы случайно
  // распарситься как "имя_файла X Y Z" схемы.
  const wipeRequest = parseCliWipeRequest(process.argv);
  const schemaRequest = wipeRequest ? null : parseCliSchemaRequest(process.argv);
  const loadedSchema = schemaRequest ? loadSchemaOrExit(schemaRequest.fileName) : null;
  const schema = schemaRequest ? applyRotation(loadedSchema, schemaRequest.rotate) : null;
  const commandList = wipeRequest
    ? buildWipeCommandList(wipeRequest)
    : (schemaRequest ? buildSchemaCommandList(schema, schemaRequest) : null);

  let attempt = 0;
  let sentIndex = -1; // индекс последней команды из commandList, реально отправленной client.write

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

    const commands = createCommandQueue(client, config.commandsPerSecond, () => {
      if (commandList === null) return;
      sentIndex++;
      if (sentIndex === commandList.length - 1) {
        // Всё отправлено - сервер сам не закроет соединение, поэтому не
        // висим бесконечно: даём секунду на последние подтверждения в
        // чат (commands.fill.success и т.п.) и завершаем сами. handleDisconnect
        // увидит sentIndex на конце списка и корректно завершится exit(0)
        // без попытки переподключения (штатное завершение).
        log('[raw] Все команды схемы отправлены - жду подтверждений и завершаю соединение.');
        setTimeout(() => client.end(), 1000);
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

    client.on('chat', (packet) => {
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
     * То, ради чего всё затевалось: заполняет очередь командами (или
     * планирует тестовый /setblock, если commandList === null) - раньше
     * это делалось прямо в обработчике 'login', теперь только после того,
     * как waitUntilReadyThenBeginWork ниже подтвердит, что игрок реально
     * заспавнен (а не висит на экране смерти).
     */
    function beginWork() {
      if (commandList !== null) {
        const remaining = commandList.slice(sentIndex + 1);
        if (remaining.length === 0) {
          log('[raw] Схема уже полностью отправлена - завершаю работу.');
          process.exit(0);
          return;
        }
        if (sentIndex >= 0) {
          log(`[raw] Связь восстановлена, продолжаю с команды ${sentIndex + 2} из ${commandList.length}.`);
        }
        remaining.forEach((cmd) => commands.enqueue(cmd));
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
