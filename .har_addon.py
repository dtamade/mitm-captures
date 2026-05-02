import json
import base64
import re
from datetime import datetime, timezone
from mitmproxy import ctx

class HarDumper:
    # Skip these content types (static resources)
    SKIP_CONTENT_TYPES = [
        r'image/',
        r'font/',
        r'audio/',
        r'video/',
        r'application/font',
        r'application/x-font',
        r'text/css',
        r'application/javascript',
        r'application/x-javascript',
        r'text/javascript',
    ]
    
    # Skip these file extensions
    SKIP_EXTENSIONS = [
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg', '.bmp',
        '.woff', '.woff2', '.ttf', '.otf', '.eot',
        '.css', '.js', '.map',
        '.mp3', '.mp4', '.webm', '.ogg', '.wav',
        '.pdf', '.zip', '.gz', '.tar',
    ]

    def __init__(self):
        self.har = {
            "log": {
                "version": "1.2",
                "creator": {"name": "mitmproxy-har", "version": "1.0"},
                "entries": []
            }
        }
        self.har_file = None
        self._skip_patterns = [re.compile(p, re.I) for p in self.SKIP_CONTENT_TYPES]

    def configure(self, updated):
        import os
        self.har_file = os.environ.get("MITM_HAR_FILE", "capture.har")

    def _should_skip(self, flow):
        # Check file extension
        path = flow.request.path.lower().split('?')[0]
        for ext in self.SKIP_EXTENSIONS:
            if path.endswith(ext):
                return True
        
        # Check response content-type
        content_type = flow.response.headers.get("content-type", "").lower()
        for pattern in self._skip_patterns:
            if pattern.search(content_type):
                return True
        
        return False

    def response(self, flow):
        # Skip static resources
        if self._should_skip(flow):
            return
        
        entry = {
            "startedDateTime": datetime.now(timezone.utc).isoformat(),
            "time": int((flow.response.timestamp_end - flow.request.timestamp_start) * 1000),
            "request": {
                "method": flow.request.method,
                "url": flow.request.pretty_url,
                "httpVersion": flow.request.http_version,
                "headers": [{"name": k, "value": v} for k, v in flow.request.headers.items()],
                "queryString": [{"name": k, "value": v} for k, v in flow.request.query.items()],
                "cookies": [{"name": k, "value": v} for k, v in flow.request.cookies.items()],
                "headersSize": len(str(flow.request.headers)),
                "bodySize": len(flow.request.content) if flow.request.content else 0,
            },
            "response": {
                "status": flow.response.status_code,
                "statusText": flow.response.reason,
                "httpVersion": flow.response.http_version,
                "headers": [{"name": k, "value": v} for k, v in flow.response.headers.items()],
                "cookies": [{"name": k, "value": v} for k, v in flow.response.cookies.items()],
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
            except:
                entry["request"]["postData"] = {
                    "mimeType": flow.request.headers.get("content-type", ""),
                    "text": base64.b64encode(flow.request.content).decode()
                }
        # Add response body (only if text-based)
        if flow.response.content:
            content_type = flow.response.headers.get("content-type", "").lower()
            # Only include body for text-based responses
            if any(t in content_type for t in ['json', 'xml', 'html', 'text/', 'javascript', 'x-www-form']):
                try:
                    entry["response"]["content"]["text"] = flow.response.content.decode("utf-8", errors="replace")
                except:
                    entry["response"]["content"]["text"] = base64.b64encode(flow.response.content).decode()
                    entry["response"]["content"]["encoding"] = "base64"
            else:
                # For binary, just note it was skipped
                entry["response"]["content"]["text"] = "[binary content not captured]"
        
        self.har["log"]["entries"].append(entry)
        self._save()

    def _save(self):
        if self.har_file:
            with open(self.har_file, "w") as f:
                json.dump(self.har, f, indent=2, ensure_ascii=False)

addons = [HarDumper()]
