#!/usr/bin/env python3
"""Generate index and summary artifacts from mitmproxy flow file."""

import json
import sys
from collections import Counter
from datetime import datetime, timezone


def iso_utc(timestamp):
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def safe_len(payload):
    if not payload:
        return 0
    return len(payload)


def status_bucket(status):
    if status is None:
        return "no-response"
    if 100 <= status < 200:
        return "1xx"
    if 200 <= status < 300:
        return "2xx"
    if 300 <= status < 400:
        return "3xx"
    if 400 <= status < 500:
        return "4xx"
    if 500 <= status < 600:
        return "5xx"
    return "other"


def flow_to_index_entry(index_id, flow):
    request = flow.request
    response = flow.response

    duration_ms = None
    if response and request.timestamp_start is not None and response.timestamp_end is not None:
        duration_ms = int((response.timestamp_end - request.timestamp_start) * 1000)

    status_code = response.status_code if response else None
    content_type = response.headers.get("content-type", "") if response else ""
    response_bytes = safe_len(response.content) if response else 0

    return {
        "id": index_id,
        "startedDateTime": iso_utc(request.timestamp_start),
        "method": request.method,
        "scheme": request.scheme,
        "host": request.host,
        "port": request.port,
        "path": request.path,
        "url": request.pretty_url,
        "status": status_code,
        "statusBucket": status_bucket(status_code),
        "durationMs": duration_ms,
        "requestBytes": safe_len(request.content),
        "responseBytes": response_bytes,
        "contentType": content_type,
    }


def to_markdown_table(rows, headers):
    if not rows:
        return "(none)"

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        escaped = [str(cell).replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def write_summary(flow_file, summary_file, entries):
    total = len(entries)
    responded = [item for item in entries if item["status"] is not None]
    no_response = total - len(responded)

    error_count = sum(1 for item in responded if item["status"] >= 400)
    durations = [item["durationMs"] for item in responded if item["durationMs"] is not None]
    avg_duration = int(sum(durations) / len(durations)) if durations else 0

    status_buckets = Counter(item["statusBucket"] for item in entries)
    top_hosts = Counter(item["host"] for item in entries if item["host"]).most_common(15)

    slowest = sorted(
        [item for item in entries if item["durationMs"] is not None],
        key=lambda item: item["durationMs"],
        reverse=True,
    )[:20]

    status_rows = [(key, value) for key, value in sorted(status_buckets.items(), key=lambda item: item[0])]
    host_rows = [(host, count) for host, count in top_hosts]
    slow_rows = [
        (
            item["id"],
            item["durationMs"],
            item["status"] if item["status"] is not None else "-",
            item["method"],
            item["host"],
            item["path"],
        )
        for item in slowest
    ]

    lines = []
    lines.append("# Capture Summary")
    lines.append("")
    lines.append(f"- Flow file: `{flow_file}`")
    lines.append(f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`")
    lines.append(f"- Total requests: `{total}`")
    lines.append(f"- Responses received: `{len(responded)}`")
    lines.append(f"- No response: `{no_response}`")
    lines.append(f"- 4xx/5xx count: `{error_count}`")
    lines.append(f"- Average duration (responded): `{avg_duration} ms`")
    lines.append("")
    lines.append("## Status buckets")
    lines.append("")
    lines.append(to_markdown_table(status_rows, ["Bucket", "Count"]))
    lines.append("")
    lines.append("## Top hosts")
    lines.append("")
    lines.append(to_markdown_table(host_rows, ["Host", "Count"]))
    lines.append("")
    lines.append("## Slowest requests (Top 20)")
    lines.append("")
    lines.append(to_markdown_table(slow_rows, ["ID", "ms", "Status", "Method", "Host", "Path"]))
    lines.append("")

    with open(summary_file, "w", encoding="utf-8") as output:
        output.write("\n".join(lines))


def main(argv):
    if len(argv) != 4:
        print(f"Usage: {argv[0]} <flow_file> <index_ndjson_file> <summary_md_file>")
        return 1

    flow_file = argv[1]
    index_file = argv[2]
    summary_file = argv[3]

    try:
        from mitmproxy.io import FlowReader
    except Exception as exc:
        print(f"Failed to import FlowReader: {exc}", file=sys.stderr)
        return 2

    entries = []
    with open(flow_file, "rb") as flow_stream:
        reader = FlowReader(flow_stream)
        for index_id, flow in enumerate(reader.stream(), start=1):
            entries.append(flow_to_index_entry(index_id, flow))

    with open(index_file, "w", encoding="utf-8") as output:
        for entry in entries:
            output.write(json.dumps(entry, ensure_ascii=False) + "\n")

    write_summary(flow_file, summary_file, entries)
    print(f"Generated {index_file} and {summary_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
