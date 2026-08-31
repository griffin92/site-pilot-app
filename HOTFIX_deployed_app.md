# Hotfix for the currently deployed app (`SitePilotAI_Cloud.py`)

Apply this if you want the live app's contrast fixed **now**, without deploying
the full rebuild.

## The bug

Your app runs in **dark theme**. My earlier CSS assumed light:

```css
section[data-testid="stSidebar"] button:not(.stButton button):not([kind="primary"]) { color: var(--sp-ink) !important; }
```

`--sp-ink` is near-black (`#10151C`). That rule was meant for Streamlit's
"Browse files" button, which has a light background **in light theme**. In dark
theme that button is dark — so this paints dark text on a dark button.

Root cause: I set a text colour on an element whose background I don't control.

## Two-part fix

### 1. Pin the theme

Create `.streamlit/config.toml` in your repo:

```toml
[theme]
base = "light"
primaryColor = "#E8590C"
backgroundColor = "#F3F5F7"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#10151C"
font = "sans serif"
```

This alone fixes it, since the CSS was written for light. It also makes drawings
read truer against a light canvas.

### 2. Replace the sidebar CSS block

In `SitePilotAI_Cloud.py`, find the sidebar rules that begin with
`/* ---- Sidebar: dark nav rail ---- */` and replace **through** the
`section[data-testid="stSidebar"] hr` line with:

```css
    /* ---- Sidebar: dark nav rail ----
       Rule: never set a text colour on an element whose background you don't
       also control. Native widgets get BOTH here, so contrast holds in either
       theme. */
    section[data-testid="stSidebar"] { background-color: var(--sp-navy); border-right: 1px solid rgba(255,255,255,0.06); }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] small,
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] { color: #E8ECF1; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.1); }

    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        background-color: rgba(255,255,255,0.055);
        border: 1px dashed rgba(232,236,241,0.32);
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] div,
    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] span,
    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small { color: #C9D2DC; }
    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
        background-color: rgba(232,236,241,0.14);
        color: #FFFFFF;
        border: 1px solid rgba(232,236,241,0.42);
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploaderFile"] * { color: #C9D2DC; }
    section[data-testid="stSidebar"] [data-baseweb="input"],
    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: #FFFFFF; border-color: rgba(232,236,241,0.28);
    }
    section[data-testid="stSidebar"] [data-baseweb="input"] input,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div { color: var(--sp-ink); }
```

Specifically **delete** the old line containing
`button:not(.stButton button):not([kind="primary"])` — that's the one causing it.

## Also worth knowing

The clash-audit and takeoff bug you reported is **not** fixable with a small
patch to the single file. Both engines scrape lines containing `ISSUE:` /
`TAKEOFF:`, and on any multi-sheet run the merge pass rewrites the findings and
drops those prefixes — so the parser matches nothing and the panel comes up
empty as though the scan found no problems.

The rebuild replaces prefix-scraping with structured JSON output and merges in
Python. That's a real architectural change, not a one-liner, which is why the
fix lives there.
