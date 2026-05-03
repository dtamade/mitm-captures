#!/usr/bin/env bash
# startCaptures.sh - Start mitmproxy capture in current directory

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./startCaptures.sh [options]

Options:
  -p, --program             Program mode (do not modify GNOME proxy)
  -H, --host <host>         Listen host (default: 127.0.0.1)
  -P, --port <port>         Listen port (default: 18080)
  -d, --dir <path>          Target directory to store captures (default: current dir)
      --force-recover       Clean stale state file automatically
  -h, --help                Show this help

Examples:
  ./startCaptures.sh
  ./startCaptures.sh --program --port 18081
  ./startCaptures.sh --dir /path/to/project
EOF
}

warn() {
    echo "[WARN] $*" >&2
}

err() {
    echo "[ERROR] $*" >&2
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        err "Missing command: $1"
        exit 1
    fi
}

require_value_arg() {
    local opt="$1"
    local value="${2:-}"
    if [[ -z "$value" || "$value" == -* ]]; then
        err "Option $opt requires a value"
        exit 1
    fi
}

port_in_use() {
    local port="$1"

    if command -v ss >/dev/null 2>&1; then
        ss -H -ltn "sport = :$port" 2>/dev/null | grep -q .
        return $?
    fi

    if command -v lsof >/dev/null 2>&1; then
        lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    fi

    return 1
}

read_kv() {
    local key="$1"
    local file="$2"
    local line

    line="$(grep -E "^${key}=" "$file" | tail -n 1 || true)"
    line="${line#*=}"
    line="${line%$'\r'}"
    line="${line#\"}"
    line="${line%\"}"
    line="${line#\'}"
    line="${line%\'}"
    printf '%s' "$line"
}

proxy_get() {
    local schema="$1"
    local key="$2"
    local value

    value="$(gsettings get "$schema" "$key" 2>/dev/null || true)"
    value="${value#\'}"
    value="${value%\'}"
    printf '%s' "$value"
}

set_gnome_proxy_manual() {
    local host="$1"
    local port="$2"

    gsettings set org.gnome.system.proxy mode 'manual' >/dev/null 2>&1 || return 1
    gsettings set org.gnome.system.proxy.http host "$host" >/dev/null 2>&1 || return 1
    gsettings set org.gnome.system.proxy.http port "$port" >/dev/null 2>&1 || return 1
    gsettings set org.gnome.system.proxy.https host "$host" >/dev/null 2>&1 || return 1
    gsettings set org.gnome.system.proxy.https port "$port" >/dev/null 2>&1 || return 1
}

restore_gnome_proxy() {
    local mode="$1"
    local http_host="$2"
    local http_port="$3"
    local https_host="$4"
    local https_port="$5"

    if ! command -v gsettings >/dev/null 2>&1; then
        return 1
    fi

    local effective_mode="$mode"
    if [[ -z "$effective_mode" ]]; then
        effective_mode="none"
    fi

    gsettings set org.gnome.system.proxy.http host "$http_host" >/dev/null 2>&1 || return 1
    [[ "$http_port" =~ ^[0-9]+$ ]] || return 1
    gsettings set org.gnome.system.proxy.http port "$http_port" >/dev/null 2>&1 || return 1
    gsettings set org.gnome.system.proxy.https host "$https_host" >/dev/null 2>&1 || return 1
    [[ "$https_port" =~ ^[0-9]+$ ]] || return 1
    gsettings set org.gnome.system.proxy.https port "$https_port" >/dev/null 2>&1 || return 1

    if ! gsettings set org.gnome.system.proxy mode "$effective_mode" >/dev/null 2>&1; then
        return 1
    fi

    return 0
}

PROGRAM_MODE=false
LISTEN_HOST="127.0.0.1"
LISTEN_PORT="18080"
TARGET_DIR="$(pwd)"
FORCE_RECOVER=false

MITM_PID=""
TMP_ENV_FILE=""
PROXY_APPLIED=false
LOCK_DIR=""

release_lock() {
    if [[ -n "$LOCK_DIR" && -d "$LOCK_DIR" ]]; then
        rmdir "$LOCK_DIR" 2>/dev/null || true
        LOCK_DIR=""
    fi
}

acquire_lock_or_exit() {
    if command -v flock >/dev/null 2>&1; then
        exec 9>"$LOCK_FILE"
        if ! flock -n 9; then
            err "Another capture operation is running. Please retry."
            exit 1
        fi
        return
    fi

    LOCK_DIR="${LOCK_FILE}.d"
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        return
    fi

    err "Another capture operation is running. Please retry."
    exit 1
}

cleanup_on_error() {
    local exit_code="$?"

    release_lock

    if [[ "$exit_code" -eq 0 ]]; then
        return 0
    fi

    if [[ -n "$TMP_ENV_FILE" ]]; then
        rm -f "$TMP_ENV_FILE" 2>/dev/null || true
    fi

    if [[ -n "$MITM_PID" ]] && kill -0 "$MITM_PID" 2>/dev/null; then
        kill -TERM "$MITM_PID" 2>/dev/null || true
        sleep 0.2
        kill -KILL "$MITM_PID" 2>/dev/null || true
    fi

    if [[ "$PROXY_APPLIED" == "true" && "$PROGRAM_MODE" != "true" ]]; then
        restore_gnome_proxy \
            "$PREV_PROXY_MODE" \
            "$PREV_PROXY_HTTP_HOST" \
            "$PREV_PROXY_HTTP_PORT" \
            "$PREV_PROXY_HTTPS_HOST" \
            "$PREV_PROXY_HTTPS_PORT" >/dev/null 2>&1 || true
    fi
}

trap cleanup_on_error EXIT

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--program)
            PROGRAM_MODE=true
            shift
            ;;
        -H|--host)
            require_value_arg "$1" "${2:-}"
            LISTEN_HOST="${2:-}"
            shift 2
            ;;
        -P|--port)
            require_value_arg "$1" "${2:-}"
            LISTEN_PORT="${2:-}"
            shift 2
            ;;
        -d|--dir)
            require_value_arg "$1" "${2:-}"
            TARGET_DIR="${2:-}"
            shift 2
            ;;
        --force-recover)
            FORCE_RECOVER=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            err "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [[ -z "$LISTEN_HOST" ]]; then
    err "Listen host cannot be empty"
    exit 1
fi

if ! [[ "$LISTEN_PORT" =~ ^[0-9]+$ ]] || (( LISTEN_PORT < 1 || LISTEN_PORT > 65535 )); then
    err "Invalid port: $LISTEN_PORT"
    exit 1
fi

if [[ ! -d "$TARGET_DIR" ]]; then
    err "Target directory does not exist: $TARGET_DIR"
    exit 1
fi

require_cmd mitmdump

if port_in_use "$LISTEN_PORT"; then
    err "Port is already in use: $LISTEN_PORT"
    exit 1
fi

CAPTURES_DIR="$TARGET_DIR/captures"
ENV_FILE="$CAPTURES_DIR/proxy_info.env"
LOCK_FILE="$CAPTURES_DIR/.capture.lock"

mkdir -p "$CAPTURES_DIR"
acquire_lock_or_exit

if [[ -f "$ENV_FILE" ]]; then
    ACTIVE_PID="$(read_kv "MITM_PID" "$ENV_FILE")"
    if [[ "$ACTIVE_PID" =~ ^[0-9]+$ ]] && kill -0 "$ACTIVE_PID" 2>/dev/null; then
        err "Capture already running (PID: $ACTIVE_PID). Stop it first."
        exit 1
    fi
    if [[ "$FORCE_RECOVER" == "true" ]]; then
        warn "Removing stale state file: $ENV_FILE"
        rm -f "$ENV_FILE"
    else
        warn "Found stale state file: $ENV_FILE"
        warn "Use --force-recover to clean it automatically"
        exit 1
    fi
fi

RUN_ID="$(date +%Y%m%d_%H%M%S)_$$"
FLOW_FILE="$CAPTURES_DIR/capture_${RUN_ID}.flow"
HAR_FILE="$CAPTURES_DIR/capture_${RUN_ID}.har"
LOG_FILE="$CAPTURES_DIR/capture_${RUN_ID}.log"
MANIFEST_FILE="$CAPTURES_DIR/capture_${RUN_ID}.manifest.json"
INDEX_FILE="$CAPTURES_DIR/capture_${RUN_ID}.index.ndjson"
SUMMARY_FILE="$CAPTURES_DIR/capture_${RUN_ID}.summary.md"
AI_JSON_FILE="$CAPTURES_DIR/capture_${RUN_ID}.ai.json"
AI_MD_FILE="$CAPTURES_DIR/capture_${RUN_ID}.ai.md"

PREV_PROXY_MODE=""
PREV_PROXY_HTTP_HOST=""
PREV_PROXY_HTTP_PORT=""
PREV_PROXY_HTTPS_HOST=""
PREV_PROXY_HTTPS_PORT=""

if [[ "$PROGRAM_MODE" != "true" ]]; then
    if command -v gsettings >/dev/null 2>&1; then
        PREV_PROXY_MODE="$(proxy_get org.gnome.system.proxy mode)"
        PREV_PROXY_HTTP_HOST="$(proxy_get org.gnome.system.proxy.http host)"
        PREV_PROXY_HTTP_PORT="$(proxy_get org.gnome.system.proxy.http port)"
        PREV_PROXY_HTTPS_HOST="$(proxy_get org.gnome.system.proxy.https host)"
        PREV_PROXY_HTTPS_PORT="$(proxy_get org.gnome.system.proxy.https port)"
    else
        warn "gsettings not found, cannot manage GNOME system proxy"
    fi
fi

mitmdump -q --listen-host "$LISTEN_HOST" --listen-port "$LISTEN_PORT" \
    --set block_global=false --set flow_detail=0 \
    -w "$FLOW_FILE" >"$LOG_FILE" 2>&1 9>&- &
MITM_PID=$!

sleep 0.5
if ! kill -0 "$MITM_PID" 2>/dev/null; then
    err "Failed to start mitmdump"
    [[ -s "$LOG_FILE" ]] && tail -n 20 "$LOG_FILE" >&2
    exit 1
fi

for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
    if ! kill -0 "$MITM_PID" 2>/dev/null; then
        err "mitmdump exited during startup"
        [[ -s "$LOG_FILE" ]] && tail -n 20 "$LOG_FILE" >&2
        exit 1
    fi
    sleep 0.2
done

if [[ "$PROGRAM_MODE" != "true" ]] && command -v gsettings >/dev/null 2>&1; then
    if ! set_gnome_proxy_manual "$LISTEN_HOST" "$LISTEN_PORT"; then
        warn "Failed to update GNOME proxy settings"
    else
        PROXY_APPLIED=true
    fi
fi

TMP_ENV_FILE="$ENV_FILE.tmp.$$"
cat >"$TMP_ENV_FILE" <<EOF
MITM_PID=$MITM_PID
PROGRAM_MODE=$PROGRAM_MODE
TARGET_DIR=$TARGET_DIR
CAPTURES_DIR=$CAPTURES_DIR
RUN_ID=$RUN_ID
FLOW_FILE=$FLOW_FILE
HAR_FILE=$HAR_FILE
LOG_FILE=$LOG_FILE
MANIFEST_FILE=$MANIFEST_FILE
INDEX_FILE=$INDEX_FILE
SUMMARY_FILE=$SUMMARY_FILE
AI_JSON_FILE=$AI_JSON_FILE
AI_MD_FILE=$AI_MD_FILE
LISTEN_HOST=$LISTEN_HOST
LISTEN_PORT=$LISTEN_PORT
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PREV_PROXY_MODE=$PREV_PROXY_MODE
PREV_PROXY_HTTP_HOST=$PREV_PROXY_HTTP_HOST
PREV_PROXY_HTTP_PORT=$PREV_PROXY_HTTP_PORT
PREV_PROXY_HTTPS_HOST=$PREV_PROXY_HTTPS_HOST
PREV_PROXY_HTTPS_PORT=$PREV_PROXY_HTTPS_PORT
EOF
chmod 600 "$TMP_ENV_FILE"
mv "$TMP_ENV_FILE" "$ENV_FILE"
TMP_ENV_FILE=""

FLOW_SHA256=""
if command -v sha256sum >/dev/null 2>&1; then
    FLOW_SHA256="$(sha256sum "$FLOW_FILE" 2>/dev/null | awk '{print $1}')"
fi

cat >"$MANIFEST_FILE" <<EOF
{
  "schemaVersion": "1",
  "runId": "${RUN_ID}",
  "targetDir": "${TARGET_DIR}",
  "capturesDir": "${CAPTURES_DIR}",
  "startedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "programMode": ${PROGRAM_MODE},
  "listen": {
    "host": "${LISTEN_HOST}",
    "port": ${LISTEN_PORT}
  },
  "process": {
    "pid": ${MITM_PID},
    "launcher": "mitmdump"
  },
  "files": {
    "flow": "${FLOW_FILE}",
    "har": "${HAR_FILE}",
    "log": "${LOG_FILE}",
    "index": "${INDEX_FILE}",
    "summary": "${SUMMARY_FILE}",
    "aiJson": "${AI_JSON_FILE}",
    "aiMd": "${AI_MD_FILE}",
    "stateEnv": "${ENV_FILE}",
    "flowSha256AtStart": "${FLOW_SHA256}"
  },
  "rawDataPolicy": {
    "immutable": true,
    "description": "Raw capture files are not modified by analysis artifacts"
  }
}
EOF

echo "================================================"
echo " mitmproxy capture started"
echo "================================================"
echo " PID:          $MITM_PID"
echo " Listen:       $LISTEN_HOST:$LISTEN_PORT"
echo " Flow file:    $FLOW_FILE"
echo " HAR file:     $HAR_FILE"
echo " Log file:     $LOG_FILE"
echo " Manifest:     $MANIFEST_FILE"
if [[ "$PROGRAM_MODE" == "true" ]]; then
    echo " Proxy mode:   program (system proxy unchanged)"
else
    if [[ "$PROXY_APPLIED" == "true" ]]; then
        echo " Proxy mode:   GNOME system proxy -> manual"
    else
        echo " Proxy mode:   unchanged (gsettings unavailable/failed)"
    fi
fi
echo ""
echo " To stop and export HAR:"
echo "   $(cd "$(dirname "$0")" && pwd)/stopCaptures.sh"
echo " Then ask AI directly:"
echo "   $(cd "$(dirname "$0")" && pwd)/ai.sh"
echo "================================================"

trap - EXIT
