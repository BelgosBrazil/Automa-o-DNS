"""
Integração com a API Hablla para obter registros CNAME de autenticação de email.

A API Hablla pode ou não expor os registros DNS diretamente.
Tentamos múltiplos endpoints e formatos de resposta.
"""

import re
import requests

HABLLA_API_BASE = "https://api.hablla.com"


def _extract_cname_records(obj, found: list, path: str = ""):
    """
    Recursivamente busca estruturas que parecem registros CNAME em qualquer JSON.
    Aceita: {host, data}, {host, value}, {name, data}, {name, value}, etc.
    """
    if isinstance(obj, list):
        for i, item in enumerate(obj):
            _extract_cname_records(item, found, f"{path}[{i}]")
        return

    if isinstance(obj, dict):
        host = (
            obj.get("host")
            or obj.get("name")
            or obj.get("subdomain")
            or obj.get("hostname")
        )
        data = (
            obj.get("data")
            or obj.get("value")
            or obj.get("target")
            or obj.get("destination")
        )
        if host and data and isinstance(host, str) and isinstance(data, str):
            h, d = str(host).strip(), str(data).strip()
            if h and d and "." in d and len(d) > 4:
                found.append({"host": h, "data": d})
        for k, v in obj.items():
            _extract_cname_records(v, found, f"{path}.{k}")


def extract_workspace_id(value: str) -> str:
    """Extrai workspace_id de URL ou ID puro. Ex: studio.hablla.com/workspace/abc123/ -> abc123"""
    s = (value or "").strip()
    m = re.search(r"workspace[/\-_]?([a-zA-Z0-9]+)", s)
    if m:
        return m.group(1)
    return s.split("/")[-1].split("?")[0] if s else ""


def fetch_cname_from_hablla(token: str, workspace_id: str) -> tuple[list[dict], list[str]]:
    """
    Tenta obter registros CNAME da API Hablla.
    Retorna (lista de {host, data}, lista de mensagens/logs).
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    logs = []
    all_records = []

    def _get(url: str) -> dict | None:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                return r.json()
            logs.append(f"GET {url}: {r.status_code}")
            return None
        except Exception as e:
            logs.append(f"Erro ao acessar {url}: {e}")
            return None

    base = f"{HABLLA_API_BASE}/v1/workspaces/{workspace_id}"

    conns = _get(f"{base}/connections")
    if conns:
        items = conns if isinstance(conns, list) else conns.get("data", conns.get("connections", []))
        if not isinstance(items, list):
            items = [items] if items else []
        for c in items:
            cid = c.get("id") if isinstance(c, dict) else None
            if cid:
                detail = _get(f"{base}/connections/{cid}")
                if detail:
                    _extract_cname_records(detail, all_records)
        if isinstance(conns, dict):
            _extract_cname_records(conns, all_records)

    doms = _get(f"{base}/domains")
    if doms:
        _extract_cname_records(doms, all_records)

    seen = set()
    unique = []
    for r in all_records:
        key = (r["host"], r["data"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique, logs


def parse_cname_from_text(text: str) -> list[dict]:
    """
    Extrai registros CNAME de texto colado ou CSV.
    Formatos aceitos:
    - Formato multi-linha Hablla (Tipo/host/data em linhas separadas)
    - host,data ou host;data por linha
    - host  data (tab ou espaços)
    - Tabela com colunas Tipo, Host, Data
    """
    records = []
    lines = text.strip().splitlines()

    def _is_header(line: str) -> bool:
        if re.match(r"^(Tipo|Host|Data|Válido)\s", line, re.I):
            return True
        if re.match(r"^Tipo\s+Host\s+Data", line, re.I):
            return True
        if "Chaves de configuração" in line or "Estas são as chaves" in line:
            return True
        return False

    def _looks_like_host(s: str) -> bool:
        return bool(s and ("." in s or "_" in s) and len(s) > 2)

    def _looks_like_data(s: str) -> bool:
        return bool(s and "." in s and len(s) > 4 and not s.lower().startswith("v=dmarc"))

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or line.startswith("#"):
            continue
        if _is_header(line):
            continue

        # Formato multi-linha: CNAME na própria linha, host e data nas próximas (com possíveis linhas em branco)
        if line.upper() == "CNAME":
            # Buscar próxima linha que parece host
            j = i
            host = ""
            while j < len(lines):
                cand = lines[j].strip()
                if _looks_like_host(cand):
                    host = cand
                    j += 1
                    break
                if cand and cand.upper() in ("TXT", "CNAME"):
                    break
                j += 1
            # Buscar próxima linha que parece data
            data = ""
            while j < len(lines):
                cand = lines[j].strip()
                if _looks_like_data(cand):
                    data = cand
                    j += 1
                    break
                if cand and cand.upper() in ("TXT", "CNAME"):
                    break
                j += 1
            if host and data:
                records.append({"host": host, "data": data})
            if j < len(lines) and lines[j].strip().lower() in ("não", "nao", "sim"):
                j += 1
            i = j
            continue

        # Pular registro TXT (TXT, host, data, valid)
        if line.upper() == "TXT" and i + 2 <= len(lines):
            i += 3  # pular host, data e valid
            continue

        # Formato em linha única (tab, vírgula, etc.)
        parts = [p.strip() for p in re.split(r"[\t,;|]+", line) if p.strip()]
        if len(parts) >= 2:
            host = parts[0] if len(parts) == 2 else parts[1]
            data = parts[1] if len(parts) == 2 else parts[2]
            if host.lower() in ("host", "name", "type", "cname") or data.lower() in ("data", "value"):
                continue
            if parts[0].upper() == "CNAME" and len(parts) >= 3:
                host, data = parts[1], parts[2]
            if host and data and "." in data and _looks_like_data(data):
                records.append({"host": host, "data": data})
            continue

        m = re.search(r"CNAME\s+(\S+)\s+(\S+\.\S+)", line, re.I)
        if m:
            records.append({"host": m.group(1), "data": m.group(2)})

    return records
