# Deploy checklist

Start here. Total time ~15 minutes for Stage 1.

**What I can't do for you:** sign into GitHub, create your Firebase project,
generate service-account keys, or paste API keys. Those all involve credentials
or account creation. Everything else is done — the steps below are the parts
that need your login.

---

## Stage 1 — Get the rebuild running (~10 min)

### 1. Put the files in your repo

**Option A — the script (fastest).** Unzip `sitepilot.zip`, open a terminal in
your local clone of `site-pilot-app`, and run:

```bash
bash /path/to/sitepilot/deploy.sh /path/to/sitepilot
```

It backs up your current state to a `pre-rebuild-backup` branch, copies
everything in, verifies every module compiles, and stages the changes. It
**stops before committing** so you can review. It never touches credentials —
the push uses your existing git setup.

**Option B — drag and drop.** In your repo, create folders `engines/`,
`services/`, `ui/`, `templates/`, `.streamlit/` and copy the matching files in.
Keep `app.py`, `config.py`, `requirements.txt`, `packages.txt` at the top level.

### 2. Commit and push

```bash
git commit -m "Rebuild: modular architecture, estimator, RFI, project memory"
git push
```

### 3. Change the entry point ← **the app will not start without this**

Streamlit Cloud → your app → **Manage app → Settings → Main file path**

| | |
|---|---|
| Change from | `SitePilotAI_Cloud.py` |
| Change to | `app.py` |

### 4. Confirm it boots

You should see the project gate — "Open Project" / "New Project" cards, *not*
the old upload slots. A **Session** pill in the title block is expected; it
means Firebase isn't connected yet, which is fine.

---

## Stage 2 — Firebase, so projects persist (~10 min)

Without this, the app works fully but forgets everything when you close it. The
sheet index is ~100 AI calls on a full set, so this is the step that stops you
re-indexing.

1. https://console.firebase.google.com → **Add project**. Skip Analytics.
2. **Build → Firestore Database → Create database** → *production mode*, pick a
   nearby region.
3. **Gear icon → Project settings → Service accounts → Generate new private key.**
   Downloads a JSON file. **This file is a credential — don't paste it into a
   chat, including to me.**
4. Streamlit Cloud → **Manage app → Settings → Secrets**, and add:

```toml
GEMINI_API_KEY = "your-existing-key"

FIREBASE_SERVICE_ACCOUNT = '''
<paste the entire contents of that JSON file here>
'''
```

5. Reboot the app. The pill flips to **Cloud**.

Lock down client access (the Admin SDK bypasses these, so deny-all is correct
for single-user):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} { allow read, write: if false; }
  }
}
```

---

## Stage 3 — Storage, so drawings and photos persist (optional)

**Requires the Blaze plan.** Firebase Storage has no free tier for new projects.
Blaze is pay-as-you-go with a monthly free allowance; single-user usage should
land in low single-digit dollars — but **set a budget alert** (Google Cloud
Console → Billing → Budgets & alerts) so there are no surprises.

1. Upgrade to Blaze (bottom-left of the Firebase console).
2. **Build → Storage → Get started.**
3. Add to your Streamlit secrets:
   ```toml
   FIREBASE_STORAGE_BUCKET = "your-project-id.firebasestorage.app"
   ```

Skip this and everything still works — you just re-upload the PDF each session
and photos are session-only.

---

## If something breaks

- **App won't start** → main file path is still `SitePilotAI_Cloud.py` (step 3).
- **`ModuleNotFoundError`** → `requirements.txt` didn't get copied. It needs
  `pandas` and `openpyxl`, both new since your last deploy.
- **Gantt button errors** → `templates/gantt_template.xlsx` didn't get copied.
  It's a binary file; drag-and-drop sometimes misses it.
- **Blank crash, no traceback** → memory. Lower `DEEP_SCAN_BATCH` in
  `config.py` from 12 to 8.
- **Want to undo the whole thing** → `git reset --hard pre-rebuild-backup`

Send me the error text and I'll fix it.

---

## Rolling back

The deploy script leaves a `pre-rebuild-backup` branch pointing at your old
code. Your previous single-file app is one command away at all times.
