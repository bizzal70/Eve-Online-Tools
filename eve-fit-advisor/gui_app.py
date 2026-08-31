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

from core import EveFitAdvisorError, get_recommendation

GUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui")


class Api:
    def start_login(self, client_id):
        """Called from JS. Blocks (this runs off the GUI thread) until the
        SSO login completes or fails, then returns a JSON-serializable dict.
        """
        try:
            data = get_recommendation(client_id)
            return {"ok": True, "data": data}
        except EveFitAdvisorError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # unexpected -- still surface it to the UI, not a crash
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
