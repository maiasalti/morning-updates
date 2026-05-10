# Daily Stocks, AI & Biotech Digest

A self-running email digest that fetches AI/tech stock movements, AI & tech news, and biotech advancements, summarizes everything with Claude, and delivers a clean HTML email to your inbox **every morning at 10am Singapore time** via GitHub Actions.

---

## What it does

- **Runs automatically** every day at 10:00 AM SGT (02:00 UTC) — also triggerable manually
- **Pulls stock data** for ~60 AI/tech tickers from Yahoo Finance (free, no API key)
- **Fetches** the latest AI/tech and biotech news from NewsAPI
- **Summarizes** with Claude — smart, warm, human tone, no hype
- **Sends** a dark-themed HTML email via Gmail SMTP

### Email sections

1. **Stocks** — 20-stock watchlist with last-close prices and 24h % change, plus the top 10 biggest movers from a broader ~60-ticker AI/tech universe (by absolute % move, so big drops surface too)
2. **AI & Tech** — Top 5 stories: model releases, chip development, data centers, AI infrastructure, policy
3. **Biotech** — Up to 5 stories. Prioritizes AI × biotech crossover (AI-discovered drugs, AlphaFold-style breakthroughs, computational biology), fills with general biotech advancements (clinical trial wins, FDA approvals, gene editing)

### Stock universe

**Daily watchlist (20):**
NVDA, MSFT, GOOGL, META, AMZN, TSM, AVGO, AMD, ASML, ARM, MU, SMCI, VRT, ANET, DELL, ORCL, PLTR, CRM, NOW, SNOW

**Plus ~40 more for the movers scan:**
AAPL, TSLA, IBM, INTC, QCOM, TXN, NXPI, MRVL, ON, LRCX, KLAC, AMAT, ADI, MCHP, SWKS, GFS, CSCO, JNPR, NTAP, PSTG, HPE, MDB, DDOG, NET, ESTC, AI, PATH, BBAI, SOUN, IONQ, QBTS, RGTI, NBIS, COHR, ANSS, SYM, DUOL, U, TEM, RXRX

---

## Setup (one-time, ~10 minutes)

### Step 1 — Get your API keys & credentials

#### Anthropic API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in (or create an account)
3. Navigate to **API Keys** → **Create Key**
4. Copy the key — it starts with `sk-ant-...`
5. Add a small amount of credit under **Billing** (Claude is very cheap for this — expect < $0.10 per run)

#### NewsAPI Key
1. Go to [newsapi.org/register](https://newsapi.org/register)
2. Sign up for a free account
3. Your API key is shown immediately on the dashboard
4. Free tier allows 100 requests/day — plenty for daily runs

#### Gmail App Password
You cannot use your regular Gmail password. You need a Google **App Password**:
1. Make sure [2-Step Verification is enabled](https://myaccount.google.com/security) on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Select app: **Mail** → Select device: **Other** → type "GitHub Digest" → click **Generate**
4. Copy the 16-character password (e.g., `abcd efgh ijkl mnop` — remove spaces when you use it)

> No extra key for stock data — Yahoo Finance is free via `yfinance`.

---

### Step 2 — Add the 5 secrets to GitHub

1. Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each:

| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |
| `NEWS_API_KEY` | Your NewsAPI key |
| `EMAIL_SENDER` | Your Gmail address (e.g. `you@gmail.com`) |
| `EMAIL_PASSWORD` | Your 16-character Gmail App Password (no spaces) |
| `EMAIL_RECIPIENT` | Email address to send the digest to |

> `EMAIL_SENDER` and `EMAIL_RECIPIENT` can be the same (send to yourself).

---

### Step 3 — Enable Actions and do a manual test run

1. Go to your repo → **Actions** tab
2. If prompted, click **"I understand my workflows, go ahead and enable them"**
3. In the left sidebar, click **Daily Stocks, AI & Biotech Digest**
4. Click **Run workflow** → **Run workflow** (green button)
5. The run takes ~30–60 seconds
6. Check your inbox

---

## Project structure

```
ai-cancer-digest/
├── digest/
│   └── digest.py          # Main script
├── .github/
│   └── workflows/
│       └── digest.yml     # GitHub Actions cron workflow
├── requirements.txt
└── README.md
```

---

## Customization

| Thing to change | Where |
|---|---|
| Delivery time | `digest.yml` → cron schedule (currently `0 2 * * *` = 02:00 UTC = 10am SGT) |
| Watchlist or universe | `digest.py` → `WATCHLIST` and `EXTRA_UNIVERSE` constants |
| News topics / search terms | `main()` → `ai_query` and `biotech_query` strings |
| Number of stories per section | Each `summarize_*()` function |
| Email design | `build_html()` → all inline CSS |
| Claude model | `MODEL` constant at the top of `digest.py` |

### Changing the timezone

Edit the cron line in `.github/workflows/digest.yml`. GitHub Actions cron is always in **UTC**, so:

| Local 10am | Cron expression |
|---|---|
| Singapore (UTC+8) | `0 2 * * *` |
| London (UTC+0) | `0 10 * * *` |
| New York (UTC-5) | `0 15 * * *` |
| Pacific (UTC-8) | `0 18 * * *` |

For DST-aware locations, pick whichever offset matters more to you.

---

## Troubleshooting

**Email not arriving?**
- Check your spam folder
- Verify `EMAIL_PASSWORD` is the App Password, not your Gmail login password
- Make sure 2-Step Verification is on for your Google account

**NewsAPI returns 0 articles?**
- The script auto-widens the search window from 1 day to 3 days
- Free tier doesn't allow searching articles older than ~1 month

**Stock data missing for some tickers?**
- Yahoo Finance occasionally rate-limits. Failed tickers are logged and skipped — the rest still come through
- Ticker symbols change occasionally (e.g., FB → META). Update `WATCHLIST` if you hit this

**Claude returns invalid JSON?**
- Rare but possible — re-run the workflow manually
- The `_clean_json()` helper strips markdown fences if Claude wraps its response

**Workflow not running on schedule?**
- GitHub may delay scheduled workflows by up to 1 hour during high-traffic periods
- Repos with no activity for 60 days have scheduled workflows paused — push a commit to reactivate

**Weekend runs show "stale" stock data?**
- That's expected — the email shows the last US trading day's close. The "Last close" date in the email tells you exactly which day
