"""Loopback-only Viewer with deterministic Python checks and model-bound history."""
import argparse
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

VIEWER = Path(__file__).resolve().parent
ACC = VIEWER.parent
sys.path.insert(0, str(ACC / "src"))
from compliance_contract import read, save, load_contracts
from compliance_runner import run
from export_compliance import model_paths

RUN_LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Local model registrations and exports must be visible after refresh.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def reply(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def local_request(self):
        host = self.headers.get("Host", "")
        expected = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        return host in (expected, f"localhost:{self.server.server_port}") and (not origin or origin in (f"http://{expected}", f"http://localhost:{self.server.server_port}"))

    def do_GET(self):
        if not self.local_request():
            return self.reply(403, {"error": "Local requests only"})
        parsed = urlparse(self.path)
        if parsed.path == "/api/contracts":
            return self.reply(200, load_contracts())
        if parsed.path == "/api/history":
            model_id = parse_qs(parsed.query).get("model_id", [None])[0]
            if model_id not in model_paths():
                return self.reply(400, {"error": "Unknown model"})
            reports = [read(p) for p in sorted((ACC / "runs" / model_id).glob("*.json"))]
            return self.reply(200, sorted(reports, key=lambda r: r["timestamp"], reverse=True))
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/run" or not self.local_request():
            return self.reply(403, {"error": "Local run endpoint required"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                raise ValueError("Facts payload must be between 1 byte and 2 MB")
            request = json.loads(self.rfile.read(length))
            model_id = request.get("model_id")
            paths = model_paths()
            if model_id not in paths:
                raise ValueError("Unknown model")
            facts_path = ACC / "reviewed_facts" / f"{model_id}.json"
            facts = request.get("facts")
            if facts is None:
                facts = read(facts_path) if facts_path.exists() else {}
            if not isinstance(facts, dict) or not isinstance(facts.get("facts_by_rule", {}), dict):
                raise ValueError("Facts must contain a facts_by_rule object")
            # Serialized publication avoids concurrent writes. Historical runs are always new files.
            with RUN_LOCK:
                report = run(paths[model_id], model_id, facts, request.get("rule_ids"))
                save(VIEWER / "dist/data" / f"compliance-{model_id}.json", report)
            self.reply(200, report)
        except (ValueError, KeyError, TypeError) as exc:
            self.reply(400, {"error": str(exc)})
        except Exception as exc:
            self.reply(500, {"error": f"CHECK_ERROR: {type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(VIEWER / "dist")))
    print(f"Viewer and ACC: http://127.0.0.1:{args.port}/", flush=True)
    server.serve_forever()
