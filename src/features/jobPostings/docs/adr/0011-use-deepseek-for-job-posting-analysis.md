# Use DeepSeek for job posting analysis

Job Posting Analysis uses DeepSeek as the configured LLM provider through a backend-only `DEEPSEEK_API_KEY`. The local HTML interface never receives the key, and the first implementation should keep the provider integration small and direct instead of adding a multi-provider abstraction before another provider is needed.

DeepSeek configuration is required only for analysis endpoints. Capture endpoints remain usable without `DEEPSEEK_API_KEY`; health/status can report `analysisConfigured: false`, and the local analysis interface should disable analysis controls with a clear message instead of breaking capture.

The default analysis model is `deepseek-v4-flash` for fast local batch runs. Configuration should allow `deepseek-v4-pro` through a `DEEPSEEK_MODEL` override in `.env`, so higher-quality analysis can be selected without changing code or adding model selection to the local UI. Configuration should reject deprecated DeepSeek aliases such as `deepseek-chat` and `deepseek-reasoner`; the `/chat/completions` URL is the OpenAI-compatible API endpoint used by the supported v4 model IDs, not a request to the deprecated `deepseek-chat` model.
