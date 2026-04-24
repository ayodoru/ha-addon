#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

EVENTS_FILE="/data/events.jsonl"
STATUS_FILE="/data/ayodo_status.json"

log_event() {
  local TYPE="${1:-system}"
  local STATUS="${2:-info}"
  local MESSAGE="${3:-}"
  local DOMAIN="${4:-}"

  EVENT_TYPE="${TYPE}" EVENT_STATUS="${STATUS}" EVENT_MESSAGE="${MESSAGE}" EVENT_DOMAIN="${DOMAIN}" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone

event = {
    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "type": os.environ.get("EVENT_TYPE", "system"),
    "status": os.environ.get("EVENT_STATUS", "info"),
    "message": os.environ.get("EVENT_MESSAGE", ""),
}
domain = os.environ.get("EVENT_DOMAIN", "")
if domain:
    event["domain"] = domain

os.makedirs("/data", exist_ok=True)
with open("/data/events.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(event, ensure_ascii=False) + "\n")
PY
}

save_access_status() {
  local DOMAIN="${1:-}"
  local SYNONYM="${2:-}"
  local TUNNEL_HOST="${3:-}"
  local TUNNEL_PORT="${4:-}"
  local SSH_PORT="${5:-}"
  local LOCAL_HOST="${6:-}"
  local LOCAL_PORT="${7:-}"
  local STATE="${8:-connected}"

  AYODO_DOMAIN="${DOMAIN}" AYODO_SYNONYM="${SYNONYM}" AYODO_TUNNEL_HOST="${TUNNEL_HOST}" \
  AYODO_TUNNEL_PORT="${TUNNEL_PORT}" AYODO_SSH_PORT="${SSH_PORT}" AYODO_LOCAL_HOST="${LOCAL_HOST}" \
  AYODO_LOCAL_PORT="${LOCAL_PORT}" AYODO_STATE="${STATE}" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone

status = {
    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "state": os.environ.get("AYODO_STATE", "connected"),
    "domain": os.environ.get("AYODO_DOMAIN", ""),
    "synonym": os.environ.get("AYODO_SYNONYM", ""),
    "tunnel_host": os.environ.get("AYODO_TUNNEL_HOST", ""),
    "tunnel_port": os.environ.get("AYODO_TUNNEL_PORT", ""),
    "ssh_port": os.environ.get("AYODO_SSH_PORT", ""),
    "local_host": os.environ.get("AYODO_LOCAL_HOST", ""),
    "local_port": os.environ.get("AYODO_LOCAL_PORT", ""),
}

os.makedirs("/data", exist_ok=True)
with open("/data/ayodo_status.json", "w", encoding="utf-8") as f:
    json.dump(status, f, ensure_ascii=False, indent=2)
PY
}
