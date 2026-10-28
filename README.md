# THIQA — Smart Car-Insurance Recommendation Platform

THIQA (ثقة) is a graduation-project platform (IT Department, Qassim University) that recommends the most
suitable car-insurance package for a customer using a **three-agent pipeline**, and explains *why*.
Insurer prices come from a **simulated insurer platform** (four mock companies with their own APIs and
websites). Prices are demo values, **not real quotes from Saudi insurers**.

## Architecture

```
Browser ──► Node.js / Express (3000)  ──►  Python agents service (8000)  ──►  Mock insurer APIs (8001)
            • customer + admin UI           Agent 1  Data Receiver & Retrieval       4 companies, each with its
            • auth & sessions               Agent 2  Recommendation (weighted sum)   own request/response format,
            • persistence (thiqa.db)        Agent 3  Explainer                       staff portal & purchase page
            • admin dashboard               (reads providers + API settings          (insurers_mock.db)
                                             from thiqa.db on every request)
```

| Component | Folder | Database |
|---|---|---|
| THIQA website, customer accounts, history, admin dashboard | `server/` | `database/thiqa.db` |
| Three agents + orchestrator | `agents/main.py`, `agent1_receiver.py`, `agent2_recommender.py`, `agent3_explainer.py`, `orchestrator.py` | reads `thiqa.db` (providers + API settings) |
| Simulated insurer companies | `agents/mock_insurer_api.py` | `database/insurers_mock.db` |

- **Agent 1** validates the request (incl. city / gender / accidents / cars count), calls every *active*
  insurer **in parallel** with its own adapter, retries fast failures, and normalizes all packages into one
  unified format. One failing insurer never breaks the request.
- **Agent 2** filters ineligible offers, normalizes 9 criteria to 0–1, and scores each package with
  **S = Σ wᵢ·xᵢ** using the weight profile of the chosen priority (Budget / Balanced / Service / Digital).
  Packages that include the add-ons the customer explicitly requested are ranked first.
- **Agent 3** turns the score breakdown into a plain Arabic explanation and compares with alternatives.
- **Node** stores every request (success *and* failure), all retrieved quotes, the recommendation and its
  explanation in one transaction (audit trail), and serves the admin dashboard.

## Run (Windows)

Requirements: **Python 3.10+** and **Node.js 22.13+**.

Double-click **`run-website.bat`**. On first run it installs dependencies, then opens three windows:

| Service | URL |
|---|---|
| THIQA website | http://localhost:3000 |
| Admin dashboard | http://localhost:3000/admin/ |
| Insurer companies platform | http://127.0.0.1:8001 |
| Agents API docs | http://127.0.0.1:8000/docs |

Start order matters the first time: the website (Node) creates/migrates `thiqa.db` and seeds the four
providers, then the insurer platform moves its legacy tables into `insurers_mock.db`. The batch file
does this for you. Manual start (three terminals, from the repository folder):

```bat
cd server && npm install && npm start
cd agents && python -m pip install -r requirements.txt && python -m uvicorn mock_insurer_api:app --port 8001
cd agents && python -m uvicorn main:app --port 8000
```

### Accounts

| Who | How |
|---|---|
| Customer | Register at `/register.html` (username, email, password ≥ 8 chars with a letter and a digit). |
| THIQA admin | Create once: `cd server && npm run create-admin -- --username admin --email admin@thiqa.local` (prompts for a password). Log in at `/admin/login.html`. Admin and customer logins are separate. |
| Insurer staff (demo) | On each company site (e.g. `http://127.0.0.1:8001/tawuniya`): `tawuniya_admin / Tawuniya@2026`, `rajhi_admin / Rajhi@2026`, `medgulf_admin / Medgulf@2026`, `acig_admin / Acig@2026`. Override with `<PROVIDER>_PORTAL_USER` / `<PROVIDER>_PORTAL_PASSWORD` before the first start. |

## Tests

```bat
cd agents && python -m pytest tests -q      :: agents + mock insurers (258 tests)
cd server && npm test                       :: website, auth, persistence, admin, migrations (20 tests)
```

Tests use temporary databases and never touch `database/thiqa.db`.

## Configuration (environment variables)

| Variable | Used by | Default |
|---|---|---|
| `PORT` | Node | `3000` |
| `THIQA_DB_PATH` | Node, agents | `database/thiqa.db` |
| `AGENTS_SERVICE_URL` | Node | `http://127.0.0.1:8000` |
| `INSURER_PLATFORM_URL` | Node (seeded endpoints, links) | `http://127.0.0.1:8001` |
| `COOKIE_SECURE` | Node (set `1` behind HTTPS) | off |
| `AGENTS_ALLOWED_ORIGINS` | agents CORS | `http://localhost:3000,http://127.0.0.1:3000` |
| `INSURERS_DB_PATH` | insurer platform | `database/insurers_mock.db` |
| `MOCK_FAULTS` | insurer platform (demo failures) | e.g. `rajhi=timeout,acig=500` |

## Documentation

- `server/API.md` — every website / admin API endpoint with request and response shapes.
- `database/schema.sqlite.sql` — the database schema actually used (commented).
- `database/thiqa_database.sql` — the same logical schema in MySQL syntax (for the report).
- `CHANGES_AR.md` — summary (Arabic) of what was fixed and added, mapped to the project task list.

## Limitations

- Insurer companies, prices and ratings are simulated. Connecting a real insurer means adding its
  endpoint + key in **Admin → API settings** and, if its format differs, a new adapter in
  `agents/insurer_adapters.py`.
- Do not enter real national IDs or other sensitive personal data in this demo.
