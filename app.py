#!/usr/bin/env python3
"""Backend Flask para o frontend de configuração DNS Hablla/GoDaddy."""

import json
from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path

from dns_config import add_dns_records, build_records_payload, parse_domains_from_text
from hablla_api import fetch_cname_from_hablla, parse_cname_from_text, extract_workspace_id

app = Flask(__name__, static_folder="static", static_url_path="")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/configurar", methods=["POST"])
def configurar():
    """Recebe credenciais, domínios e registros CNAME e executa a configuração."""
    try:
        data = request.get_json() or {}
        api_key = (data.get("api_key") or "").strip()
        api_secret = (data.get("api_secret") or "").strip()
        domains_raw = data.get("domains", "")
        cname_records = data.get("cname_records", [])
        ote = data.get("ote", False)

        errors = []
        if not api_key:
            errors.append("API Key da GoDaddy é obrigatória")
        if not api_secret:
            errors.append("API Secret da GoDaddy é obrigatório")
        if not domains_raw and not data.get("domains_file"):
            errors.append("Informe os domínios (texto ou arquivo)")
        if not cname_records:
            errors.append("Adicione pelo menos um registro CNAME do Hablla")

        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        domains = parse_domains_from_text(domains_raw)

        if not domains and "domains_file" in data:
            domains = parse_domains_from_text(data["domains_file"])

        if not domains:
            return jsonify({
                "ok": False,
                "errors": ["Nenhum domínio válido encontrado. Use um domínio por linha."],
            }), 400

        valid_records = []
        for r in cname_records:
            if isinstance(r, dict) and r.get("host") and r.get("data"):
                valid_records.append({
                    "host": r["host"].strip(),
                    "data": r["data"].strip(),
                    "ttl": int(r.get("ttl", 3600)),
                })

        if not valid_records:
            return jsonify({
                "ok": False,
                "errors": ["Registros CNAME inválidos. Cada um precisa de Host e Data."],
            }), 400

        results = []
        for domain in domains:
            payload = build_records_payload(domain, valid_records)
            success, msg = add_dns_records(
                domain, payload, api_key, api_secret, ote=ote
            )
            results.append({
                "domain": domain,
                "success": success,
                "message": msg,
            })

        return jsonify({
            "ok": True,
            "results": results,
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "errors": [str(e)],
        }), 500


@app.route("/api/parse-domains", methods=["POST"])
def parse_domains():
    """Apenas faz o parse dos domínios para preview (sem configurar)."""
    try:
        data = request.get_json() or {}
        text = data.get("domains", "") or data.get("content", "")
        domains = parse_domains_from_text(text)
        return jsonify({"domains": domains, "count": len(domains)})
    except Exception as e:
        return jsonify({"domains": [], "count": 0, "error": str(e)})


@app.route("/api/hablla-fetch-cname", methods=["POST"])
def hablla_fetch_cname():
    """Busca registros CNAME da API Hablla."""
    try:
        data = request.get_json() or {}
        token = (data.get("token") or data.get("api_token") or "").strip()
        workspace = (data.get("workspace_id") or data.get("workspace") or "").strip()
        workspace_id = extract_workspace_id(workspace) or workspace

        if not token:
            return jsonify({"ok": False, "errors": ["Token da API Hablla é obrigatório"]}), 400
        if not workspace_id:
            return jsonify({"ok": False, "errors": ["Workspace ID é obrigatório (ou cole a URL do Studio)"]}), 400

        records, logs = fetch_cname_from_hablla(token, workspace_id)

        return jsonify({
            "ok": True,
            "records": records,
            "logs": logs,
        })
    except Exception as e:
        return jsonify({"ok": False, "errors": [str(e)]}), 500


@app.route("/api/parse-cname", methods=["POST"])
def parse_cname():
    """Extrai registros CNAME de texto colado ou CSV (host,data)."""
    try:
        data = request.get_json() or {}
        text = (data.get("text") or data.get("content") or data.get("cname_text") or "").strip()
        if not text:
            return jsonify({"ok": False, "errors": ["Cole o texto com os registros CNAME"]}), 400

        records = parse_cname_from_text(text)
        return jsonify({"ok": True, "records": records})
    except Exception as e:
        return jsonify({"ok": False, "errors": [str(e)]}), 500


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"Abra http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
