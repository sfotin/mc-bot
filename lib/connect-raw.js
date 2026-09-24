'use strict';

const mc = require('minecraft-protocol');
const { autoVersionForge } = require('minecraft-protocol-forge');
const { log } = require('./utils');

/**
 * Создаёт "сырой" клиент minecraft-protocol (без mineflayer: без модели
 * мира, инвентаря, физики) для модового Forge-сервера.
 *
 * Логика подключения та же, что в lib/connect.js: version всегда false,
 * чтобы node-minecraft-protocol сходил в сервер за server list ping'ом,
 * а autoVersionForge подставила forge-рукопожатие (канал FML|HS) с точным
 * списком модов сервера, когда обнаружит по ping-ответу, что это Forge/FML.
 *
 * config.port необязателен - см. комментарий в lib/connect.js/config.js:
 * если не задан, ключ port не попадает в опции, и node-minecraft-protocol
 * сам делает SRV-запрос _minecraft._tcp.<host>.
 */
function createRawClient(config) {
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

  const client = mc.createClient(options);

  // Держим ссылку на options, чтобы снаружи можно было прочитать
  // options.protocolVersion после того, как autoVersion его определит
  // (сам client такого поля не хранит - см. разбор в предыдущей итерации).
  client.rawOptions = options;

  autoVersionForge(client);

  if (hasExplicitPort) {
    log(`[raw] Подключение к ${config.host}:${config.port} как ${config.username} (явный порт, ожидаемая версия: ${config.version})...`);
  } else {
    log(`[raw] Порт не задан - подключение к ${config.host} как ${config.username} через SRV-запись _minecraft._tcp.${config.host} (ожидаемая версия: ${config.version})...`);
  }

  return client;
}

module.exports = { createRawClient };
