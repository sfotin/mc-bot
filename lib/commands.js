'use strict';

const fs = require('fs');
const path = require('path');
const { Vec3 } = require('vec3');
const { goals } = require('mineflayer-pathfinder');
const { placeBlockAt, buildSchema } = require('./build');
const { log } = require('./utils');

function parseCoords(args) {
  if (args.length < 3) return null;
  const [x, y, z] = args.slice(0, 3).map(Number);
  if ([x, y, z].some((n) => Number.isNaN(n))) return null;
  return new Vec3(Math.floor(x), Math.floor(y), Math.floor(z));
}

function loadSchema(schemasDir, fileName) {
  // Разрешаем только имя файла, без выхода за пределы папки со схемами
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

function registerCommands(bot, config) {
  const state = { busy: false };

  function help() {
    bot.chat(`Команды: ${config.commandPrefix}goto x y z | ${config.commandPrefix}place x y z blockName | ${config.commandPrefix}build файл.json x y z | ${config.commandPrefix}stop`);
  }

  bot.on('chat', async (username, message) => {
    if (username === bot.username) return;
    if (!message.startsWith(config.commandPrefix)) return;

    const parts = message.slice(config.commandPrefix.length).trim().split(/\s+/);
    const cmd = parts.shift().toLowerCase();

    try {
      if (cmd === 'help') {
        help();
        return;
      }

      if (cmd === 'stop') {
        bot.pathfinder.setGoal(null);
        state.busy = false;
        bot.chat('Остановился.');
        return;
      }

      if (state.busy) {
        bot.chat('Занят выполнением предыдущей команды, подождите или напишите !stop');
        return;
      }

      if (cmd === 'goto') {
        const pos = parseCoords(parts);
        if (!pos) {
          bot.chat(`Использование: ${config.commandPrefix}goto X Y Z`);
          return;
        }
        state.busy = true;
        bot.chat(`Иду к (${pos.x}, ${pos.y}, ${pos.z})...`);
        log(`Команда goto от ${username}: ${pos}`);
        try {
          await bot.pathfinder.goto(new goals.GoalNear(pos.x, pos.y, pos.z, config.gotoRangeBlocks));
          bot.chat(`Пришёл в (${pos.x}, ${pos.y}, ${pos.z}).`);
        } catch (err) {
          bot.chat(`Не смог дойти: ${err.message}`);
        } finally {
          state.busy = false;
        }
        return;
      }

      if (cmd === 'place') {
        if (parts.length < 4) {
          bot.chat(`Использование: ${config.commandPrefix}place X Y Z blockName`);
          return;
        }
        const pos = parseCoords(parts);
        const blockName = parts[3];
        if (!pos || !blockName) {
          bot.chat(`Использование: ${config.commandPrefix}place X Y Z blockName`);
          return;
        }
        state.busy = true;
        log(`Команда place от ${username}: ${blockName} в ${pos}`);
        try {
          const result = await placeBlockAt(bot, pos, blockName, { range: config.gotoRangeBlocks + 3 });
          if (result.ok) {
            bot.chat(`Поставил ${blockName} в (${pos.x}, ${pos.y}, ${pos.z}).`);
          } else {
            bot.chat(`Не удалось поставить блок: ${result.reason}`);
          }
        } finally {
          state.busy = false;
        }
        return;
      }

      if (cmd === 'build') {
        if (parts.length < 4) {
          bot.chat(`Использование: ${config.commandPrefix}build файл.json X Y Z`);
          return;
        }
        const fileName = parts[0];
        const origin = parseCoords(parts.slice(1));
        if (!origin) {
          bot.chat(`Использование: ${config.commandPrefix}build файл.json X Y Z`);
          return;
        }

        let schema;
        try {
          schema = loadSchema(config.schemasDir, fileName);
        } catch (err) {
          bot.chat(`Не удалось загрузить схему: ${err.message}`);
          return;
        }

        state.busy = true;
        log(`Команда build от ${username}: файл=${fileName}, origin=${origin}, блоков=${schema.length}`);
        try {
          await buildSchema(bot, schema, origin, config);
        } catch (err) {
          bot.chat(`Ошибка постройки: ${err.message}`);
        } finally {
          state.busy = false;
        }
        return;
      }

      bot.chat(`Неизвестная команда. ${config.commandPrefix}help - список команд.`);
    } catch (err) {
      state.busy = false;
      log('Ошибка обработки команды:', err);
      bot.chat(`Внутренняя ошибка: ${err.message}`);
    }
  });
}

module.exports = { registerCommands, loadSchema, parseCoords };
