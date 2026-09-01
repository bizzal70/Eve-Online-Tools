#!/usr/bin/env python3
"""
Runs the "double-check this fit" feature against specific ships already in
fits_database.json, straight from the command line -- useful for checking
several ships in one go instead of clicking through the GUI one at a time.

    set ANTHROPIC_API_KEY=sk-ant-...      (Windows cmd)
    $env:ANTHROPIC_API_KEY="sk-ant-..."   (PowerShell)
    python verify_ships.py Vexor Hurricane
"""

import json
import os
import sys

import core


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY first (see the docstring at the top of this file).")

    ship_names = sys.argv[1:]
    if not ship_names:
        sys.exit("Usage: python verify_ships.py <Ship1> <Ship2> ...")

    with open(core.FITS_PATH) as f:
        data = json.load(f)

    for ship_name in ship_names:
        entry = data["ships"].get(ship_name)
        if not entry:
            print(f"--- {ship_name}: not found in fits_database.json, skipping ---\n")
            continue

        fit = entry["fits"][0]
        print(f"--- {ship_name} ('{fit['name']}') ---")
        try:
            result = core.verify_fit(ship_name, fit, api_key)
        except core.EveFitAdvisorError as e:
            print(f"  FAILED: {e}\n")
            continue

        verdict = "still current" if result["still_recommended"] else "MAY BE OUTDATED/INCORRECT"
        print(f"  Verdict: {verdict} (confidence: {result['confidence']})")
        for c in result.get("concerns", []):
            print(f"  - {c}")
        for s in result.get("sources", []):
            print(f"  source: {s['title']} ({s['url']})")
        print()


if __name__ == "__main__":
    main()
