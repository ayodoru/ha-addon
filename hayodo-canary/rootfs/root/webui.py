import logging
import os
import json
import re
from glob import glob
from datetime import datetime, timezone, timedelta

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from flask import Flask, render_template

template_dir = os.path.dirname(os.path.realpath(__file__))
app = Flask(__name__, template_folder=template_dir)


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
            })
    except Exception as e:
        logging.exception(e)

    merged_events = list(reversed(events)) + tunnel_events
    merged_events.sort(key=lambda event: event.get("ts") or "", reverse=True)
    return merged_events


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

    public_url = ""
    domain = status.get("synonym") or status.get("domain")
    if domain:
        public_url = f"https://{domain}"

    return {
        "state": state,
        "label": label,
        "public_url": public_url,
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

    return render_template(
        'ayodo.html',
        access=access,
        chart=chart,
        certs=certs,
        events=events[:40],
        status=status,
        theme=theme,
    )


# Home Assistant ingress starts on port 8099
if __name__ == "__main__":
    from waitress import serve

    serve(app, host="0.0.0.0", port=8099)
