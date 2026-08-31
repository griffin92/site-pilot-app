# Site Pilot — Setup

## Deploy in stages

The app is built to run at each stage, so you can deploy now and add pieces later.

| Stage | What you get | What you need |
|---|---|---|
| 1 | Everything works, nothing persists between sessions | `GEMINI_API_KEY` |
| 2 | Projects, indexes, RFIs, artifacts persist | + Firestore (free Spark plan) |
| 3 | Drawings + photos persist too | + Firebase Storage (Blaze plan) |

---

## Stage 1 — Run it now

**Repo layout** — the app is modular now, so keep this structure:

```
app.py            ← entry point (this is what you point Streamlit at)
config.py
requirements.txt
packages.txt
services/   engines/   ui/   templates/
```

1. Copy your existing `templates/gantt_template.xlsx` into `templates/`.
2. Add your `GEMINI_API_KEY` to your host's secrets.
3. Point your host at `app.py` (note: renamed from `SitePilotAI_Cloud.py`).

That's it. You'll see a "Session" pill in the title block, meaning no persistence yet.

---

## Stage 2 — Firestore (project memory)

This is what kills the repetitive indexing. The sheet index is ~100 AI calls
on a full set; once saved, it's recalled instantly forever.

1. Go to https://console.firebase.google.com → **Add project**. Skip Analytics.
2. **Build → Firestore Database → Create database.** Start in **production mode**,
   pick a region near you.
3. **Project Settings (gear) → Service accounts → Generate new private key.**
   Downloads a JSON file.
4. Paste the *entire* JSON into your secrets as `FIREBASE_SERVICE_ACCOUNT`
   (see `.streamlit/secrets.toml.example` for the exact format).

Restart. The pill flips to "Cloud."

**Security rules** — since the Admin SDK bypasses rules and this is single-user,
lock the client side down entirely:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} { allow read, write: if false; }
  }
}
```

---

## Stage 3 — Storage (drawings + photos persist)

**This requires the Blaze plan.** Firebase Storage no longer offers a free tier
for new projects. Blaze is pay-as-you-go with a free monthly allowance — for
single-user use with a few drawing sets and photo libraries, expect very low
single-digit dollars per month, but **set a budget alert** so there are no
surprises.

1. **Upgrade to Blaze** (Firebase console, bottom-left).
2. **Build → Storage → Get started.**
3. Copy the bucket name (like `your-project.firebasestorage.app`) into secrets as
   `FIREBASE_STORAGE_BUCKET`.
4. Set a budget alert: Google Cloud Console → Billing → Budgets & alerts.

Without this, everything still works — you just re-upload the PDF each session
and photos are session-only.

---

## Hosting

You mentioned being open to moving off Streamlit Community Cloud. The ~1GB
ceiling there is what caused the original silent crash on a 102-sheet set.
Batching now keeps you under it, but photos plus large sets will push on it again.

| Host | Notes |
|---|---|
| **Streamlit Community Cloud** | Free, ~1GB RAM. Fine for Stage 1–2, tight for photos. |
| **Render** | ~$7/mo for 512MB, ~$25/mo for 2GB. Simple, Docker-free. |
| **Railway** | Usage-based, easy GitHub deploys. Good middle ground. |
| **Fly.io** | Cheap, scales to zero, more config work. |

For any of them: start command is `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`,
and you need `poppler-utils` installed (that's what `packages.txt` does on
Streamlit Cloud; on Render/Railway add it via an apt buildpack or Dockerfile).

---

## Secrets

Never commit `.streamlit/secrets.toml` — `.gitignore` already excludes it.
Use your host's secrets manager in production.
