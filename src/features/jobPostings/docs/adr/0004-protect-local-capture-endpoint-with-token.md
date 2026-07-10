# Protect local capture endpoint with token

The local backend requires a shared capture token on extension-to-backend requests and only allows CORS from the configured extension origin. Even though the backend runs locally, browser pages can attempt requests to localhost services, so capture writes need a low-friction guard before they can create pages in the user's Notion workspace.

The Chrome extension captures only after an explicit button click using `activeTab` and `scripting`. It does not request broad persistent host access for all pages in the MVP.

The backend owns Notion destination config and secrets, including the Notion token, database ID, capture token, optional LLM key, and port. The extension owns only the backend URL and capture token needed to call the local service; it never stores the Notion token or database ID. The backend exposes a health/config validation endpoint so the extension can report whether the service is online and whether the configured Notion schema is valid.

Job Posting Analysis uses the same local backend trust boundary. The existing backend serves the small local HTML analysis interface, keeps Notion and DeepSeek secrets server-side, and accepts analysis writes from the same localhost origin without exposing Notion, DeepSeek, or capture-token credentials in the browser UI.
