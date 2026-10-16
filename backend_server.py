"""Small HTTP backend for testing the Streamlit AI-analysis integration."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from run_analysis import run_codex_analysis


HOST = os.getenv("AI_BACKEND_HOST", "127.0.0.1")
PORT = int(os.getenv("AI_BACKEND_PORT", "8000"))
TOKEN = os.getenv("AI_BACKEND_TOKEN", "")


class AnalysisHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/health":
            self._send(200, {"status": "ok", "service": "stock-strategy-ai-backend"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/analyze":
            self._send(404, {"error": "not found"})
            return
        if TOKEN and self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._send(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
            report = run_codex_analysis(
                data.get("stock_code", ""),
                data.get("depth", "标准"),
                bool(data.get("enable_debate", True)),
                bool(data.get("enable_risk", True)),
                bool(data.get("save_history", True)),
            )
            self._send(200, {"report": report})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"invalid request: {exc}"})
        except Exception as exc:  # Keep errors inside the JSON API boundary.
            self._send(500, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[backend] {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), AnalysisHandler)
    print(f"AI backend listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
