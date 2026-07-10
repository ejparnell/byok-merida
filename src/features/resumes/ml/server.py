import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from analysis import candidate_matches, load_normalization_dictionary, score_fit


DICTIONARY = load_normalization_dictionary()


class FitRuntimeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self.send_json({
                "ok": True,
                "service": "resume-fit-runtime",
                "dictionaryLoaded": True,
                "dictionaryVersion": DICTIONARY["version"],
                "skillCount": len(DICTIONARY["skills"]),
            })
            return
        self.send_json({"ok": False, "message": "Not found."}, status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.read_json()
            if path == "/fit/candidates":
                result = {
                    "ok": True,
                    "candidates": candidate_matches(
                        body.get("requirements", []),
                        body.get("evidenceItems", []),
                        DICTIONARY,
                    ),
                }
                self.send_json(result)
                return
            if path == "/fit/score":
                result = score_fit(
                    body.get("requirements", []),
                    body.get("evidenceItems", []),
                    body.get("candidates", []),
                    body.get("semanticSimilarities", {}),
                )
                self.send_json({"ok": True, **result})
                return
            self.send_json({"ok": False, "message": "Not found."}, status=404)
        except Exception as error:
            self.send_json({"ok": False, "message": str(error)}, status=400)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def send_json(self, payload, status=200):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        if os.environ.get("FIT_RUNTIME_DEBUG") == "1":
            super().log_message(format, *args)


def main():
    port = int(os.environ.get("FIT_RUNTIME_PORT", "3218"))
    server = ThreadingHTTPServer(("127.0.0.1", port), FitRuntimeHandler)
    print(f"Resume fit runtime listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
