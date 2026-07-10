export class FitRuntimeClient {
  constructor({ baseUrl, fetchImpl = fetch }) {
    this.baseUrl = String(baseUrl || "").replace(/\/$/, "");
    this.fetch = fetchImpl;
  }

  async health() {
    if (!this.baseUrl) {
      return { ok: false, message: "FIT_RUNTIME_URL is not configured." };
    }

    try {
      const response = await this.fetch(`${this.baseUrl}/health`);
      const payload = await response.json().catch(() => ({}));
      return {
        ok: response.ok && payload.ok === true,
        ...payload,
      };
    } catch (error) {
      return {
        ok: false,
        message: error.message || "Resume Fit Analysis runtime is unavailable.",
      };
    }
  }

  async candidates(input) {
    return this.post("/fit/candidates", input);
  }

  async score(input) {
    return this.post("/fit/score", input);
  }

  async post(path, input) {
    const response = await this.fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || `Fit runtime request failed with ${response.status}`);
    }
    return payload;
  }
}
