from __future__ import annotations

import json
import mimetypes
import os
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
PORT = int(os.environ.get("PORT", "8765"))


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


DOTENV = load_dotenv(ROOT / ".env")
API_KEY = os.environ.get("OPENDART_API_KEY", DOTENV.get("OPENDART_API_KEY", "")).strip()


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "DARTWorkshopStarter/1.0"

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, relative_path: str) -> None:
        target = (STATIC_DIR / relative_path).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/index":
            route = parse_qs(parsed.query).get("__route", [""])[0]
            path = "/" if not route else f"/{route.lstrip('/')}"
        if path == "/api/health":
            self.send_json({
                "app": {"id": "kr.opendart.dart-hr-workshop-starter"},
                "api_key_configured": bool(API_KEY),
                "stage": "starter",
            })
            return
        if path in {"/api/companies", "/api/financials", "/api/people"}:
            self.send_json(
                {"status": "not_implemented", "path": path, "message": "Claude Code 실습에서 구현합니다."},
                HTTPStatus.NOT_IMPLEMENTED,
            )
            return
        if path in {"/", "/index.html"}:
            self.serve_file("index.html")
            return
        if path.startswith("/static/"):
            self.serve_file(path.removeprefix("/static/"))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        message = f"[starter] {self.address_string()} {format % args}"
        print(message.encode("ascii", "backslashreplace").decode("ascii"))


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), DashboardHandler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"DART HR Workshop Starter: {url}")
    print(f"OpenDART key configured: {bool(API_KEY)}")
    if os.environ.get("DART_OPEN_BROWSER", "true").lower() != "false":
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
