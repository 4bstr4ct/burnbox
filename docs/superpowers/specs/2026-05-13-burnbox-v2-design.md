# Burnbox v2 — Design Spec

## Goal

Transform burnbox from a single-provider temp email CLI into a multi-provider, async-first, publication-ready tool that auto-selects the best available free provider and gives users the ability to configure custom/self-hosted providers.

## Decisions

1. **Multi-provider with 3-tier extensibility**: built-in providers (Provider protocol) + config-provider (self-hosted clones via base_url) + entry points (plugins for custom APIs)
2. **Default provider selection via health check**: ping all providers in parallel at startup, pick the first alive one, fallback to next by priority
3. **No password on disk**: session stores address + account_id + token only. Token expires naturally. Resume works via token. Expired token = "start a new session"
4. **Async architecture**: `httpx.AsyncClient` + `asyncio`. Required because multi-provider health check is parallel by nature. Sync would mean 30s startup if first providers are dead
5. **Read-only mailbox**: no send/reply/forward. Auto-detect OTP codes and confirmation links in messages — highlight + auto-copy to clipboard when exactly one candidate found
6. **Three CLI commands**: `burnbox` (create + poll + burn), `burnbox address` (create + copy address + exit), `burnbox resume` (reconnect to live session). No standalone `burn` command — burning is implicit on exit without `--keep`
7. **Auto-copy address to clipboard**: default behavior on `burnbox` and `burnbox address`
8. **Public release later**: git initialized, README/LICENSE/CI after feature work is done

## Architecture

### Provider Layer

```
Provider (Protocol)
├── name: str
├── is_alive() -> bool              # async health check
├── register() -> ProviderSession   # create temp account
├── login(addr, pw) -> ProviderSession
├── fetch_messages(seen) -> list[InboxMessage]
├── delete_account(account_id) -> bool
└── supports_custom_url: bool        # True for mail.tm-compatible clones
```

**Built-in providers** (classes implementing Provider):
- `MailTmProvider` — https://api.mail.tm (current, JSON-LD/Hydra API)
- `MailGwProvider` — https://api.mail.gw (sister service, same API shape)
- `GuerrillaMailProvider` — guerrillamail.com (different API, different schema)
- `OneSecMailProvider` — 1secmail.com (simple REST)

**Config-provider**: when user sets `provider = "custom"` + `base_url` in config, `MailTmProvider` is instantiated with custom URL. This works because most self-hosted temp mail APIs are mail.tm forks.

**Entry points**: `burnbox.providers` entry point group. User registers a class via `pyproject.toml` / `setup.cfg`. Burnbox discovers at startup via `importlib.metadata`.

### Session Model

```python
@dataclass(frozen=True)
class Session:
    address: str
    account_id: str
    token: str
    provider_name: str       # which provider created this
    created_at: float         # time.time()
```

Saved to `~/.config/burnbox/session.json`. **No password field.**

Resume flow:
1. Load session → try `fetch_messages(set())` with stored token
2. If 401 → token expired → print "Session expired. Start fresh with `burnbox`" → delete session → exit
3. If success → enter poll loop

### Async Flow

```
burnbox CLI startup
  ├── Load config (TOML + env + CLI flags)
  ├── Discover providers (built-in + entry points)
  ├── If --provider specified → use that one
  │   └── If custom + base_url → MailTmProvider(url=base_url)
  └── Else → health-check all providers in parallel
      ├── asyncio.gather(*[p.is_alive() for p in providers])
      ├── Pick first alive by priority order
      └── If none alive → print error + exit
  ├── Register account → auto-copy address to clipboard
  ├── If command == "address" → print address → exit
  ├── Else → enter async poll loop
  │   ├── Fetch new messages (async)
  │   ├── Auto-detect codes → highlight + copy
  │   └── asyncio.sleep(poll_interval)
  └── On exit → burn account (unless --keep) → delete session
```

### Code/Link Detection

```python
OTP_PATTERNS = [
    r'\b\d{4,8}\b',                        # 4-8 digit codes
    r'(?:code|код|pin|otp)[\s:]*\d{4,8}',  # labeled codes (EN/RU)
]
LINK_PATTERN = r'https?://[^\s<>"\']+'      # URLs
```

Extraction rules:
1. Scan message text for OTP patterns + URLs
2. If exactly one OTP code found → copy to clipboard + highlight green
3. If multiple candidates → highlight all in yellow, don't touch clipboard
4. If confirmation link found alongside code → show link below code
5. Never overwrite clipboard if ambiguous

### Config (TOML)

```toml
# ~/.config/burnbox.toml

[provider]
default = "mailtm"          # or skip for auto-select
custom_url = ""             # for self-hosted mail.tm clones

[polling]
interval = 5.0              # seconds
timeout = 10.0              # HTTP timeout

[output]
copy_address = true          # auto-copy address to clipboard
copy_code = true             # auto-copy detected OTP codes
```

Env var overrides: `BURNBOX_PROVIDER`, `BURNBOX_POLL_INTERVAL`, `BURNBOX_TIMEOUT`, `BURNBOX_CUSTOM_URL`.

## File Structure (new/modified)

```
burnbox/
├── __init__.py              # public API exports (updated)
├── __main__.py              # asyncio entry point (NEW)
├── account.py               # REMOVE — absorbed into providers
├── api.py                   # REMOVE — replaced by async_api.py
├── async_api.py             # NEW — httpx.AsyncClient with retry
├── cli.py                   # REWRITE — async CLI, 3 commands
├── client.py                # REWRITE — async BurnBoxClient
├── config.py                # EXPAND — TOML config + env vars
├── detectors.py             # NEW — OTP/link detection + clipboard
├── exceptions.py            # KEEP — add ProviderError, SessionError
├── messages.py              # REWRITE — async MessageService
├── models.py                # EXPAND — Session dataclass, ProviderInfo
├── schemas.py               # KEEP — mail.tm-specific, move to providers/
├── providers/
│   ├── __init__.py          # NEW — Provider protocol + registry
│   ├── base.py              # NEW — Provider protocol definition
│   ├── registry.py          # NEW — provider discovery + health check
│   ├── mailtm.py            # NEW — MailTmProvider (current logic migrated)
│   ├── mailgw.py            # NEW — MailGwProvider
│   ├── guerrillamail.py     # NEW — GuerrillaMailProvider
│   └── onesecmail.py        # NEW — OneSecMailProvider
tests/
├── conftest.py              # NEW — shared async fixtures
├── test_async_api.py        # NEW
├── test_client.py           # REWRITE for async
├── test_config.py           # NEW / expanded
├── test_detectors.py        # NEW
├── test_providers.py        # NEW — per-provider tests
├── test_registry.py         # NEW — health check + selection
├── test_session.py          # NEW — session persistence without password
├── test_cli.py              # NEW — CLI command tests
├── test_models.py           # EXPAND
├── test_services.py         # REWRITE
├── test_account.py          # REMOVE
├── test_api.py              # REMOVE
├── test_api_request.py      # REMOVE
```
