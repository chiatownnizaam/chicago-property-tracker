# launchd deployment

Runs the FastAPI backend and a Cloudflare Quick Tunnel as macOS launchd
agents so they auto-start on login and restart on crash.

## Install

```bash
./deploy/launchd/install.sh
```

The script:
1. Renders the two `.plist.template` files with absolute paths for the
   current machine (replaces `{{REPO_DIR}}`, `{{HOME}}`, `{{CLOUDFLARED}}`).
2. Writes them to `~/Library/LaunchAgents/`.
3. Loads them with `launchctl bootstrap`.

Re-run any time the templates change — it's idempotent.

## Status / logs

```bash
launchctl list | grep chicagopropertytracker

tail -f ~/Library/Logs/chicago-property-tracker/backend.log
tail -f ~/Library/Logs/chicago-property-tracker/tunnel.err.log

# Find the current tunnel URL (it changes only on Mac reboot)
grep -oE 'https://[a-z-]+\.trycloudflare\.com' \
  ~/Library/Logs/chicago-property-tracker/tunnel.err.log | tail -1
```

## Stop

```bash
launchctl bootout gui/$(id -u)/com.chicagopropertytracker.backend
launchctl bootout gui/$(id -u)/com.chicagopropertytracker.tunnel
```

## Notes

- PostgreSQL is expected to be running via `brew services start postgresql@16`,
  which uses launchd internally.
- The Quick Tunnel URL changes on Mac reboot. For a permanent URL, use a
  named Cloudflare Tunnel + a domain.
