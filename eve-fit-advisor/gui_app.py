#!/usr/bin/env python3
"""
EVE Fit Advisor -- GUI front end
==================================
Same read-only login/ESI/scoring logic as the CLI (see core.py), presented
as a local desktop window instead of a terminal. No password, no client
secret, no network server exposed beyond the localhost OAuth callback the
SSO login already requires.

Run:
    python gui_app.py
"""

import os

import webview

from core import (
    EveFitAdvisorError,
    base_dir,
    forget_account,
    get_recommendation,
    get_recommendation_saved,
    list_saved_accounts,
    research_fit,
    save_custom_fit,
    validate_fit_names,
    validate_fit_slots,
    verify_fit,
)

GUI_DIR = os.path.join(base_dir(), "gui")


class Api:
    def start_login(self, client_id):
        """Called from JS. Blocks (this runs off the GUI thread) until the
        SSO login completes or fails, then returns a JSON-serializable dict.
        Used for a fresh interactive login (new character, or a saved one
        whose token has expired).
        """
        try:
            data = get_recommendation(client_id)
            return {"ok": True, "data": data}
        except EveFitAdvisorError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # unexpected -- still surface it to the UI, not a crash
            return {"ok": False, "error": f"Unexpected error: {e}"}

    def list_accounts(self):
        """Remembered characters this app has previously logged into."""
        return list_saved_accounts()

    def quick_login(self, char_id):
        """Continues as a remembered character using its saved refresh
        token -- no browser involved. If the saved login has expired,
        returns ok:False with expired:True so the UI can offer a fresh
        login instead of just showing an error."""
        try:
            data = get_recommendation_saved(char_id)
            return {"ok": True, "data": data}
        except EveFitAdvisorError as e:
            return {"ok": False, "error": str(e), "expired": type(e).__name__ == "SavedLoginExpired"}
        except Exception as e:
            return {"ok": False, "error": f"Unexpected error: {e}", "expired": False}

    def forget_account(self, char_id):
        forget_account(char_id)
        return {"ok": True}

    def research_fit(self, ship_name, style_hint, api_key):
        """Calls the Claude API (with live web search) to research a
        current fit for a ship, using the caller's own Anthropic API key.
        This is a paid call the user is opting into, separate from ESI."""
        try:
            fit = research_fit(ship_name, style_hint, api_key)
            warnings = validate_fit_names(fit)
            slot_problems = validate_fit_slots(ship_name, fit)
            return {"ok": True, "fit": fit, "warnings": warnings, "slot_problems": slot_problems}
        except EveFitAdvisorError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Unexpected error: {e}"}

    def save_researched_fit(self, ship_name, fit):
        save_custom_fit(ship_name, fit)
        return {"ok": True}

    def verify_fit(self, ship_name, fit, api_key):
        """Fact-checks a fit already on screen (built-in or researched)
        instead of proposing a new one -- another paid Claude API call."""
        try:
            result = verify_fit(ship_name, fit, api_key)
            return {"ok": True, "result": result}
        except EveFitAdvisorError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Unexpected error: {e}"}


def main():
    webview.create_window(
        "EVE Fit Advisor",
        os.path.join(GUI_DIR, "index.html"),
        js_api=Api(),
        width=820,
        height=720,
        min_size=(600, 500),
        background_color="#0b0f14",
    )
    webview.start()


if __name__ == "__main__":
    main()
