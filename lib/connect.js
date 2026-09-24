'use strict';

const mineflayer = require('mineflayer');
const { pathfinder } = require('mineflayer-pathfinder');
const { autoVersionForge } = require('minecraft-protocol-forge');
const { log } = require('./utils');

/**
 * Создаёт mineflayer-бота, подключённого к модовому Forge-серверу.
 *
 * Рукопожатие с Forge (канал FML|HS) требует, чтобы node-minecraft-protocol
 * сначала сходил в сервер за server list ping'ом и получил список модов
 * (modinfo) — это происходит только при автоопределении версии
 * (version: false). Поэтому здесь версия соединения всегда false, а
 * autoVersionForge сама подставит нужный список модов и версию протокола,
 * когда обнаружит, что сервер — Forge/FML. Значение config.version
 * используется только для логов.
 *
 * config.port необязателен. Если он не задан (null/undefined/''), ключ
 * port вообще не попадает в опции createBot — тогда node-minecraft-protocol
 * (см. tcp_dns.js) сам делает SRV-запрос _minecraft._tcp.<host> и берёт
 * хост/порт из ответа, если host не IP и не localhost.
 */
function createBot(config) {
  if (!config.host) {
    throw new Error('MC_HOST не задан. Скопируй .env.example в .env и укажи адрес сервера.');
  }

  const hasExplicitPort = config.port !== null && config.port !== undefined && config.port !== '';

  const options = {
    host: config.host,
    username: config.username,
    auth: 'offline',
    version: false
  };
  if (hasExplicitPort) {
    options.port = config.port;
  }

  const bot = mineflayer.createBot(options);

  // Подключаем поддержку Forge-рукопожатия к внутреннему protocol-клиенту бота
  autoVersionForge(bot._client);

  bot.loadPlugin(pathfinder);

  if (hasExplicitPort) {
    log(`Подключение к ${config.host}:${config.port} как ${config.username} (явный порт, ожидаемая версия: ${config.version})...`);
  } else {
    log(`Порт не задан - подключение к ${config.host} как ${config.username} через SRV-запись _minecraft._tcp.${config.host} (ожидаемая версия: ${config.version})...`);
  }

  return bot;
}

module.exports = { createBot };
