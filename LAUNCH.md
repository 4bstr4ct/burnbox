# burnbox launch plan

## pre-launch checklist

- [ ] GIF demo in README (asciinema recording: burnbox full cycle with OTP)
- [ ] CONTRIBUTING.md
- [ ] Awesome lists PRs: awesome-cli-apps, awesome-python, awesome-privacy
- [ ] pip install burnbox works flawlessly on linux/macos/windows
- [ ] be active in r/commandline, r/Python, HN comments 1-2 weeks before launch

## demo gif script

1. `burnbox` — address created, copied to clipboard
2. sign up on a real site with the temp address (or send via SMTP script as fallback)
3. OTP arrives — burnbox shows "Codes: 482951", "Copied code: 482951"
4. Ctrl+C — "Burned."
5. terminal ~80 cols, font large, 15-20 sec max

## channels (priority order)

### 1. show hn — main hit

**title options:**
- `Show HN: Burnbox – a CLI that gives you a disposable email, auto-copies OTPs, then burns the account`
- `Show HN: CLI tool for disposable email with OTP auto-detection and auto-burn`

**rules:**
- post 8-10 AM ET, tuesday-thursday
- link to github, not landing page
- be in comments 2+ hours, answer everything
- admit limitations honestly (few providers, disposable domains)
- never ask friends to upvote

**what works (from successful posts):**
- descriptive title > clever branding
- "I built" framing = authenticity
- one-liner install: `pip install burnbox`
- GIF/screenshot in README = visual proof

### 2. dev.to article

**title:** "I Built a CLI That Gives You a Disposable Email, Auto-Copies OTPs, and Burns Itself — Here's Why"

**tags:** #showdev #python #cli #security #productivity

**structure:**
- pain point (2-3 para): every signup = spam, manual temp email, hunt for OTP
- solution (1-2 para): one command, auto-detect, auto-burn
- GIF demo
- how it works: OTP parser engine, 5 parsers, 12 langs, confidence scoring
- comparison table: burnbox vs tmpmail vs mailsy vs tema
- why generic OTP > per-service hardcoded
- quick start: pip install burnbox
- what's next: roadmap

### 3. reddit

**r/commandline** — text post, must list alternatives (tmpmail, mailsy, tema), comparison
**r/Python** — monthly showcase thread only, must include "what it does / target audience / comparison"
**r/opensource** — promotional flair, honest title
**r/privacy** — angle: disposable email for privacy, no browser needed

**reddit strategy:**
- stagger posts 1-2 days between platforms
- each post = different angle per audience
- engage heavily in comments 2-3 hours after posting
- build karma 1-2 weeks before launch

### 4. awesome lists (long-tail passive traffic)

- awesome-cli-apps (github.com/aharris88/awesome-cli-apps)
- awesome-python (github.com/vinta/awesome-python)
- awesome-privacy (github.com/pluja/awesome-privacy)
- single accepted PR = years of passive traffic

### 5. newsletters

- Console (console.substack.com) — specifically covers CLI tools, submit on website
- PyCoder's Weekly (pycoders.com/submit)
- Python Weekly (pythonweekly.com)
- TLDR newsletter (tldr.tech/submit) — dev tools section

### 6. other channels

- Lobsters (lobste.rs) — need invite, tag: python/cli/security/privacy
- Fosstodon / fediverse — hashtags #Python #CLI #OpenSource #Privacy
- Product Hunt — low priority, CLI tools underperform there
- Discord: Python Discord showcase channel

## launch timeline

| day | action |
|---|---|
| -4 to -2 | polish README, record GIF, awesome lists PRs, CONTRIBUTING.md |
| -1 | soft launch to 5-10 friends, write dev.to draft |
| **day 0 (tue/wed)** | 8AM ET: Show HN → 9AM: r/commandline → 10AM: dev.to publish |
| +1 | r/opensource, lobsters, console newsletter submit |
| +2 to +7 | r/privacy, r/Python showcase, fosstodon, newsletter submissions |

## key principles

- README is the landing page — every channel drives there
- people try `pip install burnbox` in 10 seconds = win
- reduce friction to zero
- honest about limitations > inflated claims
- engage in comments, don't drop links and run
