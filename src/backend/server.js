import http from "node:http";
import { loadConfig, validateConfig } from "./config.js";
import { failed, OPERATOR_FAILURE_REASONS } from "./contracts.js";
import { createRouteAdapters } from "./adapters.js";

const TOKEN_POLICIES = {
  NONE: "none",
  REQUIRED: "required",
  SAME_ORIGIN: "same-origin",
};

export function createServer({
  config = loadConfig(),
  adapters = createRouteAdapters({ config }),
} = {}) {
  const jobPostingsAdapter = adapters.jobPostings;
  const resumesAdapter = adapters.resumes;
  const routes = [
    ...jobPostingsAdapter.routes,
    ...resumesAdapter.routes,
  ];

  return http.createServer(async (request, response) => {
    try {
      await routeRequest(request, response, {
        config,
        routes,
        jobPostingsAdapter,
      });
    } catch (error) {
      console.error(error);
      if (response.headersSent) {
        if (!response.writableEnded) {
          response.end();
        }
        return;
      }
      sendJson(request, response, config, error.status || 500, failed(
        OPERATOR_FAILURE_REASONS.INVALID_REQUEST,
        error.message || "Unexpected server error.",
      ));
    }
  });
}

async function routeRequest(request, response, {
  config,
  routes,
  jobPostingsAdapter,
}) {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);

  if (request.method === "OPTIONS") {
    handleOptions(request, response, config);
    return;
  }

  if (!isAllowedOrigin(request, config)) {
    sendJson(request, response, config, 403, failed(
      OPERATOR_FAILURE_REASONS.INVALID_TOKEN,
      "Request origin is not allowed.",
    ));
    return;
  }

  const route = findRoute(routes, request.method, url.pathname);
  const tokenPolicy = route?.token || TOKEN_POLICIES.REQUIRED;
  if (requiresToken(request, tokenPolicy) && !hasValidToken(request, config)) {
    sendJson(request, response, config, 401, failed(
      OPERATOR_FAILURE_REASONS.INVALID_TOKEN,
      "Capture token is missing or invalid.",
    ));
    return;
  }

  if (request.method === "GET" && url.pathname === "/health") {
    await handleHealth(request, response, {
      config,
      jobPostingsAdapter,
      validateSchema: url.searchParams.get("validate") === "1",
    });
    return;
  }

  if (!route) {
    sendJson(request, response, config, 404, failed(
      OPERATOR_FAILURE_REASONS.INVALID_REQUEST,
      "Endpoint not found.",
    ));
    return;
  }

  await route.handle(routeContext({
    request,
    response,
    url,
    config,
  }));
}

function findRoute(routes, method, path) {
  return routes.find((route) => route.method === method && route.path === path);
}

function routeContext({
  request,
  response,
  url,
  config,
}) {
  return {
    url,
    readJson: () => readJson(request),
    sendHtml: (html) => sendHtml(response, html),
    sendJson: (status, payload) => sendJson(request, response, config, status, payload),
    streamNdjson: (writeEvents) => streamNdjson(request, response, config, writeEvents),
  };
}

async function handleHealth(request, response, {
  config,
  jobPostingsAdapter,
  validateSchema,
}) {
  const configResult = validateConfig(config);
  const payload = {
    ok: configResult.valid,
    config: {
      notionToken: Boolean(config.notionToken),
      notionDatabaseId: Boolean(config.notionDatabaseId),
      notionResumeDatabaseId: Boolean(config.notionResumeDatabaseId),
      notionNotesDatabaseId: Boolean(config.notionNotesDatabaseId),
      captureToken: Boolean(config.captureToken),
      extensionOrigin: Boolean(config.extensionOrigin),
      port: config.port,
      analysisConfigured: Boolean(config.deepseekApiKey),
      deepseekModel: config.deepseekModel,
      fitRuntimeUrl: config.fitRuntimeUrl,
      fitRuntimePort: config.fitRuntimePort,
    },
    errors: configResult.errors,
  };

  if (configResult.valid && validateSchema) {
    const schema = await jobPostingsAdapter.validateNotionSchema();
    payload.ok = payload.ok && schema.valid;
    payload.notionSchema = schema;
  }

  sendJson(request, response, config, 200, payload);
}

function handleOptions(request, response, config) {
  if (!isAllowedOrigin(request, config)) {
    response.writeHead(403);
    response.end();
    return;
  }

  response.writeHead(204, corsHeaders(request, config));
  response.end();
}

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) {
    chunks.push(chunk);
  }

  const text = Buffer.concat(chunks).toString("utf8");
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    const error = new Error("Request body must be valid JSON.");
    error.status = 400;
    throw error;
  }
}

function sendJson(request, response, config, status, payload) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    ...corsHeaders(request, config),
  });
  response.end(JSON.stringify(payload));
}

function sendHtml(response, html) {
  response.writeHead(200, {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(html);
}

async function streamNdjson(request, response, config, writeEvents) {
  response.writeHead(200, {
    "Content-Type": "application/x-ndjson; charset=utf-8",
    "Cache-Control": "no-store",
    ...corsHeaders(request, config),
  });

  const emit = async (event) => {
    response.write(`${JSON.stringify(event)}\n`);
  };

  try {
    await writeEvents(emit);
  } finally {
    response.end();
  }
}

function hasValidToken(request, config) {
  return Boolean(config.captureToken)
    && request.headers["x-capture-token"] === config.captureToken;
}

function requiresToken(request, tokenPolicy) {
  if (tokenPolicy === TOKEN_POLICIES.NONE) {
    return false;
  }

  if (tokenPolicy === TOKEN_POLICIES.SAME_ORIGIN && isLocalPageRequest(request)) {
    return false;
  }

  return true;
}

function isLocalPageRequest(request) {
  const origin = request.headers.origin;
  const fetchSite = request.headers["sec-fetch-site"];

  return (origin && isSameOriginRequest(request, origin))
    || fetchSite === "same-origin";
}

function isAllowedOrigin(request, config) {
  const origin = request.headers.origin;
  if (!origin) {
    return true;
  }

  return Boolean(
    (config.extensionOrigin && origin === config.extensionOrigin)
    || isSameOriginRequest(request, origin),
  );
}

function corsHeaders(request, config) {
  const origin = request.headers.origin;
  if (!origin || !isAllowedOrigin(request, config)) {
    return {};
  }

  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Capture-Token",
    "Access-Control-Max-Age": "600",
    Vary: "Origin",
  };
}

function isSameOriginRequest(request, origin) {
  const host = request.headers.host;
  if (!host) {
    return false;
  }

  return origin === `http://${host}` || origin === `https://${host}`;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const config = loadConfig();
  const server = createServer({ config });
  server.listen(config.port, () => {
    console.log(`Merida local operator backend listening on http://127.0.0.1:${config.port}`);
    console.log(`Job Posting Analysis UI available at http://127.0.0.1:${config.port}/analysis`);
    console.log(`Resume Creation UI available at http://127.0.0.1:${config.port}/resumes`);
  });
}
