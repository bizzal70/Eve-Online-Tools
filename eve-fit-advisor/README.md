# EVE Fit Advisor

A small, read-only tool: it logs into EVE Online through CCP's official login
(ESI/SSO), looks at your character's name, current ship, and trained skills,
and tells you the best fitting on file for that ship — plus exactly which
skills are holding you back from flying it in full.

It never sees your password, and it only ever requests two read-only
permissions (your skills, and what ship you're currently in). It cannot fly
your ship, trade, warp you anywhere, or spend your ISK — CCP's terms of
service ban tools that act in the game on your behalf, so this one
deliberately only *reads*.

Run it locally on your own computer (not in a browser tab, not in this
chat) — it needs to open your web browser and briefly run a tiny local
server to catch the login redirect.

## 1. Register a free ESI application (one-time, ~2 minutes)

1. Go to **https://developers.eveonline.com** and log in with your EVE
   account.
2. **Manage Applications → Create New Application.**
3. Fill it in:
   - **Name**: anything, e.g. `Fit Advisor`
   - **Description**: anything
   - **Connection Type**: `Authentication & API Access`
   - **Permissions**: check
     - `esi-skills.read_skills.v1`
     - `esi-location.read_ship_type.v1`
   - **Callback URL**: `http://localhost:8765/callback`
4. Save it, then open the application and copy the **Client ID** shown.
   (There's no client secret to worry about — this script uses PKCE, which
   doesn't need one.)

## 2. Run it

There are three ways to run this: a standalone `.exe`, a GUI window run from
Python, or the original command line. All three use the same login/scoring
logic (`core.py`) and the same `fits_database.json`.

### Standalone .exe (no Python needed)

If someone built `EVE Fit Advisor.exe` for you (see "Building the .exe"
below), just double-click it. Nothing to install. `fits_database.json` and
the GUI's HTML/CSS/JS are bundled inside it, so it's fully self-contained —
editing fits means rebuilding the exe (or just using the GUI/CLI from source
instead, which reads the file live).

### GUI (recommended, from source)

Needs one extra package, [pywebview](https://pywebview.flowrl.com/), which
renders the window using Windows' built-in WebView2 runtime (already present
on any up-to-date Windows 10/11):

```bash
pip install -r requirements.txt
python gui_app.py
```

A window opens. Paste your Client ID, click **Log In With EVE**, approve the
read-only scopes in the browser tab that pops up, and the recommended fit
appears back in the window.

After that first login, the app remembers your character and just continues
as them automatically the next time you open it — no browser, no clicking,
nothing to re-enter. Use **"Log in with a different character"** to add
another character or switch, and the **×** next to a remembered character to
forget it (and its saved login) entirely.

This works by storing a refresh token locally at
`%APPDATA%\EveFitAdvisor\accounts.json` (both the GUI and the standalone exe
use the same file, so logging in once covers both). Anyone with a copy of
that file could read your skills/ship/etc. without your password — it's not
as sensitive as a password, but treat it like a "stay logged in" browser
cookie: don't share it, and remove it (or use the × in the app) if you ever
want to fully revoke local access.

### Command line

No extra packages needed — just the standard library.

```bash
python3 eve_fit_advisor.py --client-id=YOUR_CLIENT_ID
```

or set it once for future runs:

```bash
export EVE_CLIENT_ID=YOUR_CLIENT_ID
python3 eve_fit_advisor.py
```

Either way, a browser tab opens asking you to log in to EVE and approve the
two read-only scopes. Approve it, and it picks up the login automatically —
nothing to copy/paste. It then reports your recommended fit and any skills
still worth training for it.

Run it again any time you switch ships or finish training something —
it's meant to be rerun, not a one-off report.

## Building the .exe

Requires [PyInstaller](https://pyinstaller.org/):

```bash
pip install -r requirements.txt
pip install pyinstaller
```

Then, from the `eve-fit-advisor` folder:

```bash
pyinstaller --onefile --windowed --name "EVE Fit Advisor" --add-data "fits_database.json;." --add-data "gui;gui" gui_app.py
```

The finished exe lands at `dist/EVE Fit Advisor.exe`. `build/` and `dist/`
are gitignored — the exe itself isn't checked into the repo (it's a
multi-megabyte local build artifact); rebuild it from source whenever you
want a fresh copy.

## 3. Ships currently covered

`Venture`, `Retriever`, `Rifter`, `Merlin`, `Vexor`, `Catalyst`, `Rupture`,
`Drake`, `Hurricane`, `Raven`.

If your active ship isn't in that list, the script will say so and list
what is. Add more any time — see below.

## Adding or editing fits

Everything the tool recommends lives in `fits_database.json`, in plain
JSON, one entry per ship (keyed by the ship's exact in-game type name).
Each fit lists modules by slot, drones/charges, and a `skills` map of
skill name → minimum level. To add a ship or tweak a fit, just edit that
file — no code changes needed. Skill names must match real EVE skill
names exactly (that's how the script looks up their skill IDs via ESI).

The fits shipped here are general community-standard baseline loadouts
meant as a solid starting point, not necessarily the single best possible
fit for your exact circumstances (implants, current market prices, your
specific playstyle). For serious min-maxing, cross-check in a fitting
tool like Pyfa or EVE Workbench.

## Troubleshooting

- **"Couldn't start a local server on port 8765"** — something else on
  your machine is using that port. Close it, or change `CALLBACK_PORT` in
  `eve_fit_advisor.py` *and* the Callback URL in your ESI application to
  match.
- **Login times out** — you have 3 minutes to complete the browser login
  after it opens; just rerun the script if you miss the window.
- **"No curated fits on file yet for '<Ship>'"** — that ship isn't in
  `fits_database.json` yet; add it following the pattern of the existing
  entries.
