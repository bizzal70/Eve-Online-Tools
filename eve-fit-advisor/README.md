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

You need Python 3 (no extra packages — it only uses the standard library).

```bash
python3 eve_fit_advisor.py --client-id=YOUR_CLIENT_ID
```

or set it once for future runs:

```bash
export EVE_CLIENT_ID=YOUR_CLIENT_ID
python3 eve_fit_advisor.py
```

A browser tab opens asking you to log in to EVE and approve the two
read-only scopes. Approve it, and the script picks up the login
automatically — nothing to copy/paste. It then prints your recommended
fit and any skills still worth training for it.

Run it again any time you switch ships or finish training something —
it's meant to be rerun, not a one-off report.

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
