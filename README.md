# POS Sales Voice Agent

A voice assistant for a restaurant POS. The user asks *"What are today's sales?"* or *"Product sale report for BTM from 1 to 10 September"*; the agent speaks the answer and shows KPI cards, a chart and a table.

The project has **three independently deployable parts**:

```
frontend/      React UI (mic, chat, charts)                          :5173
   │  /api/chat, /api/stt
   ▼
backend/       Voice agent API (FastAPI)                             :8000
   │           Groq Whisper (speech -> text), Groq gpt-oss-120b (LLM)
   │           NO database access
   │  MCP over HTTP + "Authorization: Bearer <MCP_AUTH_TOKEN>"
   ▼
mcp-server/    Sales MCP server                                      :8001/mcp
   │           13 read-only sales tools + the POS report procedures
   ▼
MSSQL          BOPOS_NAMASTE (read-only login recommended)
```

| Part | Talks to | Secrets it holds |
|---|---|---|
| `frontend/` | backend | none |
| `backend/` | Groq, MCP server | `LLM_API_KEY`, `MCP_AUTH_TOKEN` |
| `mcp-server/` | SQL Server | `DB_PASSWORD`, `MCP_AUTH_TOKEN` |

The LLM never touches the database. Only the MCP server has database credentials, and it only runs fixed, parameterized, read-only queries and a whitelist of read-only report procedures.

---

## 1. Prerequisites (Windows)

| Requirement | Needed by |
|---|---|
| Python 3.11+ | backend, mcp-server |
| Node.js 18+ | frontend |
| ODBC Driver 17 or 18 for SQL Server | mcp-server only |
| Groq API key (https://console.groq.com/keys) | backend only |

## 2. Local development

1. Run `setup.bat` once (creates `mcp-server\venv`, `backend\venv`, installs npm packages and creates both `.env` files).
2. Fill in:
   - `mcp-server\.env`: `DB_SERVER`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD`, `MCP_AUTH_TOKEN`
   - `backend\.env`: `LLM_API_KEY`, `MCP_SERVER_URL`, and the **same** `MCP_AUTH_TOKEN`
3. Run `start-all.bat` (three windows: MCP server, API, UI) and open http://localhost:5173.

Generate a token with:
```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 3. Deploying the parts separately

### mcp-server (on a machine that can reach SQL Server)
```bat
cd mcp-server
setup.bat
:: edit .env, then:
start.bat
```
- `MCP_HOST=0.0.0.0` to accept connections from the backend machine; keep `MCP_AUTH_TOKEN` set.
- Behind a domain / reverse proxy, set `MCP_ALLOWED_HOSTS=mcp.yourdomain.com` and serve it over HTTPS.
- Health check (no token needed): `GET http://<host>:8001/health`, with database check: `/health?db=1`.
- Use the read-only login from `mcp-server/database/05_bopos_readonly_login.sql`, not `sa`.

### backend (anywhere that can reach Groq and the MCP server)
```bat
cd backend
setup.bat
:: edit .env: LLM_API_KEY, MCP_SERVER_URL=https://mcp.yourdomain.com/mcp, MCP_AUTH_TOKEN
start.bat
```
- No ODBC driver or database access needed.
- `GET /api/health` shows whether the backend can reach the MCP server (and through it, the database).

### frontend
```bat
cd frontend
npm install
npm run build
```
Serve `frontend/dist` with any web server and route `/api` to the backend (or set `VITE_API_BASE` at build time). Add the frontend URL to `CORS_ORIGINS` in `backend\.env`.

### Settings that must match on both sides
| Setting | mcp-server/.env | backend/.env |
|---|---|---|
| `MCP_AUTH_TOKEN` | the secret | the same secret |
| `BUSINESS_DAY_START_HOUR` | 5 | 5 |
| `TIMEZONE` | Asia/Kolkata | Asia/Kolkata |

## 4. Testing step by step

| Step | Where | Command | What it checks |
|---|---|---|---|
| A | mcp-server | `python -m app.check_tools` | DB connection + all tools, without the LLM |
| B | mcp-server | `python -m app.verify_bopos` | Agent numbers vs the POS report procedures |
| C | browser | http://localhost:8001/health?db=1 | MCP server + DB |
| D | browser | http://localhost:8000/api/health | backend → MCP server → DB |
| E | backend | `python -m app.cli` | Text chat with the agent (LLM + tools), no voice |
| F | browser | http://localhost:5173 | Full UI |

## 5. What the agent can answer (MCP tools)

| Tool | Example questions |
|---|---|
| `get_sales_summary` | What are today's sales? How many bills this month? |
| `get_daily_sales` | Date-wise sales for September |
| `get_item_sales_by_date` | Date-wise product sales; daily sales of Masala Dosa |
| `get_top_items` | Top 5 items this week; least selling items |
| `get_category_sales` | Item-group-wise sales |
| `get_payment_mode_sales` | Cash vs online today |
| `get_order_type_sales` | How much came from Zomato and Swiggy? |
| `get_hourly_sales` | What is the peak hour? |
| `compare_sales` | Today vs yesterday; this month vs last month |
| `get_void_and_discount_report` | Voided / cancelled bills, discounts |
| `get_data_availability` | Up to which date data exists |
| `run_pos_report` | The POS's own report procedures: product sales, GST/daily sales with tax, billing, settlement, settlement variance, cash declarations, hourly orders, discarded bills/orders/items, KOT cancel, orders |
| `list_outlets` | Maps an outlet name to its id |
| `search_help` / `list_help_topics` | How do I add a new item? The printer is not printing the KOT. (answers only from `mcp-server/knowledge/`) |

### Help library (how-to and troubleshooting)
The assistant answers questions about using the POS software only from Markdown articles in
`mcp-server/knowledge/`. It never invents menu names or steps; if no article matches, it says so and
gives `SUPPORT_CONTACT` (backend `.env`). Add or edit a `.md` file and it is used from the next question,
with no restart and no Azure deployment. See `mcp-server/knowledge/README.md` and the templates in `_examples/`.

## 6. Folder structure

```
voice agent/
├── mcp-server/                 Sales MCP server (deploy next to the database)
│   ├── app/
│   │   ├── mcp_server.py       tools + HTTP app (/mcp, /health, bearer auth)
│   │   ├── pos_reports.py      whitelisted POS report procedures (run_pos_report)
│   │   ├── sources.py          how each report maps to BOPOS tables
│   │   ├── db.py               MSSQL (pyodbc), driver auto-detection
│   │   ├── config.py           mcp-server/.env settings
│   │   ├── check_tools.py      run all tools without the LLM
│   │   ├── verify_bopos.py     compare with POS report procedures
│   │   ├── inspect_db.py       schema report (needs sa)
│   │   ├── diag_items.py       product report reconciliation
│   │   └── capture_pos_queries.py  see what SQL the POS app runs (needs sa)
│   ├── database/               SQL scripts (demo DB, read-only logins)
│   ├── requirements.txt, setup.bat, start.bat, .env.example
├── backend/                    Voice agent API (no DB access)
│   ├── app/
│   │   ├── agent.py            Groq LLM + MCP client loop (sends the bearer token)
│   │   ├── main.py             FastAPI: /api/chat, /api/stt, /api/outlets, /api/health
│   │   ├── dates.py            today/yesterday/this month -> business dates
│   │   ├── config.py           backend/.env settings
│   │   └── cli.py              terminal text chat
│   ├── requirements.txt, setup.bat, start.bat, .env.example
├── frontend/                   React (Vite) UI
├── setup.bat                   local dev: set up all three
└── start-all.bat               local dev: start all three
```

## 7. Logs and monitoring

### What gets logged
| Where | Event | Fields |
|---|---|---|
| backend | every HTTP request | method, path, status, duration_ms, request_id (also returned as `X-Request-ID` header) |
| backend | every question (`event=chat`) | question, outlet, tools used (ok/failed, ms), LLM rounds, prompt/completion/total tokens, duration_ms |
| backend | speech-to-text (`event=stt`) | audio size, transcript, duration_ms |
| backend | errors (`chat_error`, `stt_error`) | full exception, readable reason (MCP down, wrong token, ...) |
| mcp-server | every tool call (`tool_call` / `tool_error`) | tool, arguments, duration_ms, error |
| mcp-server | slow database queries | SQL (first 160 chars), duration_ms, rows (threshold `SLOW_QUERY_MS`) |
| mcp-server | requests with a wrong/missing token (`auth_rejected`) | client IP (or X-Forwarded-For through the tunnel) |

Levels: normal requests are INFO; failed tools, 4xx, slow requests (`SLOW_REQUEST_MS`) and rejected tokens are WARNING; 5xx and exceptions are ERROR.

### Where to read them
- **mcp-server (local machine):** `mcp-server\logs\mcp-server.log`, rotating, 10 files x 10 MB.
- **backend running locally:** `backend\logs\backend.log` when `LOG_FILE` is set.
- **backend on Azure Functions:** Function App → *Log stream* for live logs, and *Application Insights → Logs* for history.
  Leave `LOG_FILE` empty there (Function storage is not a log store). Example query:
  ```kusto
  traces
  | where message startswith "chat answered" or severityLevel >= 2
  | project timestamp, severityLevel, message
  | order by timestamp desc
  ```

### Settings
| Setting | backend/.env | mcp-server/.env |
|---|---|---|
| `LOG_LEVEL` | INFO (DEBUG = also every MCP/LLM step) | INFO (DEBUG = also every SQL query) |
| `LOG_FORMAT` | `text` or `json` (one JSON object per line) | same |
| `LOG_FILE` | `logs/backend.log` locally, empty on Azure | `logs/mcp-server.log` |
| `LOG_QUESTIONS` | `true` = include question/transcript text | - |
| `SLOW_REQUEST_MS` / `SLOW_QUERY_MS` | 15000 | 3000 |

## 8. Notes

- Groq is a cloud API: questions, audio and tool results (sales numbers) are sent to Groq. Customer name/phone columns are removed by the MCP server before results leave it.
- Without `MCP_AUTH_TOKEN` the MCP server prints a warning and accepts any caller. Always set it when `MCP_HOST` is not `127.0.0.1`.
- This project uses version 2 of the `mcp` Python SDK (`MCPServer`, `Client`). Many online tutorials use the older v1 `FastMCP` name.
- SQL Server 2014 does not support `CREATE OR ALTER`; the BOPOS scripts avoid it.
