#!/usr/bin/env python3
"""
EVE Fit Advisor -- command-line front end
==========================================
Logs into EVE Online via CCP's official SSO (OAuth2 + PKCE -- no client
secret, no password ever touches this script), reads YOUR character's name,
current ship, and trained skills straight from ESI, then tells you the best
fitting on file for that ship and exactly which skills (if any) are holding
you back from flying it in full.

Read-only. The only scopes requested are esi-skills.read_skills.v1 and
esi-location.read_ship_type.v1 -- this script cannot fly your ship, trade,
or spend a single ISK.

All the actual logic lives in core.py; this file just wires up args/env,
calls it, and prints the result.

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

A GUI front end (built on this same core.py) is also in the works -- see
the repo README.
------------------------------------------------------------------
"""

import os
import sys

from core import EveFitAdvisorError, format_report, get_recommendation


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

    print("Opening your browser to log in via EVE SSO...\n")
    try:
        result = get_recommendation(client_id)
    except EveFitAdvisorError as e:
        sys.exit(str(e))

    print(f"\nLogged in as {result['char_name']} (character id {result['char_id']}).\n")

    if not result["covered"]:
        print(f"No curated fits on file yet for '{result['ship_type_name']}'.")
        print(f"Ships currently covered: {', '.join(result['known_ships'])}")
        print("Add an entry to fits_database.json to extend coverage -- see the README.")
        return

    best = result["best"]
    print(format_report(result["char_name"], result["ship_type_name"], best["fit"], best["score"], best["missing"]))

    if result["alternates"]:
        print("\nOther fits on file for this ship:")
        for alt in result["alternates"]:
            print(f"  - {alt['fit']['name']}: {alt['score'] * 100:.0f}% skill match")


if __name__ == "__main__":
    main()
