"""Run a local web workspace for the AI consulting content pipeline."""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from web import workspace_service

ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "web" / "static"


class WorkspaceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self._serve_file(STATIC_DIR / "index.html")
            return
        if parsed.path.startswith("/static/"):
            self._serve_file(STATIC_DIR / parsed.path.removeprefix("/static/"))
            return
        if parsed.path == "/api/dashboard":
            self._send_json(workspace_service.get_dashboard_data())
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/collect-news":
                self._send_json(workspace_service.collect_news())
                return
            if parsed.path == "/api/candidate-status":
                payload = self._read_json()
                self._send_json(workspace_service.update_candidate_status(int(payload["index"]), str(payload["status"])))
                return
            if parsed.path == "/api/add-inspiration":
                self._send_json(workspace_service.add_inspiration(self._read_json()))
                return
            if parsed.path == "/api/delete-inspiration":
                payload = self._read_json()
                self._send_json(workspace_service.delete_inspiration(int(payload["index"])))
                return
            if parsed.path == "/api/promote-selected":
                self._send_json(workspace_service.promote_selected_candidates())
                return
            if parsed.path == "/api/generate-content":
                self._send_json(workspace_service.generate_content(self._read_json()))
                return
            if parsed.path == "/api/generate-facts":
                self._send_json(workspace_service.generate_facts(self._read_json()))
                return
            if parsed.path == "/api/generate-outlines":
                self._send_json(workspace_service.generate_outlines(self._read_json()))
                return
            if parsed.path == "/api/generate-drafts":
                self._send_json(workspace_service.generate_drafts(self._read_json()))
                return
            if parsed.path == "/api/review-drafts":
                self._send_json(workspace_service.review_drafts(self._read_json()))
                return
            if parsed.path == "/api/view-file":
                payload = self._read_json()
                self._send_json(workspace_service.read_file_content(payload["path"]))
                return
            self.log_message("unmatched POST path: %s", parsed.path)
            self._send_json({"error": "Not found"}, status=404)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as exc:
            self.log_message("client disconnected before response was sent: %s", exc)
        except Exception as exc:
            try:
                self._send_json({"error": str(exc)}, status=400)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as send_exc:
                self.log_message("client disconnected before error response was sent: %s", send_exc)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as exc:
            self.log_message("client disconnected while sending json response: %s", exc)

    def _serve_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self._send_json({"error": "Not found"}, status=404)
            return
        content = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as exc:
            self.log_message("client disconnected while sending file response: %s", exc)

    def log_message(self, format, *args):
        print("[web] " + format % args)


def run(host="127.0.0.1", port=None):
    port = int(port or os.getenv("WEB_PORT", "8010"))
    server = ThreadingHTTPServer((host, port), WorkspaceHandler)
    print(f"AI咨询内容工作台已启动: http://{host}:{port}")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()


if __name__ == "__main__":
    run()
