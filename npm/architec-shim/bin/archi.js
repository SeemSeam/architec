#!/usr/bin/env node
"use strict";

const { main } = require("@seemseam/archi/lib/archi-dispatcher");

main(process.argv.slice(2))
  .then((status) => {
    process.exit(status === undefined || status === null ? 0 : status);
  })
  .catch((error) => {
    console.error(`archi npm shim: ${error.message}`);
    process.exit(1);
  });
