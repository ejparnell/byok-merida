export function renderResumesPage() {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resume Creation</title>
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
      width: min(820px, 100%);
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

    .status-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
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

    .message {
      min-height: 22px;
      margin: 10px 0;
      color: #b42318;
      font-size: 14px;
    }

    ul {
      display: grid;
      gap: 0;
      padding: 0;
      margin: 12px 0 0;
      list-style: none;
    }

    li {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      border-top: 1px solid #e1e6ee;
      padding: 12px 0;
    }

    .posting {
      display: grid;
      gap: 4px;
      min-width: 0;
    }

    .posting strong,
    .posting span {
      overflow-wrap: anywhere;
    }

    .posting strong {
      font-size: 15px;
    }

    .posting span {
      color: #64748b;
      font-size: 13px;
    }

    button {
      height: 38px;
      border: 1px solid #1d4ed8;
      border-radius: 6px;
      padding: 0 14px;
      color: #ffffff;
      background: #1d4ed8;
      cursor: pointer;
      font: inherit;
      font-size: 14px;
      font-weight: 650;
      white-space: nowrap;
    }

    button:disabled {
      border-color: #b7c0ca;
      background: #d8dee7;
      color: #64748b;
      cursor: not-allowed;
    }

    .success {
      color: #166534;
    }

    .success a {
      color: #166534;
      font-weight: 650;
    }

    @media (max-width: 680px) {
      body {
        padding: 14px;
      }

      .status-grid,
      li {
        grid-template-columns: 1fr;
      }

      button {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <main>
    <h1>Resume Creation</h1>
    <section class="panel">
      <div class="status-grid">
        <div class="metric">
          <span>Ready</span>
          <strong id="queue">-</strong>
        </div>
        <div class="metric">
          <span>Status</span>
          <strong id="status">-</strong>
        </div>
      </div>

      <div id="message" class="message"></div>
      <ul id="queueList"></ul>
    </section>
  </main>

  <script>
    const queueEl = document.querySelector("#queue");
    const statusEl = document.querySelector("#status");
    const messageEl = document.querySelector("#message");
    const queueListEl = document.querySelector("#queueList");

    refreshStatus();

    async function refreshStatus() {
      messageEl.textContent = "";
      statusEl.textContent = "loading";
      queueListEl.replaceChildren();

      try {
        const response = await fetch("/resumes/status");
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          queueEl.textContent = "-";
          statusEl.textContent = "blocked";
          messageEl.textContent = firstMessage(payload.errors) || payload.message || "Status unavailable.";
          return;
        }

        queueEl.textContent = String(payload.queueCount);
        statusEl.textContent = "ready";
        for (const item of payload.items || []) {
          queueListEl.append(renderItem(item));
        }
      } catch (error) {
        queueEl.textContent = "-";
        statusEl.textContent = "offline";
        messageEl.textContent = error.message;
      }
    }

    function renderItem(item) {
      const li = document.createElement("li");
      li.dataset.pageId = item.id;

      const posting = document.createElement("div");
      posting.className = "posting";

      const title = document.createElement("strong");
      title.textContent = item.jobTitle || "Untitled role";

      const company = document.createElement("span");
      company.textContent = item.companyName || "Unknown company";

      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Create Resume";
      button.addEventListener("click", () => createResume(item, li, button));

      posting.append(title, company);
      li.append(posting, button);
      return li;
    }

    async function createResume(item, row, button) {
      button.disabled = true;
      messageEl.textContent = "";

      try {
        const response = await fetch("/resumes/create", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ jobPostingPageId: item.id }),
        });
        const payload = await response.json();

        if (!response.ok || payload.type === "failed") {
          throw new Error(payload.message || "Resume creation failed.");
        }

        row.remove();
        const remaining = queueListEl.querySelectorAll("li").length;
        queueEl.textContent = String(remaining);
        messageEl.className = "message success";
        messageEl.replaceChildren(successLink(payload));
      } catch (error) {
        messageEl.className = "message";
        messageEl.textContent = error.message;
        button.disabled = false;
      }
    }

    function successLink(payload) {
      const span = document.createElement("span");
      const link = document.createElement("a");
      const prefix = payload.type === "already_exists" ? "Resume already exists: " : "Resume created: ";
      span.append(prefix);
      link.href = payload.resume.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = payload.resume.name || "Open Resume";
      span.append(link);
      if (payload.note?.url) {
        const noteLink = document.createElement("a");
        noteLink.href = payload.note.url;
        noteLink.target = "_blank";
        noteLink.rel = "noreferrer";
        noteLink.textContent = payload.note.name || "Open Analysis Note";
        span.append(" | Analysis Note: ", noteLink);
      }
      if (payload.exportedPdf?.relativePath) {
        span.append(" | PDF: ", payload.exportedPdf.relativePath);
      }
      return span;
    }

    function firstMessage(values) {
      return Array.isArray(values) && values.length > 0 ? values[0] : "";
    }
  </script>
</body>
</html>`;
}
