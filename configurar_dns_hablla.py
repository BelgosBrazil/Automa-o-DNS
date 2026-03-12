#!/usr/bin/env python3
"""
Script para automatizar a configuração dos registros DNS do Hablla na GoDaddy.

Os registros CNAME do Hablla são obtidos em:
Hablla Studio > Configurações > Conexões e Integrações > Email > [Sua conexão] > Configurar DNS

Referências:
- Hablla: https://docs.hablla.com/hablla-docs-en/hablla/settings/connections-and-integrations/email
- GoDaddy API: https://developer.godaddy.com/doc/endpoint/dns
"""

import json
import os
import sys
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("Instale o requests: pip install requests")
    sys.exit(1)


GODADDY_API_BASE = "https://api.godaddy.com"
DEFAULT_TTL = 3600


def get_api_credentials():
    """Obtém credenciais da API GoDaddy (variáveis de ambiente ou arquivo .env)."""
    key = os.environ.get("GODADDY_API_KEY") or os.environ.get("GODADDY_KEY")
    secret = os.environ.get("GODADDY_API_SECRET") or os.environ.get("GODADDY_SECRET")

    if not key or not secret:
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k.upper() in ("GODADDY_API_KEY", "GODADDY_KEY"):
                        key = v
                    elif k.upper() in ("GODADDY_API_SECRET", "GODADDY_SECRET"):
                        secret = v

    return key, secret


def parse_host_to_name(host: str, domain: str) -> str:
    """
    Converte o Host do Hablla para o formato 'name' da GoDaddy.

    Exemplos:
    - host="em1234", domain="meusite.com" -> "em1234"
    - host="em1234.meusite.com", domain="meusite.com" -> "em1234"
    - host="@", domain="meusite.com" -> "@"
    """
    host = host.strip().lower()
    domain = domain.strip().lower().lstrip(".")

    if host in ("@", "") or host == domain:
        return "@"

    if host.endswith("." + domain):
        return host[: -len(domain) - 1]

    return host


def add_dns_records(
    domain: str,
    records: list[dict],
    api_key: str,
    api_secret: str,
) -> bool:
    """
    Adiciona registros DNS na GoDaddy via API.

    records: lista de dicts com 'type', 'name', 'data', e opcionalmente 'ttl'
    """
    url = f"{GODADDY_API_BASE}/v1/domains/{domain}/records"
    headers = {
        "Authorization": f"sso-key {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    payload = []
    for r in records:
        rec = {
            "type": r["type"].upper(),
            "name": r["name"],
            "data": r["data"].rstrip("."),
            "ttl": int(r.get("ttl", DEFAULT_TTL)),
        }
        if rec["ttl"] < 600:
            rec["ttl"] = 600
        payload.append(rec)

    try:
        resp = requests.patch(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            return True
        print(f"Erro da API GoDaddy: {resp.status_code}")
        print(resp.text)
        return False
    except requests.RequestException as e:
        print(f"Erro de conexão: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Configura registros DNS do Hablla na GoDaddy"
    )
    parser.add_argument(
        "domain",
        help="Domínio na GoDaddy (ex: meusite.com.br)",
    )
    parser.add_argument(
        "--host",
        action="append",
        dest="hosts",
        help="Host do CNAME (pode repetir). Ex: em1234",
    )
    parser.add_argument(
        "--data",
        action="append",
        dest="datas",
        help="Valor/Destino do CNAME (pode repetir). Ex: 1234.example.sendgrid.net",
    )
    parser.add_argument(
        "--config",
        "-c",
        help="Arquivo JSON com registros. Ex: [{\"host\": \"em1234\", \"data\": \"...\"}]",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem alterar o DNS",
    )
    parser.add_argument(
        "--ote",
        action="store_true",
        help="Usar ambiente de teste da GoDaddy (OTE)",
    )
    args = parser.parse_args()

    global GODADDY_API_BASE
    if args.ote:
        GODADDY_API_BASE = "https://api.ote-godaddy.com"

    api_key, api_secret = get_api_credentials()
    if not args.dry_run and (not api_key or not api_secret):
        print(
            "Configure as credenciais da GoDaddy:\n"
            "  - Variáveis de ambiente: GODADDY_API_KEY e GODADDY_API_SECRET\n"
            "  - Ou arquivo .env neste diretório\n\n"
            "Obtenha em: https://developer.godaddy.com/keys/"
        )
        sys.exit(1)

    records = []

    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Arquivo não encontrado: {config_path}")
            sys.exit(1)
        data = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            records = data
        else:
            records = data.get("records", [data])

    if args.hosts and args.datas:
        if len(args.hosts) != len(args.datas):
            print("--host e --data devem ter a mesma quantidade de valores")
            sys.exit(1)
        for h, d in zip(args.hosts, args.datas):
            records.append({"host": h, "data": d})

    if not records:
        print(
            "Nenhum registro informado.\n\n"
            "Obtenha os valores no Hablla:\n"
            "  Studio > Configurações > Conexões e Integrações > Email > [Sua conexão] > Configurar DNS\n\n"
            "Exemplos de uso:\n"
            "  python configurar_dns_hablla.py meusite.com --host em1234 --data 1234.example.sendgrid.net\n"
            "  python configurar_dns_hablla.py meusite.com -c hablla-dns.json\n"
        )
        sys.exit(1)

    domain = args.domain
    payload = []
    for r in records:
        host = r.get("host", r.get("name", ""))
        data_val = r.get("data", r.get("value", ""))
        name = parse_host_to_name(host, domain)
        payload.append({
            "type": r.get("type", "CNAME"),
            "name": name,
            "data": data_val,
            "ttl": r.get("ttl", DEFAULT_TTL),
        })

    print(f"Domínio: {domain}")
    print("Registros a adicionar:")
    for p in payload:
        print(f"  CNAME  {p['name']}  ->  {p['data']}  (TTL: {p['ttl']})")

    if args.dry_run:
        print("\n[DRY-RUN] Nenhuma alteração realizada.")
        sys.exit(0)

    if add_dns_records(domain, payload, api_key, api_secret):
        print("\nRegistros adicionados com sucesso!")
        print("A propagação pode levar até algumas horas. Verifique em: https://www.whatsmydns.net/")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
