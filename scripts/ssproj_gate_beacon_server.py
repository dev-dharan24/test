#!/usr/bin/env python3
"""Loopback response/log server for the automatic `.ssproj` URL-sink gate."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from build_ssproj_launchservices_candidate import html_payload, js_payload, svg_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--marker-token", required=True)
    args = parser.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)

    script = js_payload(args.marker_token)
    # If SVG/HTML script ever runs, this extra request distinguishes script
    # execution from the initial image/video subresource request even when Node
    # is unavailable.  It is diagnostic only and never counts as command ACE.
    execution_beacon = (
        "try{fetch('http://127.0.0.1:18765/EXECUTED?via=script',{mode:'no-cors'})}catch(e){};"
    )
    script = execution_beacon + script
    svg = svg_payload(script).encode()
    html = html_payload(script).encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "ScreenSnapGate/1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
            record = {
                "path": self.path,
                "method": "GET",
                "client": self.client_address[0],
                "headers": {k.lower(): v for k, v in self.headers.items()},
            }
            with args.log.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")
                stream.flush()
            path = urlsplit(self.path).path
            if path == "/payload.svg":
                body, content_type = svg, "image/svg+xml"
            elif path == "/payload.html":
                body, content_type = html, "text/html; charset=utf-8"
            else:
                body, content_type = b"ok\n", "text/plain; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
