'use strict';

process.on('uncaughtException', (e) => console.error('UNCAUGHT:', e));
process.on('unhandledRejection', (e) => console.error('REJECTION:', e));

// Патчит prismarine-item раньше, чем его подхватит require('mineflayer') -
// должен требоваться первым, до всех остальных модулей проекта.
require('./lib/patch-items');

const config = require('./config');
const { createBot } = require('./lib/connect');
const { registerCommands } = require('./lib/commands');
const { log, sleep } = require('./lib/utils');

let reconnecting = false;

function start() {
  if (!config.host) {
    console.error('ОШИБКА: MC_HOST не задан. Скопируй .env.example в .env и укажи адрес сервера.');
    process.exit(1);
  }

  const connectStartedAt = Date.now();
  const bot = createBot(config);

  function secondsSinceConnect() {
    return ((Date.now() - connectStartedAt) / 1000).toFixed(1);
  }

  // 'connect' (сырой TCP-коннект) срабатывает раньше, чем ping-логика
  // autoVersionForge успевает выставить версию - на этот момент bot.version
  // ещё undefined. 'login' (после join_game) - самая ранняя точка, где версия
  // гарантированно уже определена и forge-рукопожатие уже прошло.
  bot.once('login', () => {
    log(`Вход выполнен. bot.version=${bot.version} bot.protocolVersion=${bot.protocolVersion} bot._client.version=${bot._client.version} bot._client.protocolVersion=${bot._client.protocolVersion}`);
  });

  bot.once('spawn', () => {
    log('Бот заспавнился на сервере.');
    bot.chat('Привет! Я зашёл на сервер и готов к работе.');
  });

  registerCommands(bot, config);

  bot.on('kicked', (reason) => {
    console.log('KICKED:', JSON.stringify(reason));
    log(`Разрыв (kicked) на ${secondsSinceConnect()} сек после начала подключения.`);
  });

  bot.on('error', (err) => {
    console.log('ERROR:', err);
    log(`Разрыв (error) на ${secondsSinceConnect()} сек после начала подключения.`);
  });

  bot.on('end', (reason) => {
    console.log('END:', reason);
    log(`Разрыв (end) на ${secondsSinceConnect()} сек после начала подключения.`);
    scheduleReconnect();
  });
}

function scheduleReconnect() {
  if (reconnecting) return;
  reconnecting = true;
  log(`Переподключение через ${config.reconnectDelayMs} мс...`);
  sleep(config.reconnectDelayMs).then(() => {
    reconnecting = false;
    start();
  });
}

start();
