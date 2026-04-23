import logging
import os
from glob import glob
from datetime import datetime, timezone

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

    return {
        "domain": common_name,
        "domains": domains,
        "domains_display": ", ".join(domains),
        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end": end.strftime("%Y-%m-%d %H:%M:%S"),
        "days": days_left
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


@app.route("/")
def index():
    certs = load_cert_info()
    theme = default_theme()
    log = ""
    if os.path.isfile("/data/last_run.log"):
        with open("/data/last_run.log", "r") as f:
            log = f.read()[-4000:]  # last 4000 chars

    return render_template('cert.html', log=log, certs=certs, theme=theme)


# Home Assistant ingress starts on port 8099
if __name__ == "__main__":
    from waitress import serve

    serve(app, host="0.0.0.0", port=8099)
