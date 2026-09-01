#!/usr/bin/env python3
"""
Re-researches every ship currently in fits_database.json via the Claude AI
research feature, and overwrites each ship's fit with the result.

This makes one paid Anthropic API call per ship (~10 calls) -- run it
yourself with your own key so no one else's code has to touch it:

    set ANTHROPIC_API_KEY=sk-ant-...      (Windows cmd)
    $env:ANTHROPIC_API_KEY="sk-ant-..."   (PowerShell)
    python research_all.py

Writes straight to fits_database.json. It's tracked in git, so if a result
looks wrong just `git checkout -- fits_database.json` (or ask to review the
diff first) rather than trusting this blindly -- that's the whole reason
the double-check feature exists.
"""

import json
import os
import sys

import core


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY first (see the docstring at the top of this file).")

    with open(core.FITS_PATH) as f:
        data = json.load(f)

    ships = sorted(data["ships"])
    print(f"Researching {len(ships)} ships: {', '.join(ships)}\n")

    for ship_name in ships:
        old_fit_name = data["ships"][ship_name]["fits"][0]["name"]
        print(f"--- {ship_name} (replacing '{old_fit_name}') ---")
        try:
            fit = core.research_fit(ship_name, "", api_key)
        except core.EveFitAdvisorError as e:
            print(f"  FAILED: {e}\n")
            continue

        warnings = core.validate_fit_names(fit)
        if warnings:
            print(f"  WARNING -- unverified names: {', '.join(warnings)}")

        data["ships"][ship_name]["fits"] = [fit]
        print(f"  -> {fit['name']}")
        print(f"  sources: {', '.join(s['title'] for s in fit.get('sources', []))}\n")

    with open(core.FITS_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Done. Wrote {core.FITS_PATH}")


if __name__ == "__main__":
    main()
