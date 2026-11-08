# Getting Bharati Desk onto your iPhone without a Mac

Everything below can be done from your Windows PC's web browser. Your iPhone is used only at the end, to
install the app.

| What | Where | Cost |
|---|---|---|
| Server (cases, Drive scanning, Word reports) | Railway | about USD 5–10 / month |
| Building the iPhone app | GitHub (Apple computers in the cloud) | free for occasional builds |
| Installing on iPhone | Apple TestFlight | Apple Developer Program, USD 99 / year |
| AI investigation | Claude Code on your Max plan | included in your plan |

Do the parts in order. Each part ends with a check that tells you it worked.

---

## Part A – Server on Railway (about 20 minutes)

1. Go to **railway.com** → *Login* → *Login with GitHub* (the same GitHub account that holds this repository).
   Choose the **Hobby** plan.
2. **New Project → Deploy from GitHub repo** → pick `satya007809/main`. Allow Railway access to the repository
   if asked.
3. Open the new service → **Settings**:
   * *Source → Root Directory*: `backend`
   * *Source → Branch*: `main` (after the pull request is merged; until then pick
     `claude/bharati-investigation-desk-app-mnxhpj`)
   * *Networking → Generate Domain*. You get an address like `bharati-desk-production.up.railway.app`.
     Write it down; this is your **server address**.
4. In the project, click **+ Create → Database → PostgreSQL**.
5. Back on the service → **+ (or right-click) → Attach Volume**, mount path: `/var/lib/bharati/storage`.
6. Service → **Variables → Raw Editor** and paste:

   ```
   BID_ENVIRONMENT=production
   BID_AI_MODE=claude_code
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   BID_JWT_SECRET=${{secret(64)}}
   BID_DATA_ENCRYPTION_KEY=${{secret(64)}}
   BID_RUN_WORKER_IN_PROCESS=true
   BID_ALLOW_REGISTRATION=true
   RAILWAY_RUN_UID=0
   ```

   Click *Update Variables*. Railway rebuilds and starts the server, which takes 5–10 minutes the first time.
7. **Important:** after the first start, open *Variables*, reveal `BID_DATA_ENCRYPTION_KEY` and save its value
   somewhere safe (a password manager). Without it, stored case files cannot be decrypted.

**Check:** open `https://<your server address>/health` in the browser. It should show `{"ok":true}`.

---

## Part B – Apple Developer account (about 1–2 days for Apple to approve)

1. On your iPhone install Apple's **Apple Developer** app → *Account* → **Enroll now** (as an
   individual). Pay USD 99. Apple usually approves within 48 hours.
2. When approved, on your PC open **developer.apple.com/account** → *Membership details*. Note your
   **Team ID** (10 characters).
3. **Certificates, IDs & Profiles → Identifiers → +** → *App IDs → App* → Description `Bharati Desk`,
   Bundle ID (Explicit) `in.bharatiinvestigations.desk` → Register.
4. Open **appstoreconnect.apple.com** → *Apps* → **+ → New App**: platform iOS, name
   `Bharati Investigation Desk` (if the name is taken, add your city), language English, bundle ID
   `in.bharatiinvestigations.desk`, SKU `bharati-desk`.
5. App Store Connect → **Users and Access → Integrations → App Store Connect API → Team Keys → +**.
   Name `GitHub build`, access **Admin**. Download the `.p8` file. It can be downloaded only once, so keep it
   safe. Note the **Key ID** and the **Issuer ID** shown on that page.

**Check:** you have Team ID, Key ID, Issuer ID and the `.p8` file.

---

## Part C – Let GitHub build the app (10 minutes, then about 20 minutes of building)

1. On github.com open the repository → **Settings → Secrets and variables → Actions → New repository
   secret**. Add four secrets:

   | Name | Value |
   |---|---|
   | `APPLE_TEAM_ID` | your Team ID |
   | `ASC_KEY_ID` | the Key ID |
   | `ASC_ISSUER_ID` | the Issuer ID |
   | `ASC_KEY_P8` | open the `.p8` file in Notepad and paste the **whole** text, including the BEGIN/END lines |

2. Repository → **Actions → ios → Run workflow**. Choose the branch, leave *Upload a new build to TestFlight*
   ticked, and click **Run workflow**.
3. Wait for both jobs to turn green, about 20–30 minutes.

**Check:** App Store Connect → your app → **TestFlight** shows a build (status *Processing* for a few
minutes, then *Ready to Submit / Testing*). If a job turns red, send me a screenshot of the error.

---

## Part D – Install on your iPhone (5 minutes)

1. App Store Connect → your app → TestFlight → **Internal Testing → +** → create group `Me` → add yourself.
2. On the iPhone install **TestFlight** from the App Store and open the invitation email, or open TestFlight
   directly. Tap **Install** on Bharati Desk.
3. Open **Bharati Desk** → *Server* = `https://<your server address>` → **First-time setup: create account**.
   The first account becomes administrator.
4. Back in Railway → *Variables*: set `BID_ALLOW_REGISTRATION=false` so nobody else can sign up.

TestFlight builds expire after 90 days. To renew, run the *ios* workflow again (Part C step 2).

---

## Part E – Connect Google Drive (15 minutes)

Follow `SETUP_AND_DEPLOYMENT.md` section 3 with redirect URI
`https://<your server address>/api/v1/connectors/google_drive/callback`, then add to Railway *Variables*:

```
BID_GOOGLE_CLIENT_ID=...
BID_GOOGLE_CLIENT_SECRET=...
```

In the app: Settings → Cloud accounts → **Connect** Google Drive.

## Part F – Connect Claude Code (10 minutes)

Follow `CLAUDE_CODE_MODE.md` → *One-time setup*, steps 2–4, using your server address.

You are ready. Create a case on your iPhone, paste the Drive link, scan, then tap **Investigate in Claude Code**.
