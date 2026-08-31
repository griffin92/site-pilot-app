#!/usr/bin/env bash
# Site Pilot -- one-shot deploy helper.
#
# Run this from inside your existing local clone of the site-pilot-app repo,
# with the unzipped sitepilot/ folder sitting next to it. It uses YOUR already-
# configured git credentials -- it never asks for or handles a password.
#
#   bash deploy.sh /path/to/unzipped/sitepilot
#
set -euo pipefail

SRC="${1:-}"
if [ -z "$SRC" ] || [ ! -f "$SRC/app.py" ]; then
  echo "Usage: bash deploy.sh /path/to/unzipped/sitepilot"
  echo "  (the folder containing app.py, config.py, engines/, services/, ui/)"
  exit 1
fi

if [ ! -d .git ]; then
  echo "ERROR: run this from inside your git repo (no .git found here)."
  exit 1
fi

echo "==> Backing up current state to branch 'pre-rebuild-backup'"
git branch -f pre-rebuild-backup HEAD 2>/dev/null || true

echo "==> Copying rebuild files in"
mkdir -p engines services ui templates .streamlit
cp "$SRC/app.py" "$SRC/config.py" "$SRC/requirements.txt" "$SRC/packages.txt" .
cp "$SRC/engines/"*.py   engines/
cp "$SRC/services/"*.py  services/
cp "$SRC/ui/"*.py        ui/
cp "$SRC/templates/gantt_template.xlsx" templates/
cp "$SRC/.streamlit/config.toml" .streamlit/
cp "$SRC/.gitignore" .
cp "$SRC/SETUP.md" "$SRC/HOTFIX_deployed_app.md" . 2>/dev/null || true

echo "==> Making sure secrets are never committed"
grep -qxF '.streamlit/secrets.toml' .gitignore || echo '.streamlit/secrets.toml' >> .gitignore
git rm --cached .streamlit/secrets.toml 2>/dev/null || true

echo "==> Sanity check: every module compiles"
python3 -m compileall -q app.py config.py engines services ui > /dev/null

echo "==> Files staged:"
git add -A
git status --short

cat <<'NOTE'

------------------------------------------------------------------
Nothing has been pushed yet. Review the list above, then run:

    git commit -m "Rebuild: modular architecture, estimator, RFI, project memory"
    git push

If anything looks wrong, undo everything with:

    git reset --hard pre-rebuild-backup

AFTER PUSHING, in Streamlit Cloud (share.streamlit.io):
  Manage app -> Settings -> Main file path
  change:  SitePilotAI_Cloud.py
  to:      app.py
The app will not start until you change this.
------------------------------------------------------------------
NOTE
