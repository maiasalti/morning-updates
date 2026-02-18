"""
AI & Cancer Research Biweekly Digest
Fetches news, summarizes with Claude, sends via Gmail SMTP.
"""

import json
import logging
import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config — all values come from environment variables / GitHub Secrets
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NEWS_API_KEY = os.environ["NEWS_API_KEY"]
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECIPIENT = os.environ["EMAIL_RECIPIENT"]

NEWSAPI_URL = "https://newsapi.org/v2/everything"
MODEL = "claude-opus-4-6"


# ---------------------------------------------------------------------------
# News fetching
# ---------------------------------------------------------------------------

def fetch_articles(query: str, days_back: int = 2, page_size: int = 25) -> list[dict]:
    """Fetch articles from NewsAPI and return the raw article list."""
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    params = {
        "q": query,
        "from": from_date,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": page_size,
        "apiKey": NEWS_API_KEY,
    }
    resp = requests.get(NEWSAPI_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {data.get('message', 'unknown error')}")
    articles = data.get("articles", [])
    # Drop articles with missing essentials
    articles = [a for a in articles if a.get("title") and a.get("url")]
    return articles


def articles_to_prompt_text(articles: list[dict]) -> str:
    """Render article list as numbered text for a Claude prompt."""
    lines = []
    for i, a in enumerate(articles, 1):
        title = a.get("title", "No title")
        desc = (a.get("description") or a.get("content") or "").strip()[:400]
        url = a.get("url", "")
        source = a.get("source", {}).get("name", "Unknown")
        lines.append(
            f"{i}. [{source}] {title}\n"
            f"   {desc}\n"
            f"   URL: {url}"
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Claude summarization
# ---------------------------------------------------------------------------

def _clean_json(text: str) -> str:
    """Strip markdown code fences if Claude wrapped the JSON in them."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening ``` line and the closing ``` line
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return text


def summarize_ai_news(articles: list[dict]) -> list[dict]:
    """
    Ask Claude to select and summarize the top 5 AI/ML stories.
    Returns a list of 5 story dicts with keys: title, summary, url, source.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are the editor of a smart, widely-read AI digest. Below are raw news articles from the last 48 hours about artificial intelligence and machine learning.

Your task: Pick the 5 most significant stories — model releases, research breakthroughs, company moves, policy shifts, interesting technical papers. For each, write a short, punchy 2-3 sentence summary in a warm, human voice. Be direct. No hype, no corporate speak.

Return ONLY valid JSON — a list of exactly 5 objects. Each object must have:
  - "title": a short, punchy headline you write (NOT the original title)
  - "summary": 2-3 sentences, smart and conversational
  - "url": the original article URL (copy exactly)
  - "source": the news source name (copy exactly)

Articles:
{articles_to_prompt_text(articles)}

Return only the JSON array. No markdown fences, no explanation, no preamble."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = _clean_json(message.content[0].text)
    stories = json.loads(raw)
    if not isinstance(stories, list):
        raise ValueError(f"Expected list from Claude, got: {type(stories)}")
    return stories[:5]


def summarize_cancer_news(articles: list[dict]) -> dict:
    """
    Ask Claude to identify genuinely positive cancer research stories.
    Returns {"stories": [...], "editor_note": str|None}.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are the editor of a cancer research digest. Your readers are smart, hopeful people who want real progress — not spin.

Below are raw news articles from the last 48 hours about cancer research.

Your task: Identify up to 4 stories that are GENUINELY positive or promising:
  ✓ Include: successful clinical trials, FDA/EMA drug approvals, new therapies showing real efficacy data, meaningful survivorship milestones, early breakthroughs with actual results
  ✗ Exclude: mortality statistics, tragic stories, "researchers hope someday..." fluff with no data, fundraising announcements, awareness campaigns

If fewer than 4 genuinely positive stories exist, include only the real ones. If NONE qualify, return an empty list and write an honest, warm editor's note.

Return ONLY valid JSON — an object with exactly these keys:
  - "stories": list of story objects (may be empty)
  - "editor_note": if stories is empty, 1-2 honest warm sentences for readers. Otherwise null.

Each story object must have:
  - "title": a hopeful but honest headline you write
  - "summary": 2-3 sentences, warm and grounded in actual findings
  - "url": the original article URL (copy exactly)
  - "source": the news source name (copy exactly)

Articles:
{articles_to_prompt_text(articles)}

Return only the JSON object. No markdown fences, no explanation."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = _clean_json(message.content[0].text)
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError(f"Expected dict from Claude, got: {type(result)}")
    result.setdefault("stories", [])
    result.setdefault("editor_note", None)
    return result


# ---------------------------------------------------------------------------
# HTML email builder
# ---------------------------------------------------------------------------

def _story_card(story: dict, index: int, accent: str) -> str:
    title = story.get("title", "Untitled")
    summary = story.get("summary", "")
    url = story.get("url", "#")
    source = story.get("source", "")
    return f"""
        <div style="margin-bottom:28px; padding-bottom:24px; border-bottom:1px solid #222222;">
          <p style="margin:0 0 6px 0; color:#666666; font-size:11px; text-transform:uppercase;
                    letter-spacing:0.1em; font-weight:600;">{index} &nbsp;·&nbsp; {source}</p>
          <h3 style="margin:0 0 10px 0; font-size:17px; font-weight:600; line-height:1.4; color:#f0f0f0;">
            <a href="{url}" style="color:#f0f0f0; text-decoration:none;">{title}</a>
          </h3>
          <p style="margin:0 0 12px 0; font-size:14px; line-height:1.7; color:#aaaaaa;">{summary}</p>
          <a href="{url}" style="color:{accent}; font-size:13px; text-decoration:none;
                                 font-weight:500;">Read more &rarr;</a>
        </div>"""


def build_html(ai_stories: list[dict], cancer_data: dict, date_str: str) -> str:
    ai_cards = "".join(
        _story_card(s, i + 1, "#7eb8f7") for i, s in enumerate(ai_stories)
    )

    cancer_stories = cancer_data.get("stories", [])
    editor_note = cancer_data.get("editor_note")

    if cancer_stories:
        cancer_body = "".join(
            _story_card(s, i + 1, "#4ade80") for i, s in enumerate(cancer_stories)
        )
    else:
        note = editor_note or (
            "No genuinely positive cancer research stories surfaced this cycle. "
            "We'd rather say nothing than fill space with noise. Check back in two days."
        )
        cancer_body = (
            f'<p style="color:#888888; font-size:14px; line-height:1.7; '
            f'font-style:italic; margin:0;">{note}</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI &amp; Cancer Research Digest &mdash; {date_str}</title>
</head>
<body style="margin:0; padding:0; background-color:#0d0d0d;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#0d0d0d;">
    <tr>
      <td align="center" style="padding:40px 16px 60px 16px;">
        <table role="presentation" style="max-width:600px; width:100%;"
               cellpadding="0" cellspacing="0">

          <!-- ── HEADER ──────────────────────────────────────────── -->
          <tr>
            <td style="background: linear-gradient(135deg, #0f1b35 0%, #0a1628 60%, #071020 100%);
                        border-radius:12px 12px 0 0; padding:44px 44px 36px 44px;">
              <p style="margin:0 0 10px 0; color:#7eb8f7; font-size:11px;
                         letter-spacing:0.15em; text-transform:uppercase; font-weight:700;">
                Biweekly Digest
              </p>
              <h1 style="margin:0 0 8px 0; color:#ffffff; font-size:30px;
                          font-weight:700; line-height:1.15; letter-spacing:-0.02em;">
                AI &amp; Cancer Research
              </h1>
              <p style="margin:0; color:#5a6a82; font-size:14px;">{date_str}</p>
            </td>
          </tr>

          <!-- ── INTRO BAR ───────────────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:18px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <p style="margin:0; color:#666666; font-size:13px; line-height:1.65;">
                What happened in the last 48 hours that's worth your attention.
                Two topics, curated by AI, zero noise.
              </p>
            </td>
          </tr>

          <!-- ── SECTION 1: AI/ML ────────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:36px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="border-left:3px solid #7eb8f7; padding-left:16px;">
                <p style="margin:0 0 3px 0; color:#7eb8f7; font-size:10px;
                           letter-spacing:0.14em; text-transform:uppercase; font-weight:700;">
                  Section 01
                </p>
                <h2 style="margin:0; color:#f0f0f0; font-size:20px; font-weight:700;">
                  AI &amp; Machine Learning
                </h2>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background-color:#111111; padding:28px 44px 20px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              {ai_cards}
            </td>
          </tr>

          <!-- ── GRADIENT DIVIDER ────────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:4px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="height:1px;
                           background:linear-gradient(90deg,transparent,#7eb8f7 30%,#4ade80 70%,transparent);">
              </div>
            </td>
          </tr>

          <!-- ── SECTION 2: CANCER RESEARCH ─────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:36px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="border-left:3px solid #4ade80; padding-left:16px;">
                <p style="margin:0 0 3px 0; color:#4ade80; font-size:10px;
                           letter-spacing:0.14em; text-transform:uppercase; font-weight:700;">
                  Section 02
                </p>
                <h2 style="margin:0 0 4px 0; color:#f0f0f0; font-size:20px; font-weight:700;">
                  Cancer Research
                </h2>
                <p style="margin:0; color:#555555; font-size:12px;">
                  Positive &amp; promising news only &mdash; real progress, honest reporting.
                </p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background-color:#111111; padding:28px 44px 40px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              {cancer_body}
            </td>
          </tr>

          <!-- ── FOOTER ──────────────────────────────────────────── -->
          <tr>
            <td style="background-color:#0a0a0a; border:1px solid #181818;
                        border-radius:0 0 12px 12px; padding:28px 44px;">
              <p style="margin:0 0 8px 0; color:#333333; font-size:12px;
                         line-height:1.6; text-align:center;">
                Powered by
                <a href="https://newsapi.org" style="color:#3d3d3d; text-decoration:none;">NewsAPI</a>
                &nbsp;+&nbsp;
                <a href="https://anthropic.com" style="color:#3d3d3d; text-decoration:none;">Claude claude-opus-4-6</a>
                &nbsp;&middot;&nbsp; Runs every 2 days via GitHub Actions
              </p>
              <p style="margin:0; color:#252525; font-size:11px; text-align:center;">
                You're receiving this because you built it. Nice work.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------

def send_email(subject: str, html_body: str) -> None:
    """Send the HTML digest via Gmail SMTP over SSL (port 465)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT

    plain = (
        "Your biweekly AI & Cancer Research digest is ready. "
        "Open in an HTML-capable email client to read it properly."
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())

    log.info("Email delivered to %s", EMAIL_RECIPIENT)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=== Digest run starting ===")

    # --- AI / ML news ---
    log.info("Fetching AI/ML articles...")
    ai_query = (
        '"artificial intelligence" OR "machine learning" OR "large language model" '
        'OR "GPT" OR "Claude AI" OR "Gemini" OR "AI model" OR "deep learning" '
        'OR "OpenAI" OR "foundation model" OR "AI regulation"'
    )
    ai_articles = fetch_articles(ai_query, days_back=2, page_size=25)
    if not ai_articles:
        log.warning("No AI/ML articles in last 2 days — widening to 4 days.")
        ai_articles = fetch_articles(ai_query, days_back=4, page_size=25)
    log.info("AI/ML articles fetched: %d", len(ai_articles))

    # --- Cancer research news ---
    log.info("Fetching cancer research articles...")
    cancer_query = (
        'cancer AND ('
        '"clinical trial" OR "FDA approval" OR "drug approved" OR '
        '"breakthrough therapy" OR "remission" OR "survival" OR '
        '"immunotherapy" OR "cancer treatment" OR "oncology" OR '
        '"tumor" OR "cancer drug" OR "cancer cure"'
        ')'
    )
    cancer_articles = fetch_articles(cancer_query, days_back=2, page_size=25)
    if not cancer_articles:
        log.warning("No cancer articles in last 2 days — widening to 4 days.")
        cancer_articles = fetch_articles(cancer_query, days_back=4, page_size=25)
    log.info("Cancer articles fetched: %d", len(cancer_articles))

    # --- Summarize ---
    log.info("Summarizing AI/ML stories with Claude...")
    ai_stories = summarize_ai_news(ai_articles)
    log.info("AI/ML stories selected: %d", len(ai_stories))

    log.info("Summarizing cancer research stories with Claude...")
    cancer_data = summarize_cancer_news(cancer_articles)
    log.info(
        "Cancer stories selected: %d | editor_note: %s",
        len(cancer_data.get("stories", [])),
        "yes" if cancer_data.get("editor_note") else "no",
    )

    # --- Build & send ---
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    subject = f"Your Digest: AI & Cancer Research — {date_str}"
    html_body = build_html(ai_stories, cancer_data, date_str)

    log.info("Sending email...")
    send_email(subject, html_body)

    log.info("=== Digest run complete ===")


if __name__ == "__main__":
    main()
