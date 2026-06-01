# Changelog

## v1.2.4 (2026-06-02)

### Fix
- **11 swallowed exceptions** — all `except: pass` now log with context or narrow exception type
- **3 silent `KeyboardInterrupt: pass`** — user now sees `[dim]Interrupted.[/dim]`
- **Hardcoded API URLs** — `BURNBOX_MAILTM_URL` / `BURNBOX_GUERRILLA_URL` env vars with fallback
- **Chained `.get("from", {}).get("address")`** — `isinstance` guard prevents crash on non-dict `from` field
- **`_poll_loop` deep nesting** — flattened with early `continue`, depth 6 → 3
- **`copy_to_clipboard` thin wrapper** — now logs warning on failure instead of silently returning False
- **Silent recovery** — all `except` blocks now include the caught error in log messages

### Meta
- ruff format applied project-wide (line-length 99)

## v1.2.3 (2026-06-01)

### Refactor
- Split `cli.py` monolith (410 lines) into `cli/{__init__,commands,render,poll}.py` — each module has one responsibility
- Extract shared `validate_url()` into `security.py` — deduplicated from `config.py` and `providers/utils.py`
- Extract shared `generate_id()` and `make_html_parser()` into `providers/utils.py` — deduplicated from both provider modules
- Move `select_provider()`, `get_provider_by_name()`, `close_unused()` into `providers/utils.py` — business logic no longer in CLI
- Remove dead `detect_expiry()` from `detectors/engine.py` — parsed expiry times but never surfaced to user
- Remove dead `_EXPIRY_PATTERN` regex from `detectors/engine.py`

### Fix
- Fix stale venv pointing to old project path (`Projects/py/` → `Projects/sec/`) — caused pytest-asyncio to not load (50 tests failing)

### Meta
- Change `authors` from "burnbox contributors" to "4bstr4ct" — trust signal for security tool
- Add `test_security.py` — 16 tests for URL validation (scheme, hostname, loopback, private IPs, labels)
- Add `test_sanitize.py` — 5 tests for path segment sanitization
- Remove `TestDetectExpiry` test class (4 tests) — tests for removed dead code

## v1.2.2 (2026-05-30)

### Fix
- Split `_render_message` into two Rich panels: message panel + Detected panel
- NumericOtpParser: UUID proximity filter (skip digits inside hex-dash patterns)
- Year exclusion (2024/2025) in NumericOtpParser
- html.unescape on displayed content
- Reset links shown as "verification links" (not mixed into Code line)

## v1.2.1 (2026-05-30)

### Fix
- `_ALPHANUMERIC_SIMPLE` regex requires min 1 digit — prevents pure-word false positives
- UUID fragment filtering (4+ hex-only dash groups excluded)
- html.unescape before detection + after html2text in providers
- CLI shows top-5 codes by confidence

## v1.2.0 (2026-05-29)

### Fix
- SSRF validation for custom URLs (private/reserved IP rejection)
- Atomic file creation with restrictive permissions (0o600, umask 0o077)
- OTP values masked in log output
- Async clipboard operations (asyncio.to_thread)
- Burn ordering: delete account first, then session file
- Jitter on retry backoff (0.5-1.0x)
- Deduplicate LINK_PATTERN to base.py
- Boost words for all 12 languages
- CLI input validation
- Public exports cleanup

## v1.1.0 (2026-05-28)

### Add
- OTP Parser Engine with 5 parsers (labeled, numeric, URL code, reset link, alphanumeric)
- 12-language support for OTP detection
- Confidence scoring with best-code selection
- Wayland/macOS/Windows clipboard support
- Desktop notifications
- Programmatic API (`burnbox.create()`)
- mypy strict + GitHub Actions CI
- PyPI Trusted Publisher

### Fix
- 10 bug fixes from initial release

## v1.0.0 (2026-05-27)

- Initial release
- Temporary email with burn-after-reading
- mail.tm and Guerrilla Mail providers
- Session persistence and resume
- Clipboard integration
