"""
EVE Fit Advisor -- core logic
==============================
All the actual work (SSO login, ESI calls, fit scoring) lives here as plain
functions that return data. Nothing in this module prints to the console or
calls sys.exit() -- that's the job of whatever front end imports it (the CLI
in eve_fit_advisor.py, or a future GUI). On any recoverable failure this
module raises EveFitAdvisorError with a human-readable message; catch that at
the front-end boundary and show it however makes sense there.

Read-only. The only scopes requested are esi-skills.read_skills.v1 and
esi-location.read_ship_type.v1 -- this cannot fly your ship, trade, or spend
a single ISK.
"""

import base64
import datetime
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


def base_dir() -> str:
    """Where bundled files (fits_database.json, gui/) live -- the PyInstaller
    temp extraction dir when frozen into an exe, or this file's folder when
    running from source."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


FITS_PATH = os.path.join(base_dir(), "fits_database.json")


def _config_dir() -> str:
    """Per-user local app data folder -- separate from the install/source
    folder so it survives rebuilding the exe and isn't something that'd ever
    land in the repo."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "EveFitAdvisor")
    os.makedirs(path, exist_ok=True)
    return path


ACCOUNTS_PATH = os.path.join(_config_dir(), "accounts.json")

# Fits researched via the Claude AI feature live here, separate from the
# bundled fits_database.json -- that file is read-only once frozen into the
# exe (it's extracted to a temp dir at runtime), and keeping user-added fits
# out of it means they survive rebuilding/updating the app.
CUSTOM_FITS_PATH = os.path.join(_config_dir(), "custom_fits.json")


class EveFitAdvisorError(Exception):
    """Any recoverable failure a front end should show to the user as-is."""


class SavedLoginExpired(EveFitAdvisorError):
    """A remembered character's refresh token no longer works -- the front
    end should fall back to a fresh interactive login, not just show an
    error and stop."""


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
            b"<p>You can close this tab and go back to the app.</p>"
            b"</body></html>"
        )


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def do_pkce_login(client_id: str) -> dict:
    """Runs the full PKCE authorization-code flow and returns the token
    response dict (has "access_token" and "refresh_token").

    Blocks the calling thread until the browser callback arrives (or times
    out after 3 minutes) -- run this off the UI thread in a GUI.
    """
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)

    try:
        server = http.server.HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    except OSError as e:
        raise EveFitAdvisorError(
            f"Couldn't start a local server on port {CALLBACK_PORT} ({e}). "
            "Close whatever else is using that port and try again."
        ) from e
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
    webbrowser.open(auth_url)

    server.handle_request()

    code = _auth_result.get("code")
    if not code:
        raise EveFitAdvisorError("Login timed out, was cancelled, or was denied. Try again.")
    if _auth_result.get("state") != state:
        raise EveFitAdvisorError("State mismatch on the callback -- aborting for safety. Try again.")

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
        raise EveFitAdvisorError(f"Token exchange failed ({e.code}): {e.read().decode(errors='replace')}") from e

    return token


def refresh_access_token(client_id: str, refresh_token: str) -> dict:
    """Exchanges a stored refresh token for a fresh access token, no browser
    involved. Raises SavedLoginExpired if the refresh token's been revoked
    (character deauthorized the app, password changed, etc.) -- callers
    should fall back to do_pkce_login in that case."""
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
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
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            raise SavedLoginExpired("Saved login has expired or was revoked. Please log in again.") from e
        raise EveFitAdvisorError(f"Token refresh failed ({e.code}): {e.read().decode(errors='replace')}") from e


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
        raise EveFitAdvisorError(f"ESI request to {path} failed ({e.code}): {e.read().decode(errors='replace')}") from e


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
        raise EveFitAdvisorError(f"ESI request to {path} failed ({e.code}): {e.read().decode(errors='replace')}") from e


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


def _load_accounts() -> dict:
    if not os.path.exists(ACCOUNTS_PATH):
        return {"last_used": None, "characters": {}}
    with open(ACCOUNTS_PATH) as f:
        return json.load(f)


def _save_accounts(data: dict) -> None:
    with open(ACCOUNTS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _remember_account(char_id: int, char_name: str, client_id: str, refresh_token: str) -> None:
    data = _load_accounts()
    data["characters"][str(char_id)] = {
        "char_name": char_name,
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    data["last_used"] = str(char_id)
    _save_accounts(data)


def list_saved_accounts() -> dict:
    """Returns {"last_used": "<char_id>" or None, "characters": [{"char_id": int, "char_name": str}, ...]}."""
    data = _load_accounts()
    characters = [
        {"char_id": int(cid), "char_name": entry["char_name"]} for cid, entry in data["characters"].items()
    ]
    return {"last_used": data.get("last_used"), "characters": characters}


def forget_account(char_id) -> None:
    data = _load_accounts()
    data["characters"].pop(str(char_id), None)
    if data.get("last_used") == str(char_id):
        data["last_used"] = None
    _save_accounts(data)


def load_fits() -> dict:
    if not os.path.exists(FITS_PATH):
        raise EveFitAdvisorError(f"Can't find fits_database.json next to core.py (expected at {FITS_PATH}).")
    with open(FITS_PATH) as f:
        fits_db = json.load(f)["ships"]

    if os.path.exists(CUSTOM_FITS_PATH):
        with open(CUSTOM_FITS_PATH) as f:
            custom_ships = json.load(f).get("ships", {})
        for ship_name, entry in custom_ships.items():
            if ship_name in fits_db:
                fits_db[ship_name] = {**fits_db[ship_name], "fits": fits_db[ship_name]["fits"] + entry["fits"]}
            else:
                fits_db[ship_name] = entry

    return fits_db


def save_custom_fit(ship_name: str, fit: dict) -> None:
    """Appends a researched fit to the user's local overlay file so it shows
    up as an extra option for that ship from now on."""
    if os.path.exists(CUSTOM_FITS_PATH):
        with open(CUSTOM_FITS_PATH) as f:
            data = json.load(f)
    else:
        data = {"ships": {}}
    data["ships"].setdefault(ship_name, {"fits": []})
    data["ships"][ship_name]["fits"].append(fit)
    with open(CUSTOM_FITS_PATH, "w") as f:
        json.dump(data, f, indent=2)


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


def get_recommendation(client_id: str) -> dict:
    """Full interactive flow: opens the browser for a fresh EVE SSO login,
    then builds the report. Remembers the character afterwards so
    get_recommendation_saved() can skip the browser next time.

    Shape:
      {
        "char_name": str, "char_id": int, "ship_type_name": str,
        "covered": bool,
        "known_ships": [str, ...],          # only present if not covered
        "best": {"fit": dict, "score": float, "missing": [(name, have, need), ...]},
        "alternates": [{"fit": dict, "score": float, "missing": [...]}, ...],
      }
    Raises EveFitAdvisorError on any recoverable failure (auth, network, missing file).
    """
    tokens = do_pkce_login(client_id)
    char_id, char_name = decode_jwt_character(tokens["access_token"])
    _remember_account(char_id, char_name, client_id, tokens["refresh_token"])
    return _build_report(tokens["access_token"], char_id, char_name)


def get_recommendation_saved(char_id) -> dict:
    """Same as get_recommendation(), but silently refreshes a previously
    remembered character's token instead of opening the browser. Raises
    SavedLoginExpired if that character's saved login no longer works --
    callers should fall back to get_recommendation() (fresh login) then."""
    data = _load_accounts()
    entry = data["characters"].get(str(char_id))
    if not entry:
        raise EveFitAdvisorError("No saved login for that character.")

    tokens = refresh_access_token(entry["client_id"], entry["refresh_token"])
    _remember_account(char_id, entry["char_name"], entry["client_id"], tokens["refresh_token"])
    return _build_report(tokens["access_token"], int(char_id), entry["char_name"])


def _build_report(token: str, char_id: int, char_name: str) -> dict:
    ship = esi_get(f"/characters/{char_id}/ship/", token=token)
    ship_type_name = resolve_type_name(ship["ship_type_id"])

    skills_data = esi_get(f"/characters/{char_id}/skills/", token=token)
    skill_levels = {s["skill_id"]: s["trained_skill_level"] for s in skills_data["skills"]}

    fits_db = load_fits()
    ship_entry = fits_db.get(ship_type_name)
    if not ship_entry:
        return {
            "char_name": char_name,
            "char_id": char_id,
            "ship_type_name": ship_type_name,
            "covered": False,
            "known_ships": sorted(fits_db),
        }

    all_skill_names = sorted({name for fit in ship_entry["fits"] for name in fit["skills"]})
    skill_ids = resolve_skill_ids(all_skill_names)

    scored = sorted(
        (
            {"fit": fit, "score": score, "missing": missing}
            for fit, (score, missing) in (
                (fit, evaluate_fit(fit, skill_levels, skill_ids)) for fit in ship_entry["fits"]
            )
        ),
        key=lambda x: -x["score"],
    )

    return {
        "char_name": char_name,
        "char_id": char_id,
        "ship_type_name": ship_type_name,
        "covered": True,
        "best": scored[0],
        "alternates": scored[1:],
    }


_SOURCE_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
    "required": ["title", "url"],
    "additionalProperties": False,
}

_FIT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Short fit name only, e.g. 'Magic Merlin (T2 Blaster Brawler)' -- under 60 characters, no long descriptive clauses.",
        },
        "summary": {
            "type": "string",
            "description": "One sentence describing the fit's role/style, e.g. 'General-purpose PvP brawler for low-SP pilots.'",
        },
        "high": {"type": "array", "items": {"type": "string"}},
        "mid": {"type": "array", "items": {"type": "string"}},
        "low": {"type": "array", "items": {"type": "string"}},
        "rig": {"type": "array", "items": {"type": "string"}},
        "drones": {"type": "array", "items": {"type": "string"}},
        "charges": {"type": "array", "items": {"type": "string"}},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "level": {"type": "integer"}},
                "required": ["name", "level"],
                "additionalProperties": False,
            },
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-6 short, single-idea bullet points: why this fit, ammo choice, flying tips, common variations. Each under ~30 words -- not one long paragraph.",
        },
        "sources": {"type": "array", "items": _SOURCE_SCHEMA},
    },
    "required": ["name", "summary", "high", "mid", "low", "rig", "drones", "charges", "skills", "notes", "sources"],
    "additionalProperties": False,
}


def research_fit(ship_name: str, style_hint: str, api_key: str) -> dict:
    """Uses the Claude API, with live web search turned on, to research a
    current community-recommended fit for a ship instead of relying on
    whatever's already baked into fits_database.json. Returns a dict shaped
    like one entry in that file's "fits" list, plus "notes" and "sources".

    This calls a paid third-party API using the caller's own key -- it is
    not free, and is a separate cost from anything ESI-related. Raises
    EveFitAdvisorError on any failure (bad key, rate limit, network, or a
    response that doesn't parse as the expected shape).
    """
    role = style_hint.strip() if style_hint and style_hint.strip() else "general-purpose"
    prompt = (
        f"Research a current, community-recommended EVE Online ship fitting for a {ship_name}, "
        f"for a {role} role. Use web search to check what EVE Online players currently recommend "
        f"(EVE University wiki, r/Eve, EVE Workbench, Zkillboard-linked fits, or similar community "
        f"sources) -- don't just rely on what you already know, the game's balance changes over "
        f"time and a fit that was good a year ago may not be anymore. Use the EXACT official EVE "
        f"Online names for every module, drone, charge, and skill, spelled and cased as they appear "
        f"in-game, since these get looked up against EVE's live item database afterwards. Return "
        f"one solid fit plus the real sources you actually used. Keep the name short (just the fit's "
        f"name, not a full description); put the one-line role description in 'summary'; and write "
        f"'notes' as several short, single-idea bullet points rather than one long paragraph."
    )

    result = _call_claude_json(prompt, _FIT_SCHEMA, api_key)
    result["skills"] = {s["name"]: s["level"] for s in result["skills"]}  # list-of-pairs -> dict
    result["researched_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    return result


def _call_claude_json(prompt: str, schema: dict, api_key: str) -> dict:
    """Runs one Claude API request with live web search enabled and a
    structured-output schema, returning the parsed JSON result. Shared by
    research_fit() and verify_fit() -- both are "ask Claude to look things
    up on the web and hand back a specific JSON shape" calls that differ
    only in prompt and schema."""
    try:
        import anthropic
    except ImportError as e:
        raise EveFitAdvisorError("The 'anthropic' package isn't installed. Run: pip install anthropic") from e

    client = anthropic.Anthropic(api_key=api_key)
    try:
        with client.messages.stream(
            model="claude-opus-5",
            max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise EveFitAdvisorError("That Anthropic API key was rejected. Double-check it and try again.") from e
    except anthropic.RateLimitError as e:
        raise EveFitAdvisorError("Rate limited by the Anthropic API. Wait a moment and try again.") from e
    except anthropic.APIStatusError as e:
        raise EveFitAdvisorError(f"Claude API error ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise EveFitAdvisorError(f"Couldn't reach the Anthropic API: {e}") from e

    if response.stop_reason == "refusal":
        raise EveFitAdvisorError("Claude declined this request.")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise EveFitAdvisorError("Claude didn't return a usable result. Try again.")

    return json.loads(text)


_VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "still_recommended": {
            "type": "boolean",
            "description": "False if this fit looks outdated/superseded by balance changes, or isn't a real recognizable fit.",
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "concerns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific problems found: fake/renamed items, outdated approach, better alternatives now common, etc. Empty if none.",
        },
        "sources": {"type": "array", "items": _SOURCE_SCHEMA},
    },
    "required": ["still_recommended", "confidence", "concerns", "sources"],
    "additionalProperties": False,
}


def verify_fit(ship_name: str, fit: dict, api_key: str) -> dict:
    """Fact-checks a fit that's already been proposed (whether it's one of
    the app's built-in fits or a previously AI-researched one) -- does NOT
    invent a new fit. Checks two things via live web search: are the named
    modules/drones/charges/skills real, current EVE items, and is this fit
    (or something close to it) still commonly recommended today rather than
    superseded by a balance patch or meta shift.

    Costs the caller's own Anthropic API usage, same as research_fit().
    Raises EveFitAdvisorError on any failure.
    """
    fit_summary = {k: fit.get(k) for k in ("name", "high", "mid", "low", "rig", "drones", "charges", "skills")}
    prompt = (
        f"Here is an EVE Online ship fitting for a {ship_name}:\n\n"
        f"{json.dumps(fit_summary, indent=2)}\n\n"
        f"Use web search to check two things against current sources (EVE University wiki, r/Eve, "
        f"EVE Workbench, official patch notes, or similar): (1) is every module, drone, charge, and "
        f"skill name here a real, currently-existing EVE Online name -- not renamed, removed, or "
        f"invented; (2) is this fit, or something very close to it, still commonly recommended today, "
        f"or has the game's balance changed enough that it's outdated or clearly superseded by a "
        f"different approach. Be skeptical -- flag anything you're not confident about rather than "
        f"assuming it's fine."
    )
    return _call_claude_json(prompt, _VERIFY_SCHEMA, api_key)


def validate_fit_names(fit: dict) -> list:
    """Cross-checks every module/drone/charge/skill name in a researched fit
    against ESI's live item catalog. Returns the names that didn't resolve --
    an empty list means everything checked out; a non-empty one is a signal
    the AI likely got a name slightly wrong (extra/missing word, wrong
    Roman numeral, etc.) and it's worth a manual look before trusting it."""
    all_names = set(
        fit.get("high", [])
        + fit.get("mid", [])
        + fit.get("low", [])
        + fit.get("rig", [])
        + fit.get("drones", [])
        + fit.get("charges", [])
        + list(fit.get("skills", {}).keys())
    )
    resolved = resolve_skill_ids(all_names)  # /universe/ids/ resolves any item name, not just skills
    return sorted(all_names - resolved.keys())
