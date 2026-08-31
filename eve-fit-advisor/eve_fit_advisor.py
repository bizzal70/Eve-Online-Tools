#!/usr/bin/env python3
"""
EVE Fit Advisor
===============
Logs into EVE Online via CCP's official SSO (OAuth2 + PKCE -- no client
secret, no password ever touches this script), reads YOUR character's name,
current ship, and trained skills straight from ESI, then tells you the best
fitting on file for that ship and exactly which skills (if any) are holding
you back from flying it in full.

Read-only. The only scopes requested are esi-skills.read_skills.v1 and
esi-location.read_ship_type.v1 -- this script cannot fly your ship, trade,
or spend a single ISK.

------------------------------------------------------------------
ONE-TIME SETUP
------------------------------------------------------------------
1. Go to https://developers.eveonline.com and log in with your EVE account.
2. "Manage Applications" -> "Create New Application":
     - Connection Type : Authentication & API Access
     - Permissions     : esi-skills.read_skills.v1
                         esi-location.read_ship_type.v1
     - Callback URL    : http://localhost:8765/callback
3. Save it, then copy the "Client ID" it gives you.
4. Run this script with that ID:

       python3 eve_fit_advisor.py --client-id=YOUR_CLIENT_ID

   (or set it once: export EVE_CLIENT_ID=YOUR_CLIENT_ID)

A browser tab will open asking you to log in and approve the two read-only
scopes. Approve it, and the script picks the auth code up automatically from
localhost -- nothing to copy/paste.

Run it again any time your skills or active ship change; it's meant to be
reused, not a one-shot report.
------------------------------------------------------------------
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

CALLBACK_PORT = 8765
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
SCOPES = "esi-skills.read_skills.v1 esi-location.read_ship_type.v1"
AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize/"
TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
ESI_BASE = "https://esi.evetech.net/latest"
USER_AGENT = "eve-fit-advisor/1.0 (personal use script)"

FITS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fits_database.json")

_auth_result = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the terminal quiet

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        _auth_result["code"] = qs.get("code", [None])[0]
        _auth_result["state"] = qs.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body style='font-family:sans-serif'>"
            b"<h2>Logged in via EVE SSO.</h2>"
            b"<p>You can close this tab and go back to your terminal.</p>"
            b"</body></html>"
        )


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def do_pkce_login(client_id: str) -> str:
    """Runs the full PKCE authorization-code flow and returns an access token."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)

    try:
        server = http.server.HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    except OSError as e:
        sys.exit(
            f"Couldn't start a local server on port {CALLBACK_PORT} ({e}). "
            "Close whatever else is using that port and try again."
        )
    server.timeout = 180  # give the user 3 minutes to log in

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    print("Opening your browser to log in via EVE SSO...")
    print("If it doesn't open automatically, paste this URL into a browser:\n")
    print(f"  {auth_url}\n")
    webbrowser.open(auth_url)

    server.handle_request()

    code = _auth_result.get("code")
    if not code:
        sys.exit("Login timed out, was cancelled, or was denied. Try again.")
    if _auth_result.get("state") != state:
        sys.exit("State mismatch on the callback -- aborting for safety. Try again.")

    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "code_verifier": verifier,
        }
    ).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "login.eveonline.com",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            token = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Token exchange failed ({e.code}): {e.read().decode(errors='replace')}")

    return token["access_token"]


def decode_jwt_character(access_token: str):
    """Pulls character id/name out of the SSO JWT's payload.

    This does NOT verify the token's signature -- fine here since we just
    received it directly from login.eveonline.com over HTTPS a moment ago
    and only ever use it to read our own data, but don't reuse this helper
    to validate tokens you didn't mint yourself.
    """
    payload_b64 = access_token.split(".")[1]
    padding = "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    char_id = int(payload["sub"].split(":")[-1])
    return char_id, payload.get("name")


def esi_get(path: str, token: str = None, params: dict = None):
    url = ESI_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"ESI request to {path} failed ({e.code}): {e.read().decode(errors='replace')}")


def esi_post(path: str, body, token: str = None):
    url = ESI_BASE + path
    headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"ESI request to {path} failed ({e.code}): {e.read().decode(errors='replace')}")


def resolve_type_name(type_id: int) -> str:
    return esi_get(f"/universe/types/{type_id}/")["name"]


def resolve_skill_ids(skill_names) -> dict:
    """Bulk-resolve skill (inventory type) names to type IDs via ESI."""
    names = sorted(set(skill_names))
    result = {}
    for i in range(0, len(names), 500):  # ESI caps this endpoint at 500 names/call
        chunk = names[i : i + 500]
        data = esi_post("/universe/ids/", chunk)
        for entry in data.get("inventory_types", []):
            result[entry["name"]] = entry["id"]
    return result


def load_fits() -> dict:
    with open(FITS_PATH) as f:
        return json.load(f)["ships"]


def evaluate_fit(fit: dict, skill_levels: dict, skill_ids: dict):
    missing = []
    met = 0
    required = fit["skills"]
    for skill_name, required_level in required.items():
        sid = skill_ids.get(skill_name)
        have = skill_levels.get(sid, 0) if sid else 0
        if have >= required_level:
            met += 1
        else:
            missing.append((skill_name, have, required_level))
    score = met / len(required) if required else 1.0
    return score, missing


def format_report(char_name, ship_name, fit, score, missing) -> str:
    lines = [
        f"Character:       {char_name}",
        f"Active ship:     {ship_name}",
        f"Recommended fit: {fit['name']}  ({score * 100:.0f}% of listed skills trained to spec)",
        "",
    ]
    for slot in ("high", "mid", "low", "rig"):
        if fit.get(slot):
            lines.append(f"{slot.upper():<5} " + ", ".join(fit[slot]))
    if fit.get("drones"):
        lines.append("DRONE " + ", ".join(fit["drones"]))
    if fit.get("charges"):
        lines.append("AMMO  " + ", ".join(fit["charges"]))
    lines.append("")
    if missing:
        lines.append("Train these to fly it exactly as listed:")
        for name, have, need in sorted(missing, key=lambda m: m[2] - m[1], reverse=True):
            lines.append(f"  - {name}: level {have} trained -> need level {need}")
        lines.append("")
        lines.append(
            "(Approximate guidance -- double-check exact per-module requirements "
            "in-game, the fitting window is always authoritative.)"
        )
    else:
        lines.append("You can fly this fit exactly as listed. o7")
    return "\n".join(lines)


def main():
    client_id = os.environ.get("EVE_CLIENT_ID", "")
    for arg in sys.argv[1:]:
        if arg.startswith("--client-id="):
            client_id = arg.split("=", 1)[1]

    if not client_id:
        sys.exit(
            "Missing your ESI app's Client ID.\n"
            "Run with --client-id=YOUR_CLIENT_ID or set EVE_CLIENT_ID.\n"
            "See the setup steps at the top of this script / in README.md."
        )

    if not os.path.exists(FITS_PATH):
        sys.exit(f"Can't find fits_database.json next to this script (expected at {FITS_PATH}).")

    token = do_pkce_login(client_id)
    char_id, char_name = decode_jwt_character(token)
    print(f"\nLogged in as {char_name} (character id {char_id}).\n")

    ship = esi_get(f"/characters/{char_id}/ship/", token=token)
    ship_type_name = resolve_type_name(ship["ship_type_id"])

    skills_data = esi_get(f"/characters/{char_id}/skills/", token=token)
    skill_levels = {s["skill_id"]: s["trained_skill_level"] for s in skills_data["skills"]}

    fits_db = load_fits()
    ship_entry = fits_db.get(ship_type_name)
    if not ship_entry:
        print(f"No curated fits on file yet for '{ship_type_name}'.")
        print(f"Ships currently covered: {', '.join(sorted(fits_db))}")
        print("Add an entry to fits_database.json to extend coverage -- see the README.")
        return

    all_skill_names = sorted({name for fit in ship_entry["fits"] for name in fit["skills"]})
    skill_ids = resolve_skill_ids(all_skill_names)

    scored = sorted(
        ((*evaluate_fit(fit, skill_levels, skill_ids), fit) for fit in ship_entry["fits"]),
        key=lambda x: -x[0],
    )

    best_score, best_missing, best_fit = scored[0]
    print(format_report(char_name, ship_type_name, best_fit, best_score, best_missing))

    if len(scored) > 1:
        print("\nOther fits on file for this ship:")
        for score, _missing, fit in scored[1:]:
            print(f"  - {fit['name']}: {score * 100:.0f}% skill match")


if __name__ == "__main__":
    main()
