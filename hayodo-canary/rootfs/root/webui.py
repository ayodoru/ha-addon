import logging
import os
import json
import re
import threading
import time
from glob import glob
from datetime import datetime, timezone, timedelta

import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from flask import Flask, redirect, render_template

template_dir = os.path.dirname(os.path.realpath(__file__))
app = Flask(__name__, template_folder=template_dir)
HEALTHCHECK_FILE = "/data/healthchecks.jsonl"
HEALTHCHECK_CONFIG_FILE = "/data/healthcheck_config.json"
HEALTHCHECK_INTERVAL_SECONDS = 300
HEALTHCHECK_TIMEOUT_SECONDS = 8
HEALTHCHECK_PATHS = ["/manifest.json", "/static/icons/favicon.ico"]


# -----------------------------
# Certificate Parsing (correct)
# -----------------------------
def parse_cert_file(full_path):
    pem_data = open(full_path, "rb").read()
    cert = x509.load_pem_x509_certificate(pem_data, default_backend())

    start = cert.not_valid_before_utc
    end = cert.not_valid_after_utc
    days_left = (end - datetime.now(timezone.utc)).days

    domains = []
    common_name = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    if common_name:
        domains.append(common_name)

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        for dns_name in san.get_values_for_type(x509.DNSName):
            if dns_name not in domains:
                domains.append(dns_name)
    except x509.ExtensionNotFound:
        pass

    status = "ok"
    if days_left < 0:
        status = "expired"
    elif days_left < 14:
        status = "danger"
    elif days_left < 30:
        status = "warning"

    progress = max(0, min(100, round(days_left / 90 * 100)))

    return {
        "domain": common_name,
        "domains": domains,
        "domains_display": ", ".join(domains),
        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end": end.strftime("%Y-%m-%d %H:%M:%S"),
        "days": days_left,
        "status": status,
        "progress": progress,
        "path": full_path,
    }


def load_cert_info():
    results = []
    cert_paths = []
    seen = set()

    # Active cert copied for Home Assistant usage
    ssl_fullchain = "/ssl/fullchain.pem"
    if os.path.isfile(ssl_fullchain):
        cert_paths.append(ssl_fullchain)

    # Raw certs issued by dehydrated (covers cases with multiple cert dirs)
    cert_paths.extend(sorted(glob("/data/letsencrypt/certs/*/fullchain.pem")))

    for cert_path in cert_paths:
        if cert_path in seen:
            continue
        seen.add(cert_path)
        try:
            results.append(parse_cert_file(cert_path))
        except Exception as e:
            logging.exception(e)
            # todo: work with error
            pass

    return results


def default_theme():
    return {
        "primary": "#5dade2",
        "bg": "#1e1e1e",
        "bg2": "#2a2a2a",
        "text": "#ffffff",
        "card": "#2a2a2a",
    }


def load_access_status():
    default_status = {
        "state": "unknown",
        "domain": "",
        "synonym": "",
        "tunnel_host": "",
        "tunnel_port": "",
        "ssh_port": "",
        "local_host": "",
        "local_port": "",
        "updated_at": "",
    }

    status_path = "/data/ayodo_status.json"
    if not os.path.isfile(status_path):
        return default_status

    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        default_status.update({k: v for k, v in data.items() if v is not None})
    except Exception as e:
        logging.exception(e)

    return default_status


def format_event_time(raw_ts):
    if not raw_ts:
        return ""
    try:
        dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%d.%m %H:%M")
    except ValueError:
        return raw_ts


def event_date(raw_ts):
    if not raw_ts:
        return ""
    try:
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def parse_syslog_time(raw_line):
    match = re.match(r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d\d:\d\d:\d\d)\s+(.*)$", raw_line)
    if not match:
        return "", raw_line

    timestamp, message = match.groups()
    year = datetime.now().year
    try:
        dt = datetime.strptime(f"{year} {timestamp}", "%Y %b %d %H:%M:%S")
        return dt.astimezone().isoformat(timespec="seconds"), message
    except ValueError:
        return "", message


def classify_tunnel_line(line):
    lowered = line.lower()
    if any(token in lowered for token in ["exited", "timeout", "failed", "error", "disconnect", "connection reset"]):
        return "warning"
    if any(token in lowered for token in ["starting ssh", "restart", "restarting", "successful", "remote forward success"]):
        return "success"
    return "info"


def clean_tunnel_message(line):
    message = re.sub(r"^autossh\[\d+\]:\s*", "", line).strip()
    message = re.sub(r"^debug\d?:\s*", "", message).strip()
    return message


def load_tunnel_events(limit=30):
    events = []
    sources = [
        ("/data/autossh.log", "Auto SSH"),
        ("/data/ssh_tunnel.log", "SSH tunnel"),
    ]

    for path, source in sources:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-limit:]
        except Exception as e:
            logging.exception(e)
            continue

        for line in lines:
            raw = line.strip()
            if not raw:
                continue
            raw_ts, message = parse_syslog_time(raw)
            message = clean_tunnel_message(message)
            if not message:
                continue
            events.append({
                "type": "tunnel",
                "status": classify_tunnel_line(message),
                "message": f"{source}: {message}",
                "time": format_event_time(raw_ts) if raw_ts else "",
                "ts": raw_ts,
                "date": event_date(raw_ts),
            })

    events.sort(key=lambda event: event.get("ts") or "", reverse=True)
    return events[:limit]


def load_events(limit=80):
    events = []
    events_path = "/data/events.jsonl"

    if os.path.isfile(events_path):
        try:
            with open(events_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-limit:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                event["time"] = format_event_time(event.get("ts", ""))
                event["date"] = event_date(event.get("ts", ""))
                events.append(event)
        except Exception as e:
            logging.exception(e)

    tunnel_events = load_tunnel_events()

    if events:
        merged_events = list(reversed(events)) + tunnel_events
        merged_events.sort(key=lambda event: event.get("ts") or "", reverse=True)
        return merged_events

    # Backward-compatible fallback for existing installations before events.jsonl.
    log_path = "/data/last_run.log"
    if not os.path.isfile(log_path):
        return tunnel_events

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-25:]
        for line in lines:
            clean = line.strip().replace("Ⓐ", "").strip()
            if not clean:
                continue
            status = "info"
            lowered = clean.lower()
            if "error" in lowered or "failed" in lowered or "not valid" in lowered:
                status = "warning"
            elif "success" in lowered or "valid" in lowered or "deployed" in lowered:
                status = "success"
            events.append({
                "type": "legacy",
                "status": status,
                "message": clean,
                "time": "",
                "date": "",
            })
    except Exception as e:
        logging.exception(e)

    merged_events = list(reversed(events)) + tunnel_events
    merged_events.sort(key=lambda event: event.get("ts") or "", reverse=True)
    return merged_events


def parse_event_datetime(raw_ts):
    if not raw_ts:
        return None
    try:
        dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def cleanup_jsonl_events(cutoff):
    events_path = "/data/events.jsonl"
    if not os.path.isfile(events_path):
        return

    kept_lines = []
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logging.exception(e)
        return

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            kept_lines.append(line)
            continue

        event_dt = parse_event_datetime(event.get("ts", ""))
        if event_dt is None or event_dt >= cutoff:
            kept_lines.append(line)

    try:
        with open(events_path, "w", encoding="utf-8") as f:
            f.writelines(kept_lines)
    except Exception as e:
        logging.exception(e)


def cleanup_tunnel_log(path, cutoff):
    if not os.path.isfile(path):
        return

    kept_lines = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        logging.exception(e)
        return

    for line in lines:
        raw_ts, _message = parse_syslog_time(line.strip())
        event_dt = parse_event_datetime(raw_ts)
        if event_dt is None or event_dt >= cutoff:
            kept_lines.append(line)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(kept_lines)
    except Exception as e:
        logging.exception(e)


def cleanup_old_events(days=14):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cleanup_jsonl_events(cutoff)
    cleanup_tunnel_log("/data/autossh.log", cutoff)
    cleanup_tunnel_log("/data/ssh_tunnel.log", cutoff)


def healthcheck_base_url(status):
    domain = status.get("domain", "")
    if not domain:
        return ""
    return f"https://{domain}"


def healthcheck_urls(status):
    base_url = healthcheck_base_url(status)
    if not base_url:
        return []
    return [f"{base_url}{path}" for path in HEALTHCHECK_PATHS]


def load_healthcheck_config():
    config = {"enabled": True}
    if not os.path.isfile(HEALTHCHECK_CONFIG_FILE):
        return config

    try:
        with open(HEALTHCHECK_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        config["enabled"] = bool(data.get("enabled", True))
    except Exception as e:
        logging.exception(e)

    return config


def save_healthcheck_config(enabled):
    try:
        os.makedirs(os.path.dirname(HEALTHCHECK_CONFIG_FILE), exist_ok=True)
        with open(HEALTHCHECK_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"enabled": bool(enabled)}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.exception(e)


def append_healthcheck(entry):
    try:
        os.makedirs("/data", exist_ok=True)
        with open(HEALTHCHECK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.exception(e)


def trim_healthchecks(days=7, max_lines=1000):
    if not os.path.isfile(HEALTHCHECK_FILE):
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    kept_lines = []
    try:
        with open(HEALTHCHECK_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logging.exception(e)
        return

    for line in lines[-max_lines:]:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        item_dt = parse_event_datetime(item.get("ts", ""))
        if item_dt is None or item_dt >= cutoff:
            kept_lines.append(line)

    try:
        with open(HEALTHCHECK_FILE, "w", encoding="utf-8") as f:
            f.writelines(kept_lines)
    except Exception as e:
        logging.exception(e)


def run_healthcheck_once():
    status = load_access_status()
    urls = healthcheck_urls(status)
    if not urls:
        return

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain": status.get("domain", ""),
        "url": urls[0],
        "path": HEALTHCHECK_PATHS[0],
        "ok": False,
        "status_code": None,
        "elapsed_ms": None,
        "error": "",
    }

    for url, path in zip(urls, HEALTHCHECK_PATHS):
        started = time.monotonic()
        entry["url"] = url
        entry["path"] = path
        try:
            response = requests.get(url, timeout=HEALTHCHECK_TIMEOUT_SECONDS, allow_redirects=True)
            entry["elapsed_ms"] = round(response.elapsed.total_seconds() * 1000)
            entry["status_code"] = response.status_code
            entry["ok"] = response.status_code < 500
            entry["error"] = ""
        except requests.RequestException as e:
            entry["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            entry["status_code"] = None
            entry["ok"] = False
            entry["error"] = str(e)[:180]

        if entry["ok"]:
            break

    append_healthcheck(entry)
    trim_healthchecks()


def healthcheck_worker():
    time.sleep(20)
    while True:
        try:
            if load_healthcheck_config().get("enabled", True):
                run_healthcheck_once()
        except Exception as e:
            logging.exception(e)
        time.sleep(HEALTHCHECK_INTERVAL_SECONDS)


def start_healthcheck_worker():
    worker = threading.Thread(target=healthcheck_worker, daemon=True)
    worker.start()


def load_healthchecks(limit=48):
    if not os.path.isfile(HEALTHCHECK_FILE):
        return []

    checks = []
    try:
        with open(HEALTHCHECK_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    except Exception as e:
        logging.exception(e)
        return []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        item["time"] = format_event_time(item.get("ts", ""))
        checks.append(item)

    return checks


def build_health_summary(checks, status):
    config = load_healthcheck_config()
    latest = checks[-1] if checks else None
    successful = [item for item in checks if item.get("ok")]
    latencies = [item.get("elapsed_ms") for item in successful if item.get("elapsed_ms") is not None]
    max_latency = max(latencies + [1])
    availability = round(len(successful) / len(checks) * 100) if checks else None

    points = []
    chart_width = 640
    chart_height = 180
    padding_x = 34
    padding_y = 18
    plot_width = chart_width - padding_x * 2
    plot_height = chart_height - padding_y * 2
    point_count = max(len(checks) - 1, 1)

    for index, item in enumerate(checks):
        elapsed = item.get("elapsed_ms")
        height = max(8, round((elapsed or 0) / max_latency * 82)) if item.get("ok") and elapsed is not None else 8
        x = padding_x + round(index / point_count * plot_width)
        y = chart_height - padding_y
        if item.get("ok") and elapsed is not None:
            y = padding_y + round((max_latency - elapsed) / max_latency * plot_height)
        points.append({
            "ok": item.get("ok", False),
            "height": height,
            "label": format_event_time(item.get("ts", "")),
            "elapsed_ms": elapsed,
            "status_code": item.get("status_code"),
            "error": item.get("error", ""),
            "x": x,
            "y": y,
        })

    line_points = " ".join(f"{point['x']},{point['y']}" for point in points if point["ok"] and point["elapsed_ms"] is not None)
    grid_lines = []
    y_labels = []
    for step in range(0, 4):
        value = round(max_latency / 3 * step)
        y = chart_height - padding_y - round(plot_height / 3 * step)
        grid_lines.append({"y": y})
        y_labels.append({"y": y + 4, "value": value})

    return {
        "enabled": config.get("enabled", True),
        "url": healthcheck_base_url(status),
        "path": latest.get("path", HEALTHCHECK_PATHS[0]) if latest else HEALTHCHECK_PATHS[0],
        "latest": latest,
        "points": points,
        "line_points": line_points,
        "grid_lines": grid_lines,
        "y_labels": y_labels,
        "chart_width": chart_width,
        "chart_height": chart_height,
        "axis_y": chart_height - padding_y,
        "axis_x": padding_x,
        "availability": availability,
        "avg_ms": round(sum(latencies) / len(latencies)) if latencies else None,
    }


def build_event_chart(events):
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    buckets = {day: {"date": day, "total": 0, "success": 0, "warning": 0, "error": 0} for day in days}

    for event in events:
        raw_ts = event.get("ts")
        if not raw_ts:
            continue
        try:
            day = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if day not in buckets:
            continue

        status = event.get("status", "info")
        buckets[day]["total"] += 1
        if status in buckets[day]:
            buckets[day][status] += 1

    max_total = max([item["total"] for item in buckets.values()] + [1])
    chart = []
    for day in days:
        item = buckets[day]
        item["height"] = max(6, round(item["total"] / max_total * 72)) if item["total"] else 4
        item["label"] = day.strftime("%d.%m")
        item["iso_date"] = day.isoformat()
        chart.append(item)
    return chart


def access_summary(status, events):
    access_events = [event for event in events if event.get("type") == "access"]
    last_success = next((event for event in access_events if event.get("status") == "success"), None)
    last_error = next((event for event in access_events if event.get("status") == "error"), None)

    state = status.get("state") or "unknown"
    if state == "connected":
        label = "Подключено"
    elif state == "error":
        label = "Ошибка"
    else:
        label = "Нет данных"

    primary_domain = status.get("domain", "")
    additional_domain = status.get("synonym", "")
    if additional_domain == primary_domain:
        additional_domain = ""
    local_host = status.get("local_host") or "homeassistant"
    local_port = status.get("local_port")
    local_address = f"{local_host}:{local_port}" if local_port else local_host

    return {
        "state": state,
        "label": label,
        "primary_url": f"https://{primary_domain}" if primary_domain else "",
        "additional_url": f"https://{additional_domain}" if additional_domain else "",
        "local_address": local_address,
        "local_url": f"https://{local_address}" if local_address else "",
        "last_success": last_success,
        "last_error": last_error,
    }


@app.route("/")
def index():
    certs = load_cert_info()
    theme = default_theme()
    status = load_access_status()
    events = load_events()
    chart = build_event_chart(events)
    access = access_summary(status, events)
    health = build_health_summary(load_healthchecks(), status)

    return render_template(
        'ayodo.html',
        access=access,
        chart=chart,
        certs=certs,
        events=events,
        health=health,
        status=status,
        theme=theme,
    )


@app.route("/cleanup-events", methods=["POST"])
def cleanup_events():
    cleanup_old_events(days=14)
    return redirect("./")


@app.route("/toggle-healthcheck", methods=["POST"])
def toggle_healthcheck():
    enabled = not load_healthcheck_config().get("enabled", True)
    save_healthcheck_config(enabled)
    return redirect("./")


# Home Assistant ingress starts on port 8099
if __name__ == "__main__":
    from waitress import serve

    start_healthcheck_worker()
    serve(app, host="0.0.0.0", port=8099)
