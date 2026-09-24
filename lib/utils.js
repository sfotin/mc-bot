'use strict';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function log(...args) {
  console.log(new Date().toISOString(), '-', ...args);
}

module.exports = { sleep, log };
