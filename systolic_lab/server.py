"""Loopback-only demonstration server using the Python standard library."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .simulator import Config, simulate, synthetic

WEB = Path(__file__).parent / "web"
DEMO_A = [[1, 2, 3], [4, 5, 6]]
DEMO_B = [[7, 8], [9, 10], [11, 12]]


def request_simulation(query):
    allowed = {"m", "k", "n", "rows", "cols", "bandwidth", "latency", "scratchpad",
               "seed", "demo", "trace"}
    if set(query) - allowed or any(len(v) != 1 for v in query.values()):
        raise ValueError("unknown or repeated query parameter")
    values = {key: int(value[0]) for key, value in query.items()}
    if values.get("trace", 1) not in (0, 1) or values.get("demo", 0) not in (0, 1):
        raise ValueError("demo and trace must be 0 or 1")
    m, k, n = (values.get(key, 2 if key != "k" else 3) for key in ("m", "k", "n"))
    if any(not 1 <= x <= 32 for x in (m, k, n)):
        raise ValueError("browser matrix dimensions must be in [1, 32]")
    config = Config(**{key: values[key] for key in
                       ("rows", "cols", "bandwidth", "latency", "scratchpad") if key in values})
    if config.rows > 8 or config.cols > 8:
        raise ValueError("browser array dimensions must be in [1, 8]")
    a, b = (DEMO_A, DEMO_B) if values.get("demo") else synthetic(m, k, n, values.get("seed", 7))
    data = simulate(a, b, config, trace=bool(values.get("trace", 1)))
    data["input_kind"] = "fixed teaching example" if values.get("demo") else "seeded synthetic"
    data["seed"] = None if values.get("demo") else values.get("seed", 7)
    return data


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/simulate":
            try:
                data = request_simulation(parse_qs(url.query, keep_blank_values=True))
                self.send(200, json.dumps(data).encode(), "application/json; charset=utf-8")
            except (ValueError, TypeError) as exc:
                self.send(400, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                  "/style.css": ("style.css", "text/css"),
                  "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        if url.path not in assets:
            self.send(404, b"Not found", "text/plain")
            return
        filename, mime = assets[url.path]
        self.send(200, (WEB / filename).read_bytes(), mime + "; charset=utf-8")


def serve(port=8000):
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Systolic Lab: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
