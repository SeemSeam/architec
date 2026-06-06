#!/usr/bin/env node
"use strict";

const { ensureLlmGatewayConfig } = require("../lib/archi-dispatcher");

try {
  const result = ensureLlmGatewayConfig({ quiet: true });
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
