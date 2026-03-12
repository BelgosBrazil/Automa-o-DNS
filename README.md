# Automatizar DNS Hablla na GoDaddy

Script Python e **frontend web** para configurar os registros DNS do [Hablla](https://studio.hablla.com/workspace) nos domínios da [GoDaddy](https://www.godaddy.com) via API.

## Frontend Web

Para usar a interface visual:

```bash
pip install -r requirements.txt
python app.py
```

Acesse **http://127.0.0.1:5001** no navegador (ou outra porta se 5001 estiver em uso).

Para usar uma porta específica: `python app.py 8080`

### Carregar CNAME automaticamente

**Opção 1 — API Hablla:** Informe o Token e o Workspace ID (ou URL do Studio) e clique em "Buscar configurações do Hablla". Se a API expor os registros, eles serão carregados.

**Opção 2 — Importar:** Na tela "Configurar DNS" do Hablla (Email → [Sua conexão] → Configurar DNS), copie a tabela Host/Data e cole na área de importação. Ou envie um arquivo CSV no formato `host,data`. Você pode:
- Inserir API Key e Secret da GoDaddy
- Fazer upload de um arquivo (.txt ou .csv) com os domínios
- Ou colar os domínios diretamente (um por linha)
- Adicionar os registros CNAME do Hablla (Host e Data)

Use `dominios-exemplo.txt` como modelo para o arquivo de domínios.

---

## Script em linha de comando

## O que esse script faz?

O Hablla precisa de registros **CNAME** no seu domínio para autenticar o envio de e-mails. Em vez de adicionar esses registros manualmente no painel da GoDaddy, este script usa a [API da GoDaddy](https://developer.godaddy.com/doc/endpoint/dns) para fazer isso automaticamente.

## Passo a passo

### 1. Obter as credenciais da API GoDaddy

1. Acesse [developer.godaddy.com/keys](https://developer.godaddy.com/keys/)
2. Faça login na sua conta GoDaddy
3. Clique em **Create New API Key**
4. Dê um nome (ex: "Hablla DNS")
5. Copie a **Key** e o **Secret** — o Secret só aparece uma vez!

### 2. Obter os registros CNAME do Hablla

1. Acesse o [Hablla Studio](https://studio.hablla.com/workspace)
2. Clique em **Configurações** (ícone de engrenagem)
3. Vá em **Conexões e Integrações**
4. Clique em **+ Adicionar** no Email
5. Siga o fluxo até **Configurar DNS**
6. Anote os valores de **Host** e **Data** da tabela CNAME

Exemplo da tabela no Hablla:

| Type | Host        | Data                      |
|------|-------------|---------------------------|
| CNAME| em1234      | 1234.example.sendgrid.net |

### 3. Configurar as credenciais

**Opção A — Variáveis de ambiente**

```bash
export GODADDY_API_KEY="sua_key"
export GODADDY_API_SECRET="seu_secret"
```

**Opção B — Arquivo .env**

```bash
copy .env.exemplo .env
# Edite o .env e preencha GODADDY_API_KEY e GODADDY_API_SECRET
```

### 4. Instalar dependências

```bash
pip install -r requirements.txt
```

### 5. Executar o script

**Linha de comando (um registro):**

```bash
python configurar_dns_hablla.py meusite.com.br --host em1234 --data 1234.example.sendgrid.net
```

**Linha de comando (vários registros):**

```bash
python configurar_dns_hablla.py meusite.com.br --host em1234 --data 1234.example.sendgrid.net --host url5678 --data 5678.example.sendgrid.net
```

**Arquivo JSON (recomendado para vários domínios):**

Edite `hablla-dns-exemplo.json` com seus registros:

```json
[
  {"host": "em1234", "data": "1234.example.sendgrid.net"},
  {"host": "url5678", "data": "5678.example.sendgrid.net"}
]
```

Depois execute:

```bash
python configurar_dns_hablla.py meusite.com.br -c hablla-dns-exemplo.json
```

**Simular sem alterar (dry-run):**

```bash
python configurar_dns_hablla.py meusite.com.br -c hablla-dns-exemplo.json --dry-run
```

## Múltiplos domínios

Para configurar vários domínios da GoDaddy com os mesmos registros Hablla:

```bash
for dominio in site1.com site2.com site3.com; do
  python configurar_dns_hablla.py $dominio -c hablla-dns-exemplo.json
done
```

No PowerShell (Windows):

```powershell
"site1.com", "site2.com" | ForEach-Object {
  python configurar_dns_hablla.py $_ -c hablla-dns-exemplo.json
}
```

## Verificar propagação

Após executar o script, a propagação DNS pode levar até 24–48 horas. Verifique em:

- [WhatsMyDNS](https://www.whatsmydns.net/#CNAME/)

## Referências

- [Documentação Hablla - Email e DNS](https://docs.hablla.com/hablla-docs-en/hablla/settings/connections-and-integrations/email)
- [API DNS GoDaddy](https://developer.godaddy.com/doc/endpoint/dns)
