# Setup, configuration and deployment

## 1. Run the backend locally (Mac, Linux or Windows/WSL)

```bash
cd backend
```

```bash
python3 -m venv .venv && source .venv/bin/activate
```

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest
```

Run the complete workflow on a synthetic Own Damage folder (fake AI, no API cost):

```bash
python scripts/demo_vertical_slice.py ./demo_output
```

The same demo against the real Claude API (needs `ANTHROPIC_API_KEY`):

```bash
ANTHROPIC_API_KEY=sk-ant-... python scripts/demo_vertical_slice.py ./demo_output --real
```

Start the API with an in-process worker:

```bash
uvicorn app.main:app --reload
```

Interactive API docs: http://localhost:8000/docs (disabled in production). Full spec: `docs/openapi.json`.

LibreOffice (`soffice`) should be installed for page counting, PDF output and legacy `.doc/.xls` files.

## 2. Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in. Key items:

| Variable | Notes |
|---|---|
| `BID_DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/bharati` |
| `BID_PUBLIC_BASE_URL` | Public HTTPS URL of the API (used for OAuth redirects) |
| `BID_JWT_SECRET` | ≥ 32 random characters |
| `BID_DATA_ENCRYPTION_KEY` | `python -m app.cli gen-key`. **Back it up** – without it stored files cannot be decrypted |
| `ANTHROPIC_API_KEY` | Server only. Never in the iOS app |
| `BID_AI_MODEL` / `BID_AI_DIGEST_MODEL` / `BID_AI_EFFORT` | Default `claude-opus-5-5`, effort `high` |
| `BID_GOOGLE_CLIENT_ID` / `_SECRET` | Google OAuth web client |
| `BID_MICROSOFT_CLIENT_ID` / `_SECRET` | Optional OneDrive |
| `BID_ALLOW_REGISTRATION` | Set `false` after creating your account |
| `BID_RUN_WORKER_IN_PROCESS` | `true` for a single small server; `false` when running `python -m app.worker` separately |

## 3. Google Drive OAuth

1. Google Cloud Console → create a project → **APIs & Services → Library** → enable **Google Drive API**.
2. **OAuth consent screen** → External → add your Google account as a **test user**. Scopes:
   `openid`, `email`, `.../auth/drive.readonly`, `.../auth/drive.file`.
3. **Credentials → Create OAuth client ID → Web application**. Authorised redirect URI:
   `https://<your-api-domain>/api/v1/connectors/google_drive/callback`.
4. Put the client id/secret in `.env`.

Important: while the consent screen is in **Testing** mode Google expires refresh tokens after 7 days
(you will be asked to reconnect weekly). `drive.readonly` is a *restricted* scope: publishing the app for
general users requires Google verification and a security assessment. For a single business account,
staying in Testing mode with yourself as test user is the practical option; alternatively use a Google
Workspace account and mark the app **Internal** (no 7-day expiry, no verification).

## 4. Deploy (Docker Compose on any VPS – e.g. an Indian region for data residency)

```bash
cd backend && cp .env.example .env
```

Edit `.env`, then:

```bash
POSTGRES_PASSWORD='choose-a-strong-password' docker compose up -d --build
```

This runs PostgreSQL, the API (applies `alembic upgrade head` on start) and a separate worker. Put an HTTPS
reverse proxy in front, e.g. Caddy:

```
api.your-domain.in {
    reverse_proxy 127.0.0.1:8000
}
```

Create your account from the app's "First-time setup" (the first user becomes administrator), then set
`BID_ALLOW_REGISTRATION=false` and restart. Alternatively:

```bash
docker compose exec api python -m app.cli create-user you@example.com "Your Name"
```

Daily retention purge (cron on the host):

```
15 2 * * * cd /opt/bharati/backend && docker compose exec -T api python -m app.cli purge-expired
```

Backups: back up the Postgres volume, the `storage` volume **and** the encryption key (separately).

## 5. Database migrations

```bash
alembic upgrade head
```

After changing `app/models.py`:

```bash
alembic revision --autogenerate -m "describe change"
```

## 6. Using your existing report format

In the app: Settings → Administration → Reference report formats → choose category (or "All categories") →
upload `OD_report.docx`. New reports keep that document's letterhead, header/footer, margins and styles. Section
headings are defined in `backend/app/reports/templates/<category>.yaml`; edit them to mirror your reference
report's heading structure exactly.
