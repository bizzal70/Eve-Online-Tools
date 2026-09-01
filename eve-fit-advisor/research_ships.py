#!/usr/bin/env python3
"""
Re-researches specific ships already in fits_database.json and replaces
their fit -- like research_all.py, but scoped to just the ships you name
instead of all of them.

    set ANTHROPIC_API_KEY=sk-ant-...      (Windows cmd)
    $env:ANTHROPIC_API_KEY="sk-ant-..."   (PowerShell)
    python research_ships.py Vexor Hurricane
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
        sys.exit("Usage: python research_ships.py <Ship1> <Ship2> ...")

    with open(core.FITS_PATH) as f:
        data = json.load(f)

    for ship_name in ship_names:
        if ship_name not in data["ships"]:
            print(f"--- {ship_name}: not found in fits_database.json, skipping ---\n")
            continue

        old_fit_name = data["ships"][ship_name]["fits"][0]["name"]
        print(f"--- {ship_name} (replacing '{old_fit_name}') ---")
        try:
            fit = core.research_fit(ship_name, "", api_key)
        except core.EveFitAdvisorError as e:
            print(f"  FAILED: {e}\n")
            continue

        name_warnings = core.validate_fit_names(fit)
        slot_problems = core.validate_fit_slots(ship_name, fit)
        if slot_problems:
            print(f"  SLOT PROBLEM: {slot_problems}")
        if name_warnings:
            print(f"  WARNING -- unverified names: {', '.join(name_warnings)}")

        data["ships"][ship_name]["fits"] = [fit]
        print(f"  -> {fit['name']}")
        print(f"  sources: {', '.join(s['title'] for s in fit.get('sources', []))}\n")

    with open(core.FITS_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Done. Wrote {core.FITS_PATH}")


if __name__ == "__main__":
    main()
