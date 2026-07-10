export function renderAnalysisPage() {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job Posting Analysis</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2933;
      background: #f6f7f9;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      padding: 24px;
    }

    main {
      width: min(760px, 100%);
      margin: 0 auto;
    }

    h1 {
      margin: 0 0 16px;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 0;
    }

    .panel {
      border: 1px solid #d8dee7;
      border-radius: 8px;
      background: #ffffff;
      padding: 16px;
    }

    .controls {
      display: grid;
      grid-template-columns: 120px auto;
      gap: 10px;
      align-items: end;
    }

    label {
      display: grid;
      gap: 6px;
      font-size: 13px;
      font-weight: 600;
    }

    input,
    button {
      height: 38px;
      border-radius: 6px;
      font: inherit;
      font-size: 14px;
    }

    input {
      width: 100%;
      border: 1px solid #c8d1dc;
      padding: 0 10px;
      background: #ffffff;
    }

    button {
      border: 1px solid #1d4ed8;
      padding: 0 14px;
      color: #ffffff;
      background: #1d4ed8;
      cursor: pointer;
      font-weight: 650;
    }

    button:disabled {
      border-color: #b7c0ca;
      background: #d8dee7;
      color: #64748b;
      cursor: not-allowed;
    }

    .status-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0;
    }

    .metric {
      border: 1px solid #e1e6ee;
      border-radius: 8px;
      padding: 10px;
      min-height: 64px;
    }

    .metric span {
      display: block;
      font-size: 12px;
      color: #64748b;
    }

    .metric strong {
      display: block;
      margin-top: 4px;
      font-size: 18px;
    }

    .current {
      min-height: 24px;
      margin: 10px 0;
      font-size: 14px;
      color: #334155;
    }

    .message {
      min-height: 22px;
      margin-top: 10px;
      color: #b42318;
      font-size: 14px;
    }

    ul {
      display: grid;
      gap: 8px;
      padding: 0;
      margin: 12px 0 0;
      list-style: none;
    }

    li {
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      border-top: 1px solid #e1e6ee;
      padding-top: 8px;
      font-size: 14px;
    }

    .pill {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      min-height: 24px;
      border-radius: 999px;
      padding: 0 8px;
      font-size: 12px;
      font-weight: 700;
      background: #eef2f7;
      color: #334155;
    }

    .analyzed,
    .repaired {
      background: #dcfce7;
      color: #166534;
    }

    .failed {
      background: #fee2e2;
      color: #991b1b;
    }

    .skipped {
      background: #fef3c7;
      color: #92400e;
    }

    @media (max-width: 680px) {
      body {
        padding: 14px;
      }

      .controls,
      .status-grid,
      li {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <h1>Job Posting Analysis</h1>
    <section class="panel">
      <div class="controls">
        <label>
          Batch
          <input id="limit" type="number" min="1" max="25" value="5">
        </label>
        <button id="run" type="button" disabled>Run Analysis</button>
      </div>

      <div class="status-grid">
        <div class="metric">
          <span>To Apply</span>
          <strong id="queue">-</strong>
        </div>
        <div class="metric">
          <span>Analysis</span>
          <strong id="analysis">-</strong>
        </div>
        <div class="metric">
          <span>Model</span>
          <strong id="model">-</strong>
        </div>
      </div>

      <div id="current" class="current"></div>
      <div id="message" class="message"></div>
      <ul id="results"></ul>
    </section>
  </main>

  <script>
    const limitInput = document.querySelector("#limit");
    const runButton = document.querySelector("#run");
    const queueEl = document.querySelector("#queue");
    const analysisEl = document.querySelector("#analysis");
    const modelEl = document.querySelector("#model");
    const currentEl = document.querySelector("#current");
    const messageEl = document.querySelector("#message");
    const resultsEl = document.querySelector("#results");

    runButton.addEventListener("click", runAnalysis);

    refreshStatus();

    async function refreshStatus() {
      messageEl.textContent = "";
      runButton.disabled = true;

      try {
        const response = await fetch("/analysis/status");
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          queueEl.textContent = "-";
          analysisEl.textContent = "blocked";
          modelEl.textContent = payload.model || "-";
          messageEl.textContent = firstMessage(payload.errors) || payload.message || "Status unavailable.";
          return;
        }

        queueEl.textContent = String(payload.queueCount);
        analysisEl.textContent = payload.analysisConfigured ? "ready" : "missing";
        modelEl.textContent = payload.model || "-";
        messageEl.textContent = payload.analysisConfigured ? "" : firstMessage(payload.warnings);
        runButton.disabled = !payload.analysisConfigured;
      } catch (error) {
        analysisEl.textContent = "offline";
        messageEl.textContent = error.message;
      }
    }

    async function runAnalysis() {
      runButton.disabled = true;
      resultsEl.replaceChildren();
      messageEl.textContent = "";
      currentEl.textContent = "Starting...";

      try {
        const response = await fetch("/analysis/run", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ limit: Number(limitInput.value || 5) }),
        });

        if (!response.ok || !response.body) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.message || "Analysis run failed.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const read = await reader.read();
          if (read.done) break;
          buffer += decoder.decode(read.value, { stream: true });
          const lines = buffer.split("\\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (line.trim()) handleEvent(JSON.parse(line));
          }
        }

        if (buffer.trim()) {
          handleEvent(JSON.parse(buffer));
        }
      } catch (error) {
        messageEl.textContent = error.message;
      } finally {
        await refreshStatus();
      }
    }

    function handleEvent(event) {
      if (event.type === "run_started") {
        currentEl.textContent = "0 of " + event.total;
      }

      if (event.type === "item_started") {
        currentEl.textContent = event.index + " of " + event.total + " - " + event.item.title;
      }

      if (event.type === "item_finished") {
        const li = document.createElement("li");
        const status = document.createElement("span");
        const text = document.createElement("span");
        status.className = "pill " + event.result.status;
        status.textContent = event.result.status;
        text.textContent = event.item.title + " - " + event.result.message;
        li.append(status, text);
        resultsEl.append(li);
      }

      if (event.type === "run_finished") {
        currentEl.textContent = "Done";
        if (event.message) messageEl.textContent = event.message;
      }
    }

    function firstMessage(values) {
      return Array.isArray(values) && values.length > 0 ? values[0] : "";
    }
  </script>
</body>
</html>`;
}
