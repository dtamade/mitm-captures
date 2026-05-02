#!/usr/bin/env python3
"""Build AI-friendly analysis artifacts from capture manifest and index files."""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_index(path):
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            entries.append(json.loads(text))
    return entries


def endpoint_key(item):
    method = item.get("method") or ""
    host = item.get("host") or ""
    path = item.get("path") or ""
    return f"{method} {host}{path}"


def calc_stats(entries):
    total = len(entries)
    responded = [entry for entry in entries if entry.get("status") is not None]
    no_response = total - len(responded)

    durations = [entry.get("durationMs") for entry in responded if isinstance(entry.get("durationMs"), int)]
    avg_ms = int(sum(durations) / len(durations)) if durations else 0
    p95_ms = 0
    if durations:
        sorted_durations = sorted(durations)
        p95_idx = int((len(sorted_durations) - 1) * 0.95)
        p95_ms = sorted_durations[p95_idx]

    status_buckets = Counter(entry.get("statusBucket") or "unknown" for entry in entries)
    top_hosts = Counter(entry.get("host") or "" for entry in entries if entry.get("host")).most_common(15)

    endpoint_counter = Counter(endpoint_key(entry) for entry in entries)
    top_endpoints = endpoint_counter.most_common(30)

    error_entries = [entry for entry in responded if isinstance(entry.get("status"), int) and entry.get("status") >= 400]
    error_counter = Counter(endpoint_key(entry) for entry in error_entries)
    top_error_endpoints = error_counter.most_common(20)

    slow_entries = sorted(
        [entry for entry in responded if isinstance(entry.get("durationMs"), int)],
        key=lambda item: item.get("durationMs", 0),
        reverse=True,
    )[:30]

    endpoint_status_counter = defaultdict(Counter)
    for entry in entries:
        ep = endpoint_key(entry)
        bucket = entry.get("statusBucket") or "unknown"
        endpoint_status_counter[ep][bucket] += 1

    error_prone = []
    for ep, bucket_counter in endpoint_status_counter.items():
        total_ep = sum(bucket_counter.values())
        err_ep = bucket_counter.get("4xx", 0) + bucket_counter.get("5xx", 0)
        if total_ep >= 2 and err_ep > 0:
            ratio = err_ep / total_ep
            error_prone.append((ep, total_ep, err_ep, ratio))
    error_prone.sort(key=lambda item: (item[3], item[2], item[1]), reverse=True)

    return {
        "totalRequests": total,
        "respondedRequests": len(responded),
        "noResponseRequests": no_response,
        "avgDurationMs": avg_ms,
        "p95DurationMs": p95_ms,
        "statusBuckets": dict(status_buckets),
        "topHosts": [{"host": host, "count": count} for host, count in top_hosts],
        "topEndpoints": [{"endpoint": ep, "count": count} for ep, count in top_endpoints],
        "topErrorEndpoints": [{"endpoint": ep, "count": count} for ep, count in top_error_endpoints],
        "slowestRequests": [
            {
                "id": item.get("id"),
                "durationMs": item.get("durationMs"),
                "status": item.get("status"),
                "method": item.get("method"),
                "host": item.get("host"),
                "path": item.get("path"),
                "url": item.get("url"),
            }
            for item in slow_entries
        ],
        "errorProneEndpoints": [
            {
                "endpoint": ep,
                "total": total_ep,
                "errors": err_ep,
                "errorRatio": round(ratio, 4),
            }
            for ep, total_ep, err_ep, ratio in error_prone[:20]
        ],
    }


def build_findings(stats):
    findings = []

    findings.append(f"Total requests: {stats['totalRequests']}, responses: {stats['respondedRequests']}, no response: {stats['noResponseRequests']}.")
    findings.append(f"Latency baseline: avg={stats['avgDurationMs']}ms, p95={stats['p95DurationMs']}ms.")

    errors = stats["statusBuckets"].get("4xx", 0) + stats["statusBuckets"].get("5xx", 0)
    if stats["respondedRequests"] > 0:
        err_ratio = round(errors / stats["respondedRequests"] * 100, 2)
        findings.append(f"Error responses (4xx/5xx): {errors} ({err_ratio}% of responded).")
    else:
        findings.append("No responded requests captured.")

    if stats["slowestRequests"]:
        slow = stats["slowestRequests"][0]
        findings.append(
            f"Slowest request: {slow.get('durationMs')}ms {slow.get('method')} {slow.get('host')}{slow.get('path')} (status={slow.get('status')})."
        )

    if stats["topErrorEndpoints"]:
        top = stats["topErrorEndpoints"][0]
        findings.append(f"Most frequent error endpoint: {top['endpoint']} ({top['count']} errors).")

    return findings


def build_ai_json(manifest, stats):
    analysis_targets = {
        "rootCause": "Identify likely root causes for errors and latency spikes.",
        "timeline": "Reconstruct key request timeline around failures.",
        "grouping": "Group requests by user action and backend dependency.",
        "regression": "Highlight patterns that look like regressions or flaky behavior.",
    }

    files = manifest.get("artifacts") or manifest.get("files") or {}

    return {
        "schemaVersion": "1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "capture": {
            "runId": manifest.get("runId", ""),
            "startedAt": manifest.get("startedAt", ""),
            "stoppedAt": manifest.get("stoppedAt", ""),
            "listen": manifest.get("listen", {}),
        },
        "files": {
            "flow": files.get("flow", ""),
            "har": files.get("har", ""),
            "index": files.get("index", ""),
            "summary": files.get("summary", ""),
            "manifest": files.get("manifest", manifest.get("manifest", "")),
            "aiJson": files.get("aiJson", ""),
            "aiMd": files.get("aiMd", ""),
        },
        "stats": stats,
        "findings": build_findings(stats),
        "analysisTargets": analysis_targets,
        "notes": [
            "Raw capture data remains unchanged.",
            "Use index for fast triage and flow/har for deep inspection.",
        ],
    }


def render_ai_markdown(ai_payload):
    stats = ai_payload["stats"]
    lines = []
    lines.append("# AI Analysis Brief")
    lines.append("")
    lines.append("## Context")
    lines.append("")
    lines.append(f"- Run ID: `{ai_payload['capture'].get('runId', '')}`")
    lines.append(f"- Started: `{ai_payload['capture'].get('startedAt', '')}`")
    lines.append(f"- Stopped: `{ai_payload['capture'].get('stoppedAt', '')}`")
    lines.append(f"- Total requests: `{stats.get('totalRequests', 0)}`")
    lines.append(f"- Avg/P95 latency: `{stats.get('avgDurationMs', 0)}ms / {stats.get('p95DurationMs', 0)}ms`")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    for key, value in ai_payload["files"].items():
        if value:
            lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    for finding in ai_payload.get("findings", []):
        lines.append(f"- {finding}")
    lines.append("")
    lines.append("## Suggested AI Tasks")
    lines.append("")
    for key, value in ai_payload.get("analysisTargets", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    lines.append("## Prompt Template")
    lines.append("")
    lines.append("```text")
    lines.append("You are analyzing a mitmproxy capture.")
    lines.append("Focus on error root causes, latency bottlenecks, and suspicious request patterns.")
    lines.append("Use index.ndjson for aggregation, and flow/har for deep dives.")
    lines.append("Return:")
    lines.append("1) Top 5 root-cause hypotheses with evidence")
    lines.append("2) Endpoint-level latency/error table")
    lines.append("3) Suspected dependency failures and retry chains")
    lines.append("4) Concrete next verification steps")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main(argv):
    if len(argv) != 5:
        print(f"Usage: {argv[0]} <manifest_json> <index_ndjson> <ai_json_out> <ai_md_out>")
        return 1

    manifest_path = argv[1]
    index_path = argv[2]
    ai_json_path = argv[3]
    ai_md_path = argv[4]

    manifest = load_manifest(manifest_path)
    entries = load_index(index_path)
    stats = calc_stats(entries)
    ai_payload = build_ai_json(manifest, stats)

    with open(ai_json_path, "w", encoding="utf-8") as f:
        json.dump(ai_payload, f, indent=2, ensure_ascii=False)

    with open(ai_md_path, "w", encoding="utf-8") as f:
        f.write(render_ai_markdown(ai_payload))

    print(f"Generated {ai_json_path} and {ai_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
