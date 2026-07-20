# Screenshots

Captured against the seeded demo estate (`demo-milligan`) via a headless Chromium pass
through the real running app — not mocked, not hand-picked from ideal state. Currently
referenced from the root `README.md`:

- `dashboard.png` — the hero shot: seeded demo estate with its two CRITICAL alerts.
- `documents.png` — the upload screen with the parsing checklist.
- `chat.png` — a real, grounded RAG answer with a markdown table.

`welcome.jpg` (the marketing landing page) is captured but not currently embedded in the
README — the dashboard does more work as the lead image. Swap it in if you'd rather open
with the landing page.

## Retaking these

```bash
make dev        # agent on :8000, web on :3000
make seed       # separate terminal
```

Then drive a headless browser through: `/welcome` → click "Try the live demo" → screenshot
`/` (dashboard) → click "Documents" → screenshot → click "Estate chat", send a message, wait
for the stream to finish → screenshot. Playwright works well for this; there's no committed
script since it's a one-off tool, not part of the app.

A 15–30s screen-recording GIF of the full flow (upload → alert fires → chat about it)
would convert better than any single screenshot, if you want to go further.
