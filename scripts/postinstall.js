#!/usr/bin/env node
"use strict";

const { ensureLlmGatewayConfig } = require("../lib/archi-dispatcher");

try {
  const result = ensureLlmGatewayConfig({ quiet: true });
  console.error("archi npm postinstall: project: https://github.com/SeemSeam/architec");
  console.error("archi npm postinstall: more info: https://github.com/SeemSeam/architec#readme");
  if (result.created) {
    console.error(
      `archi npm postinstall: created starter llmgateway config at ${result.path}`,
    );
  }
} catch (error) {
  console.error(
    `archi npm postinstall: warning: could not create starter llmgateway config: ${error.message}`,
  );
}
