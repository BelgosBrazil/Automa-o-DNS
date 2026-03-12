"""Módulo com a lógica de configuração DNS Hablla na GoDaddy."""

import requests

GODADDY_API_BASE = "https://api.godaddy.com"
DEFAULT_TTL = 3600


def parse_host_to_name(host: str, domain: str) -> str:
    """Converte o Host do Hablla para o formato 'name' da GoDaddy."""
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
    ote: bool = False,
) -> tuple[bool, str]:
    """
    Adiciona registros DNS na GoDaddy via API.
    Retorna (sucesso, mensagem).
    """
    base = "https://api.ote-godaddy.com" if ote else GODADDY_API_BASE
    url = f"{base}/v1/domains/{domain}/records"
    headers = {
        "Authorization": f"sso-key {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    payload = []
    for r in records:
        rec = {
            "type": str(r.get("type", "CNAME")).upper(),
            "name": r["name"],
            "data": str(r["data"]).rstrip("."),
            "ttl": max(600, int(r.get("ttl", DEFAULT_TTL))),
        }
        payload.append(rec)

    try:
        resp = requests.patch(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            return True, "OK"
        return False, f"GoDaddy API: {resp.status_code} - {resp.text[:200]}"
    except requests.RequestException as e:
        return False, str(e)


def build_records_payload(domain: str, cname_records: list[dict]) -> list[dict]:
    """Constrói o payload de registros para um domínio."""
    payload = []
    for r in cname_records:
        host = r.get("host", r.get("name", ""))
        data_val = r.get("data", r.get("value", ""))
        name = parse_host_to_name(host, domain)
        payload.append({
            "type": r.get("type", "CNAME"),
            "name": name,
            "data": data_val,
            "ttl": r.get("ttl", DEFAULT_TTL),
        })
    return payload


def parse_domains_from_text(text: str) -> list[str]:
    """Extrai lista de domínios de um texto (um por linha, ignora vazios e comentários)."""
    domains = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            domains.append(line.split(",")[0].strip())
        else:
            domains.append(line)
    return [d for d in domains if d]
