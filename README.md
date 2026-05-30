# burnbox

**Temporary email that burns after reading.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

burnbox creates a disposable email address, watches for incoming messages, auto-detects OTP codes, copies them to your clipboard — then burns the account when you're done.

Requires Python >= 3.10.

## Install

```bash
pip install burnbox
```

Or with [pipx](https://pypa.github.io/pipx/) (recommended for CLI tools):

```bash
pipx install burnbox
```

## How it works

1. **Register** — burnbox creates a temporary email account
2. **Poll** — watches for incoming messages every few seconds
3. **Detect** — finds OTP codes, verification links, and copies them to clipboard
4. **Burn** — deletes the account and session on exit (Ctrl+C)

The `--keep` flag preserves the account for later use with `burnbox resume`.

## Quick start

```bash
$ burnbox
```

That's it. You'll get a temp address, it auto-copies to clipboard, and burnbox watches for messages. When a verification code arrives, it's detected and copied. Press Ctrl+C to exit — the account is deleted automatically.

```
╭─────────── burnbox ───────────╮
│ Temp email that burns after   │
│ reading                       │
╰───────────────────────────────╯

  Provider: mailtm
  Address:  k7x9m2@example.com
  Address copied to clipboard

  Ctrl+C to exit and burn · --keep to preserve · burnbox resume
```

## CLI usage

| Command | Description |
|---|---|
| `burnbox` | Create temp email, watch for messages, burn on exit |
| `burnbox address` | Generate a temp email address and exit (account is burned immediately) |
| `burnbox resume` | Reconnect to the last saved session |

### Options

```
--provider       Provider: mailtm, mailgw, dropmail, guerrillamail
--poll, -p       Polling interval in seconds (default: 5)
--timeout, -t    HTTP request timeout (default: 10)
--keep, -k       Keep account alive after exit
--version, -v    Show version
--help, -h       Show help
```

### Examples

```bash
# Use a specific provider
burnbox --provider guerrillamail

# Keep account alive for later resume
burnbox --keep

# Resume a kept session
burnbox resume

# One-shot: just get a temp address (burned immediately)
burnbox address
```

## Programmatic API

Use burnbox as a Python library:

```python
import asyncio
import burnbox

async def main():
    box = await burnbox.create()
    async with box:
        print(f"Address: {box.address}")
        msg = await box.wait_for_message(timeout=60)
        if msg:
            print(f"Code: {msg.best_code}")
            print(f"From: {msg.sender}")
        # Account auto-burns on exit

asyncio.run(main())
```

### API reference

- `burnbox.create(provider=None, config=None)` — Create a `BurnBox` instance (await it first, then use as context manager)
- `box.address` — The temp email address
- `box.fetch_new()` — Fetch new messages
- `box.wait_for_message(timeout=60)` — Wait for the first message (returns `None` on timeout)
- `box.messages()` — Async iterator yielding messages as they arrive
- `box.burn()` — Delete the account manually
- `msg.id`, `msg.sender`, `msg.subject` — Message metadata
- `msg.content` — Message body as plain text
- `msg.best_code` — Highest-confidence OTP code detected (string or `None`)
- `msg.codes` — All detected codes as `CodeMatch` objects (`.value`, `.confidence`, `.kind`)
- `msg.links` — All detected links

## Configuration

Config file: `~/.config/burnbox.toml`

```toml
[provider]
default = "mailtm"             # Preferred provider
custom_url = "https://..."     # Custom API URL for mailtm/mailgw

[polling]
interval = 5.0                 # Seconds between polls
timeout = 10.0                  # HTTP timeout

[output]
copy_address = true             # Copy address to clipboard
copy_code = true                # Copy OTP codes to clipboard
notifications = true            # Desktop notifications on OTP
```

Environment variables override the config:

```bash
BURNBOX_PROVIDER=guerrillamail
BURNBOX_POLL_INTERVAL=3
BURNBOX_TIMEOUT=15
BURNBOX_CUSTOM_URL=https://...
```

## Providers

| Provider | Auth | Delete account | Domains | Custom URL |
|---|---|---|---|---|
| **mail.tm** | Register + token | Yes | Multiple | Yes |
| **mail.gw** | Register + token | Yes | Multiple | Yes |
| **dropmail** | Session-based (auto-expire) | Session expires | dropmail.me, 10mail.org, etc | No |
| **guerrillamail** | Session-based | Yes | sharklasers.com, grr.la, etc | No |

burnbox automatically selects the first available provider with a health check. If one is down, it falls back to the next.

## OTP Detection

burnbox detects verification codes from incoming emails using a multi-parser engine:

- **Labeled OTP** — "code: 1234", "Your verification code: 8472", "Ваш код: 5531", etc.
- **Alphanumeric codes** — Recovery codes, backup keys (e.g., `A1B2-C3D4-E5F6`)
- **URL-embedded codes** — `?code=`, `?token=`, `?otp=` in links
- **Reset/verify links** — Password reset, account verification URLs
- **Numeric OTP** — Standalone digit clusters with context-aware confidence boosting

Supports 12 languages for label detection: English, Russian, German, French, Spanish, Portuguese, Chinese, Japanese, Korean, Hindi, Arabic, Turkish. Context-aware confidence boosting is available for English and Russian; other languages use label-matching only.

Each match has a **confidence score** (0–1). The highest-confidence code is auto-copied to your clipboard.

## Plugin system

Add custom providers via Python entry points:

```python
# my_provider.py
from burnbox.providers.base import Provider
from burnbox.models import Session, InboxMessage

class MyProvider:
    name = "myprovider"
    supports_custom_url = False

    async def is_alive(self) -> bool:
        # Check if the provider API is reachable

    async def register(self) -> Session:
        # Create a new temp email account, return Session

    async def restore(self, session: Session) -> None:
        # Restore auth state from a saved session

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        # Fetch new (unseen) messages

    async def delete_account(self, account_id: str) -> bool:
        # Delete the account, return True on success

    async def aclose(self) -> None:
        # Close the HTTP client
```

```toml
# pyproject.toml
[project.entry-points."burnbox.providers"]
myprovider = "my_provider:MyProvider"
```

After `pip install`, burnbox discovers your provider automatically.

## Security considerations

- OTP codes transit through third-party email providers. Only use burnbox for non-sensitive verifications.
- Session files are stored with 0600 permissions at `~/.config/burnbox/session.json`.
- Accounts are deleted ("burned") on exit by default. Use `--keep` only if you need persistence.

## Troubleshooting

- **Clipboard not working on Linux**: Install `xclip` or `xsel` (X11) or `wl-clipboard` (Wayland).
- **All providers down**: burnbox falls back to trying providers even if health checks fail. Check your network.
- **"Session expired" on resume**: The temp email account has expired. Start a new one with `burnbox`.

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run mypy burnbox/
uv run pytest
```

## License

MIT
