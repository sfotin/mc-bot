'use strict';
// send_order.js - порядок отправки команд ботом для схемы (tools/decor/).
// Вызывает buildFillCommands из lib/fill-plan.js (логика движка не дублируется),
// разбирает координаты каждой команды и печатает JSON:
//   {"order": {"x,y,z": номер_команды, ...}, "commandCount": N,
//    "fallingSupportWarnings": [...]}
// Запуск: node tools/decor/send_order.js path/to/schema.json
// .env не нужен (config.js без MC_HOST не падает), нужен node_modules репозитория.
const fs = require('fs');
const path = require('path');
const fp = require(path.join(__dirname, '..', '..', 'lib', 'fill-plan.js'));

const file = process.argv[2];
if (!file) {
  console.error('использование: node tools/decor/send_order.js schema.json');
  process.exit(2);
}
const schema = JSON.parse(fs.readFileSync(file, 'utf-8'));
const res = fp.buildFillCommands(schema, { x: 0, y: 0, z: 0 });
const order = {};
res.commands.forEach((cmd, i) => {
  const p = cmd.trim().split(/\s+/);
  let x1, y1, z1, x2, y2, z2;
  if (p[0] === '/fill') {
    [x1, y1, z1, x2, y2, z2] = p.slice(1, 7).map(Number);
  } else if (p[0] === '/setblock') {
    [x1, y1, z1] = p.slice(1, 4).map(Number);
    [x2, y2, z2] = [x1, y1, z1];
  } else {
    return;
  }
  for (let x = Math.min(x1, x2); x <= Math.max(x1, x2); x++)
    for (let y = Math.min(y1, y2); y <= Math.max(y1, y2); y++)
      for (let z = Math.min(z1, z2); z <= Math.max(z1, z2); z++)
        order[`${x},${y},${z}`] = i;
});
process.stdout.write(JSON.stringify({
  order,
  commandCount: res.commands.length,
  fallingSupportWarnings: res.fallingSupportWarnings || [],
}));
