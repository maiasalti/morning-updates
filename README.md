# AI & Cancer Research Biweekly Digest

A self-running email digest that fetches the latest AI/ML and positive cancer research news, summarizes it with Claude claude-opus-4-6, and delivers a clean HTML email to your inbox every 2 days via GitHub Actions.

---

## What it does

- **Runs automatically** every 2 days (and can be triggered manually anytime)
- **Fetches** the latest AI/ML news and positive cancer research stories from NewsAPI
- **Summarizes** everything with Claude claude-opus-4-6 — smart, warm, human tone
- **Sends** a dark-themed HTML email via Gmail SMTP

### Email sections
1. **AI & ML** — Top 5 stories: model releases, research breakthroughs, company moves, policy
2. **Cancer Research** — Up to 4 genuinely positive stories only. If nothing qualifies, it says so honestly.

---

## Setup (one-time, ~10 minutes)

### Step 1 — Get your API keys & credentials

#### Anthropic API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in (or create an account)
3. Navigate to **API Keys** → **Create Key**
4. Copy the key — it starts with `sk-ant-...`
5. Add a small amount of credit under **Billing** (Claude claude-opus-4-6 is very cheap for this use case — expect < $0.10 per run)

#### NewsAPI Key
1. Go to [newsapi.org/register](https://newsapi.org/register)
2. Sign up for a free account
3. Your API key is shown immediately on the dashboard
4. Copy it — free tier allows 100 requests/day, which is plenty

#### Gmail App Password
You cannot use your regular Gmail password. You need a Google **App Password**:
1. Make sure [2-Step Verification is enabled](https://myaccount.google.com/security) on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Select app: **Mail** → Select device: **Other** → type "GitHub Digest" → click **Generate**
4. Copy the 16-character password (e.g., `abcd efgh ijkl mnop` — include no spaces when you use it)

---

### Step 2 — Create the GitHub repo and push

```bash
# Navigate to the project folder
cd ai-cancer-digest

# Initialize git and push to a new GitHub repo
git init
git add .
git commit -m "Initial commit: AI & Cancer Research digest"

# Create the repo on GitHub (requires gh CLI — install at cli.github.com)
gh repo create ai-cancer-digest --public --source=. --remote=origin --push

# If you don't have gh CLI, create the repo manually at github.com/new
# then run:
# git remote add origin https://github.com/YOUR_USERNAME/ai-cancer-digest.git
# git branch -M main
# git push -u origin main
```

---

### Step 3 — Add the 5 secrets to GitHub

1. Go to your repo on GitHub: `github.com/YOUR_USERNAME/ai-cancer-digest`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each of the following:

| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |
| `NEWS_API_KEY` | Your NewsAPI key |
| `EMAIL_SENDER` | Your Gmail address (e.g. `you@gmail.com`) |
| `EMAIL_PASSWORD` | Your 16-character Gmail App Password (no spaces) |
| `EMAIL_RECIPIENT` | Email address to send the digest to |

> `EMAIL_SENDER` and `EMAIL_RECIPIENT` can be the same address (send to yourself).

---

### Step 4 — Enable Actions and do a manual test run

1. Go to your repo → click the **Actions** tab
2. If prompted, click **"I understand my workflows, go ahead and enable them"**
3. In the left sidebar, click **AI & Cancer Research Digest**
4. Click **Run workflow** → **Run workflow** (green button)
5. Watch the run — it takes ~30–60 seconds
6. Check your inbox for the email!

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
| Delivery time | `digest.yml` → cron schedule (`0 9 */2 * *` = 9am UTC every 2 days) |
| Number of AI stories | `summarize_ai_news()` → change `max_tokens` or the prompt |
| News topics / search terms | `main()` → `ai_query` and `cancer_query` strings |
| Email design | `build_html()` → all inline CSS |
| Claude model | `MODEL` constant at the top of `digest.py` |

---

## Troubleshooting

**Email not arriving?**
- Check your spam folder
- Verify `EMAIL_PASSWORD` is the App Password, not your Gmail login password
- Make sure 2-Step Verification is on for your Google account

**NewsAPI returns 0 articles?**
- The script automatically widens the search window from 2 days to 4 days
- Free tier does not allow searching articles older than 1 month

**Claude returns invalid JSON?**
- Rare but possible — re-run the workflow manually; it's a transient issue
- The `_clean_json()` helper strips markdown fences if Claude wraps its response

**Actions workflow not running on schedule?**
- GitHub may delay scheduled workflows by up to 1 hour during high-traffic periods
- Repos with no activity for 60 days have scheduled workflows paused — push a commit to reactivate
