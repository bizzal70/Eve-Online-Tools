# Eve Online Tools

A small collection of personal tools for EVE Online. Each tool lives in its
own folder in this repo; see that folder's own README for setup and usage.

All tools here follow the same philosophy:

- **Read-only by default.** They log in through CCP's official EVE SSO and
  only ever request the specific ESI scopes they need to *look at* your
  data. None of them fly your ship, trade, or act on your behalf — CCP's
  terms of service are stricter about tools that do that, so these
  deliberately don't.
- **No password ever touches the code.** Login goes through EVE's own SSO
  page in your browser; the tool only ever sees a token, never your
  credentials.
- **Honest about uncertainty.** Where a tool makes a recommendation (a fit,
  an estimate, anything opinion-shaped), it says so plainly rather than
  presenting a guess as fact, and prefers to under-promise rather than
  over-promise.

## Tools

### [eve-fit-advisor](eve-fit-advisor/)

Logs in as your character, checks your current ship and trained skills,
and recommends a fit for it — plus exactly which skills are holding you
back from flying it in full. Available as a GUI, a command-line script, or
a standalone Windows `.exe`.

Ships not already in its database can be researched on demand via the
Claude AI integration (your own Anthropic API key), which searches the web
for what the community currently recommends instead of relying on
hardcoded data. Every fit — built-in or researched — gets checked against
EVE's live item and ship data (real slot counts, a conservative CPU/
powergrid estimate) before being shown, and there's a one-click
"double-check" to fact-check any fit against current sources.

See [eve-fit-advisor/README.md](eve-fit-advisor/README.md) for setup and
full details.

## Adding a new tool

Give it its own folder here (mirroring `eve-fit-advisor/`) with its own
README covering what it does and how to run it. Keep the same philosophy
above unless there's a specific, called-out reason not to.

## Disclaimer

This is unofficial, fan-made software. It is not affiliated with, endorsed,
sponsored, or specifically approved by CCP hf. EVE Online and the EVE logo
are trademarks of CCP hf.
