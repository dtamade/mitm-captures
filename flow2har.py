#!/usr/bin/env python3
"""Convert mitmproxy flow file to HAR format (filtered, AI-friendly)."""

import json
import sys
import base64
from datetime import datetime, timezone

# Skip static resources
SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg', '.bmp',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.css', '.js', '.map',
    '.mp3', '.mp4', '.webm', '.ogg', '.wav',
    '.pdf', '.zip', '.gz', '.tar',
}

SKIP_CONTENT_TYPES = {
    'image/', 'font/', 'audio/', 'video/',
    'application/font', 'application/x-font',
    'text/css', 'application/javascript', 'text/javascript',
}


def should_skip(flow):
    """Check if flow should be skipped (static resource)."""
    path = flow.request.path.lower().split('?')[0]
    for ext in SKIP_EXTENSIONS:
        if path.endswith(ext):
            return True

    if flow.response:
        content_type = flow.response.headers.get("content-type", "").lower()
        for skip_type in SKIP_CONTENT_TYPES:
            if skip_type in content_type:
                return True
    return False


def serialize_cookies(cookies):
    """Safely serialize cookies."""
    result = []
    try:
        for k, v in cookies.items():
            if isinstance(v, (tuple, list)):
                result.append({"name": str(k), "value": str(v[0]) if v else ""})
            else:
                result.append({"name": str(k), "value": str(v)})
    except Exception:
        pass
    return result


def flow_to_entry(flow):
    """Convert a single flow to HAR entry."""
    if not flow.response:
        return None

    try:
        entry = {
            "startedDateTime": datetime.fromtimestamp(
                flow.request.timestamp_start, timezone.utc
            ).isoformat(),
            "time": int((flow.response.timestamp_end - flow.request.timestamp_start) * 1000),
            "request": {
                "method": flow.request.method,
                "url": flow.request.pretty_url,
                "httpVersion": flow.request.http_version,
                "headers": [{"name": k, "value": v} for k, v in flow.request.headers.items()],
                "queryString": [{"name": k, "value": v} for k, v in flow.request.query.items()],
                "cookies": serialize_cookies(flow.request.cookies),
                "headersSize": len(str(flow.request.headers)),
                "bodySize": len(flow.request.content) if flow.request.content else 0,
            },
            "response": {
                "status": flow.response.status_code,
                "statusText": flow.response.reason or "",
                "httpVersion": flow.response.http_version,
                "headers": [{"name": k, "value": v} for k, v in flow.response.headers.items()],
                "cookies": serialize_cookies(flow.response.cookies),
                "content": {
                    "size": len(flow.response.content) if flow.response.content else 0,
                    "mimeType": flow.response.headers.get("content-type", "application/octet-stream"),
                },
                "redirectURL": flow.response.headers.get("location", ""),
                "headersSize": len(str(flow.response.headers)),
                "bodySize": len(flow.response.content) if flow.response.content else 0,
            },
            "cache": {},
            "timings": {"send": 0, "wait": 0, "receive": 0},
        }

        # Add request body
        if flow.request.content:
            try:
                entry["request"]["postData"] = {
                    "mimeType": flow.request.headers.get("content-type", ""),
                    "text": flow.request.content.decode("utf-8", errors="replace")
                }
            except Exception:
                entry["request"]["postData"] = {
                    "mimeType": flow.request.headers.get("content-type", ""),
                    "text": base64.b64encode(flow.request.content).decode()
                }

        # Add response body (only text-based)
        if flow.response.content:
            content_type = flow.response.headers.get("content-type", "").lower()
            if any(t in content_type for t in ['json', 'xml', 'html', 'text/', 'x-www-form']):
                try:
                    entry["response"]["content"]["text"] = flow.response.content.decode("utf-8", errors="replace")
                except Exception:
                    entry["response"]["content"]["text"] = base64.b64encode(flow.response.content).decode()
                    entry["response"]["content"]["encoding"] = "base64"
            else:
                entry["response"]["content"]["text"] = "[binary content not captured]"

        return entry
    except Exception as e:
        print(f"Error converting flow: {e}", file=sys.stderr)
        return None


def convert(flow_file, har_file):
    """Convert flow file to HAR."""
    from mitmproxy.io import FlowReader

    har = {
        "log": {
            "version": "1.2",
            "creator": {"name": "flow2har", "version": "1.0"},
            "entries": []
        }
    }

    with open(flow_file, "rb") as f:
        reader = FlowReader(f)
        for flow in reader.stream():
            if should_skip(flow):
                continue
            entry = flow_to_entry(flow)
            if entry:
                har["log"]["entries"].append(entry)

    with open(har_file, "w") as f:
        json.dump(har, f, indent=2, ensure_ascii=False)

    print(f"Converted {len(har['log']['entries'])} entries to {har_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <flow_file> <har_file>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
