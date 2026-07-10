import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { loadConfig } from "./config.js";
import { createServer } from "./server.js";

const config = loadConfig();
const pythonBin = existsSync(config.pythonBin) ? config.pythonBin : "python3";
const fitRuntime = spawn(pythonBin, ["src/features/resumes/ml/server.py"], {
  env: {
    ...process.env,
    FIT_RUNTIME_PORT: String(config.fitRuntimePort),
  },
  stdio: ["ignore", "inherit", "inherit"],
});

fitRuntime.on("exit", (code, signal) => {
  if (signal) {
    console.error(`Resume fit runtime exited with signal ${signal}.`);
  } else {
    console.error(`Resume fit runtime exited with code ${code}.`);
  }
});

const server = createServer({ config });
server.listen(config.port, () => {
  console.log(`Merida local operator backend listening on http://127.0.0.1:${config.port}`);
  console.log(`Job Posting Analysis UI available at http://127.0.0.1:${config.port}/analysis`);
  console.log(`Resume Creation UI available at http://127.0.0.1:${config.port}/resumes`);
});

function shutdown() {
  fitRuntime.kill("SIGTERM");
  server.close(() => {
    process.exit(0);
  });
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
