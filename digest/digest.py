"""
Daily Stocks, AI & Biotech Digest
Fetches stock movements, AI/tech news, and biotech news, summarizes with Claude,
and sends a clean HTML email via Gmail SMTP.
"""

import json
import logging
import os
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import requests
import yfinance as yf

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

# Ticker -> (full company name, brief description of what they do).
# Used for both the watchlist and the wider movers universe.
TICKER_INFO: dict[str, tuple[str, str]] = {
    # --- Watchlist (20) ---
    "NVDA":  ("NVIDIA",                    "AI chips & GPUs — the industry standard"),
    "MSFT":  ("Microsoft",                 "Azure cloud, OpenAI partnership, Copilot"),
    "GOOGL": ("Alphabet (Google)",         "Search, Gemini AI, Google Cloud"),
    "META":  ("Meta Platforms",            "Facebook/Instagram, Llama open-source AI"),
    "AMZN":  ("Amazon",                    "AWS cloud — major AI hosting platform"),
    "TSM":   ("Taiwan Semiconductor",      "Manufactures most of the world's AI chips"),
    "AVGO":  ("Broadcom",                  "Networking chips & custom AI accelerators"),
    "AMD":   ("Advanced Micro Devices",    "GPU/CPU rival to NVIDIA"),
    "ASML":  ("ASML Holding",              "Only maker of EUV chip-making machines"),
    "ARM":   ("Arm Holdings",              "Chip architecture for phones & AI devices"),
    "MU":    ("Micron Technology",         "Memory chips (DRAM, HBM for AI)"),
    "SMCI":  ("Super Micro Computer",      "AI server hardware"),
    "VRT":   ("Vertiv",                    "Data center cooling & power infrastructure"),
    "ANET":  ("Arista Networks",           "High-speed networking for data centers"),
    "DELL":  ("Dell Technologies",         "AI server systems"),
    "ORCL":  ("Oracle",                    "Enterprise software, Oracle Cloud, AI infra"),
    "PLTR":  ("Palantir Technologies",     "Government & enterprise AI data platforms"),
    "CRM":   ("Salesforce",                "CRM software with built-in AI"),
    "NOW":   ("ServiceNow",                "Enterprise workflow automation & AI agents"),
    "SNOW":  ("Snowflake",                 "Data warehouse for AI & analytics"),
    # --- Extended universe (movers scan) ---
    "AAPL":  ("Apple",                     "iPhones, on-device Apple Intelligence AI"),
    "TSLA":  ("Tesla",                     "EVs & autonomous driving AI"),
    "IBM":   ("IBM",                       "Enterprise AI (Watson, Granite), hybrid cloud"),
    "INTC":  ("Intel",                     "CPUs & chip foundry"),
    "QCOM":  ("Qualcomm",                  "Mobile chip leader (Snapdragon AI)"),
    "TXN":   ("Texas Instruments",         "Analog & embedded chips"),
    "NXPI":  ("NXP Semiconductors",        "Automotive & IoT chips"),
    "MRVL":  ("Marvell Technology",        "Data center & AI networking chips"),
    "ON":    ("ON Semiconductor",          "Power & sensor chips for autos & AI"),
    "LRCX":  ("Lam Research",              "Chip-making equipment"),
    "KLAC":  ("KLA Corp",                  "Chip inspection equipment"),
    "AMAT":  ("Applied Materials",         "Chip manufacturing equipment"),
    "ADI":   ("Analog Devices",            "High-performance analog chips"),
    "MCHP":  ("Microchip Technology",      "Embedded microcontrollers"),
    "SWKS":  ("Skyworks Solutions",        "Wireless/RF chips"),
    "GFS":   ("GlobalFoundries",           "Chip foundry"),
    "CSCO":  ("Cisco Systems",             "Networking gear & AI security"),
    "NTAP":  ("NetApp",                    "Enterprise data storage"),
    "PSTG":  ("Pure Storage",              "Flash storage for AI workloads"),
    "HPE":   ("Hewlett Packard Enterprise", "Servers & supercomputing"),
    "MDB":   ("MongoDB",                   "NoSQL database for AI apps"),
    "DDOG":  ("Datadog",                   "Cloud monitoring & observability"),
    "NET":   ("Cloudflare",                "CDN, edge compute, AI inference at edge"),
    "ESTC":  ("Elastic",                   "Search & observability platform"),
    "AI":    ("C3.ai",                     "Enterprise AI software"),
    "PATH":  ("UiPath",                    "Workflow automation & RPA"),
    "BBAI":  ("BigBear.ai",                "AI for defense & intelligence"),
    "SOUN":  ("SoundHound AI",             "Voice AI technology"),
    "IONQ":  ("IonQ",                      "Quantum computing"),
    "QBTS":  ("D-Wave Quantum",            "Quantum computing"),
    "RGTI":  ("Rigetti Computing",         "Quantum computing"),
    "NBIS":  ("Nebius Group",              "AI cloud infrastructure"),
    "COHR":  ("Coherent Corp",             "Photonics for data center networking"),
    "SNPS":  ("Synopsys",                  "Chip design software (acquired Ansys)"),
    "SYM":   ("Symbotic",                  "AI-powered warehouse robotics"),
    "DUOL":  ("Duolingo",                  "Language learning with AI tutors"),
    "U":     ("Unity Software",            "Game/3D engine with AI tools"),
    "TEM":   ("Tempus AI",                 "AI for healthcare & genomics"),
    "RXRX":  ("Recursion Pharmaceuticals", "AI-driven drug discovery"),
}

# 20-stock watchlist — shown every day in the main table
WATCHLIST = [
    "NVDA", "MSFT", "GOOGL", "META", "AMZN",
    "TSM", "AVGO", "AMD", "ASML", "ARM",
    "MU", "SMCI", "VRT", "ANET", "DELL",
    "ORCL", "PLTR", "CRM", "NOW", "SNOW",
]

# Additional tickers — pooled with the watchlist for the "Top Movers" scan.
# JNPR removed (acquired & delisted), ANSS replaced with SNPS (Synopsys, who bought it).
EXTRA_UNIVERSE = [
    "AAPL", "TSLA", "IBM", "INTC", "QCOM", "TXN", "NXPI", "MRVL", "ON",
    "LRCX", "KLAC", "AMAT", "ADI", "MCHP", "SWKS", "GFS",
    "CSCO", "NTAP", "PSTG", "HPE",
    "MDB", "DDOG", "NET", "ESTC",
    "AI", "PATH", "BBAI", "SOUN",
    "IONQ", "QBTS", "RGTI", "NBIS",
    "COHR", "SNPS", "SYM", "DUOL", "U",
    "TEM", "RXRX",
]

EXTENDED_UNIVERSE = WATCHLIST + EXTRA_UNIVERSE


# ---------------------------------------------------------------------------
# Stock fetching (yfinance — free, no API key)
# ---------------------------------------------------------------------------

def _fetch_market_cap(ticker: str) -> float | None:
    """Fetch market cap via yfinance fast_info. Returns None on failure."""
    try:
        mc = yf.Ticker(ticker).fast_info["market_cap"]
        return float(mc) if mc else None
    except Exception:
        return None


def fetch_stock_data(tickers: list[str]) -> tuple[list[dict], str | None]:
    """
    Batch-fetch the last several daily candles for each ticker, then compute
    the % change between the two most recent closes.

    Returns (results, as_of_date_str). Each result has:
        ticker, price, change_pct, change_abs, market_cap

    Tickers that fail (delisted, halted, no data) are silently dropped.
    """
    log.info("Fetching prices for %d tickers...", len(tickers))

    # Batch download is ~10x faster than per-ticker requests
    data = yf.download(
        tickers,
        period="5d",
        interval="1d",
        progress=False,
        group_by="ticker",
        auto_adjust=False,
        threads=True,
    )

    results: list[dict] = []
    as_of: str | None = None
    multi_ticker = len(tickers) > 1

    for ticker in tickers:
        try:
            t_data = data[ticker] if multi_ticker else data
            closes = t_data["Close"].dropna()
            if len(closes) < 2:
                log.warning("Not enough data for %s — skipping.", ticker)
                continue

            prev_close = float(closes.iloc[-2])
            last_close = float(closes.iloc[-1])
            change_abs = last_close - prev_close
            change_pct = (change_abs / prev_close) * 100

            if as_of is None:
                as_of = closes.index[-1].strftime("%b %d, %Y")

            results.append({
                "ticker": ticker,
                "price": last_close,
                "change_pct": change_pct,
                "change_abs": change_abs,
            })
        except Exception as e:
            log.warning("Failed to process %s: %s", ticker, e)
            continue

    log.info("Successfully fetched %d/%d tickers (as of %s)",
             len(results), len(tickers), as_of)

    # Market caps — parallel since fast_info is a per-ticker call
    log.info("Fetching market caps for %d tickers...", len(results))
    syms = [r["ticker"] for r in results]
    with ThreadPoolExecutor(max_workers=10) as ex:
        caps = list(ex.map(_fetch_market_cap, syms))
    for r, mc in zip(results, caps):
        r["market_cap"] = mc

    return results, as_of


def get_stock_summary() -> dict:
    """Return watchlist data and top-10 movers from the extended universe."""
    all_data, as_of = fetch_stock_data(EXTENDED_UNIVERSE)
    by_ticker = {d["ticker"]: d for d in all_data}

    # Preserve the order of the watchlist
    watchlist_data = [by_ticker[t] for t in WATCHLIST if t in by_ticker]

    # Top movers ranked by absolute % change (so big drops show up too)
    movers = sorted(all_data, key=lambda d: abs(d["change_pct"]), reverse=True)[:10]

    return {
        "watchlist": watchlist_data,
        "movers": movers,
        "as_of": as_of or "unknown",
    }


# ---------------------------------------------------------------------------
# News fetching
# ---------------------------------------------------------------------------

def fetch_articles(query: str, days_back: int = 1, page_size: int = 30) -> list[dict]:
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
        lines.append(f"{i}. [{source}] {title}\n   {desc}\n   URL: {url}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Claude summarization
# ---------------------------------------------------------------------------

def _clean_json(text: str) -> str:
    """Strip markdown code fences if Claude wrapped the JSON in them."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return text


def summarize_ai_news(articles: list[dict]) -> list[dict]:
    """
    Pick and summarize the top 5 AI/tech stories. Returns a list of 5 dicts
    with keys: title, summary, url, source.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are the editor of a smart, widely-read AI & tech digest. Below are raw news articles from the last 24 hours.

Your task: Pick the 5 most significant stories spanning AI/ML, semiconductors and chip development, data centers, AI infrastructure, and tech policy. Mix it up — don't make all 5 about the same company or theme. For each, write a short, punchy 2-3 sentence summary in a warm, human voice. Be direct. No hype, no corporate speak.

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


def summarize_biotech_news(articles: list[dict]) -> list[dict]:
    """
    Hybrid section: prioritize AI x biotech crossover, fill with general
    biotech advancements. Returns up to 5 dicts with keys:
    title, summary, url, source, category.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are the editor of a biotech digest for a sharp reader interested in BOTH AI x biotech crossover AND general biotech progress.

From the articles below (last 24 hours), pick up to 5 stories. Use this priority order:
1. **AI x Biotech crossover** — AI-discovered drugs, AlphaFold-style breakthroughs, computational biology, AI in medical diagnostics, ML-driven target discovery. Aim for at least 1-2 of these if any genuinely qualify.
2. **General biotech advancements** — clinical trial wins (with real efficacy data), FDA/EMA approvals, novel therapies, gene editing/CRISPR results, mRNA platforms, immunotherapies.

Skip noise: awareness campaigns, fundraising announcements, vague "researchers hope someday..." pieces with no data, mortality statistics.

Each summary 2-3 sentences, smart and grounded in actual findings. No hype.

Return ONLY valid JSON — a list of up to 5 objects. Each object must have:
  - "title": a punchy headline you write
  - "summary": 2-3 sentences
  - "url": the original article URL (copy exactly)
  - "source": the news source name (copy exactly)
  - "category": exactly "AI x Biotech" or "Biotech"

Articles:
{articles_to_prompt_text(articles)}

Return only the JSON array. No markdown fences, no explanation."""

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


# ---------------------------------------------------------------------------
# HTML email builder
# ---------------------------------------------------------------------------

def _format_market_cap(mc: float | None) -> str:
    """Format a market cap value as a short string ($2.94T, $356B, $42.1M)."""
    if not mc or mc <= 0:
        return "—"
    if mc >= 1e12:
        return f"${mc / 1e12:.2f}T"
    if mc >= 1e9:
        return f"${mc / 1e9:.1f}B"
    if mc >= 1e6:
        return f"${mc / 1e6:.0f}M"
    return f"${mc:,.0f}"


def _stock_row(item: dict) -> str:
    pct = item["change_pct"]
    is_up = pct >= 0
    color = "#4ade80" if is_up else "#f87171"
    arrow = "▲" if is_up else "▼"
    sign = "+" if is_up else ""
    ticker = item["ticker"]
    name, desc = TICKER_INFO.get(ticker, (ticker, ""))
    mc_str = _format_market_cap(item.get("market_cap"))

    descriptor_html = (
        f'<div style="color:#666666; font-size:11px; margin-top:2px; '
        f'line-height:1.3;">{name} &mdash; {desc}</div>'
        if desc else ""
    )

    return f"""
        <tr>
          <td style="padding:10px 4px; border-bottom:1px solid #1c1c1c;
                     vertical-align:top;">
            <div style="color:#f0f0f0; font-weight:600; font-size:13px;
                        font-family:Menlo,Consolas,monospace;">{ticker}</div>
            {descriptor_html}
          </td>
          <td style="padding:10px 4px; border-bottom:1px solid #1c1c1c;
                     color:#888888; text-align:right; font-size:12px;
                     font-family:Menlo,Consolas,monospace;
                     vertical-align:top; white-space:nowrap;">{mc_str}</td>
          <td style="padding:10px 4px; border-bottom:1px solid #1c1c1c;
                     color:#aaaaaa; text-align:right; font-size:13px;
                     font-family:Menlo,Consolas,monospace;
                     vertical-align:top; white-space:nowrap;">${item["price"]:,.2f}</td>
          <td style="padding:10px 4px; border-bottom:1px solid #1c1c1c;
                     color:{color}; text-align:right; font-size:13px;
                     font-weight:600; font-family:Menlo,Consolas,monospace;
                     vertical-align:top; white-space:nowrap;">
            {arrow} {sign}{pct:.2f}%
          </td>
        </tr>"""


def _stock_table(rows: list[dict], header_label: str) -> str:
    if not rows:
        return (f'<p style="color:#888888; font-size:14px; font-style:italic;">'
                f'No {header_label.lower()} data available.</p>')

    body = "".join(_stock_row(r) for r in rows)
    return f"""
        <table role="presentation" style="width:100%; border-collapse:collapse; margin-bottom:24px;">
          <thead>
            <tr>
              <th style="text-align:left; padding:8px 4px; border-bottom:1px solid #333;
                         color:#666666; font-size:10px; text-transform:uppercase;
                         letter-spacing:0.1em; font-weight:700;">{header_label}</th>
              <th style="text-align:right; padding:8px 4px; border-bottom:1px solid #333;
                         color:#666666; font-size:10px; text-transform:uppercase;
                         letter-spacing:0.1em; font-weight:700;">Mkt Cap</th>
              <th style="text-align:right; padding:8px 4px; border-bottom:1px solid #333;
                         color:#666666; font-size:10px; text-transform:uppercase;
                         letter-spacing:0.1em; font-weight:700;">Last Close</th>
              <th style="text-align:right; padding:8px 4px; border-bottom:1px solid #333;
                         color:#666666; font-size:10px; text-transform:uppercase;
                         letter-spacing:0.1em; font-weight:700;">24h</th>
            </tr>
          </thead>
          <tbody>{body}</tbody>
        </table>"""


def _story_card(story: dict, index: int, accent: str, show_category: bool = False) -> str:
    title = story.get("title", "Untitled")
    summary = story.get("summary", "")
    url = story.get("url", "#")
    source = story.get("source", "")
    category = story.get("category", "")

    meta = f"{index} &nbsp;·&nbsp; {source}"
    if show_category and category:
        meta = f"{index} &nbsp;·&nbsp; {category} &nbsp;·&nbsp; {source}"

    return f"""
        <div style="margin-bottom:28px; padding-bottom:24px; border-bottom:1px solid #222222;">
          <p style="margin:0 0 6px 0; color:#666666; font-size:11px; text-transform:uppercase;
                    letter-spacing:0.1em; font-weight:600;">{meta}</p>
          <h3 style="margin:0 0 10px 0; font-size:17px; font-weight:600; line-height:1.4; color:#f0f0f0;">
            <a href="{url}" style="color:#f0f0f0; text-decoration:none;">{title}</a>
          </h3>
          <p style="margin:0 0 12px 0; font-size:14px; line-height:1.7; color:#aaaaaa;">{summary}</p>
          <a href="{url}" style="color:{accent}; font-size:13px; text-decoration:none;
                                 font-weight:500;">Read more &rarr;</a>
        </div>"""


def build_html(stock_data: dict, ai_stories: list[dict],
               biotech_stories: list[dict], date_str: str) -> str:
    watchlist_table = _stock_table(stock_data["watchlist"], "Watchlist")
    movers_table = _stock_table(stock_data["movers"], "Top 10 Movers")
    stocks_as_of = stock_data["as_of"]

    ai_cards = "".join(
        _story_card(s, i + 1, "#7eb8f7") for i, s in enumerate(ai_stories)
    )

    if biotech_stories:
        biotech_body = "".join(
            _story_card(s, i + 1, "#4ade80", show_category=True)
            for i, s in enumerate(biotech_stories)
        )
    else:
        biotech_body = (
            '<p style="color:#888888; font-size:14px; line-height:1.7; '
            'font-style:italic; margin:0;">'
            "Quiet day in biotech. No genuinely meaningful advances surfaced — "
            "we'd rather say nothing than fill space with noise."
            '</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily Digest &mdash; {date_str}</title>
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
                Daily Digest
              </p>
              <h1 style="margin:0 0 8px 0; color:#ffffff; font-size:30px;
                          font-weight:700; line-height:1.15; letter-spacing:-0.02em;">
                Stocks, AI &amp; Biotech
              </h1>
              <p style="margin:0; color:#5a6a82; font-size:14px;">{date_str}</p>
            </td>
          </tr>

          <!-- ── INTRO BAR ───────────────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:18px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <p style="margin:0; color:#666666; font-size:13px; line-height:1.65;">
                What moved overnight and what to know this morning.
                Three sections, curated by AI, zero noise.
              </p>
            </td>
          </tr>

          <!-- ── SECTION 1: STOCKS ──────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:36px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="border-left:3px solid #f59e0b; padding-left:16px;">
                <p style="margin:0 0 3px 0; color:#f59e0b; font-size:10px;
                           letter-spacing:0.14em; text-transform:uppercase; font-weight:700;">
                  Section 01
                </p>
                <h2 style="margin:0 0 4px 0; color:#f0f0f0; font-size:20px; font-weight:700;">
                  Stocks
                </h2>
                <p style="margin:0; color:#555555; font-size:12px;">
                  Last close: {stocks_as_of}
                </p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background-color:#111111; padding:28px 44px 8px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              {watchlist_table}
              {movers_table}
            </td>
          </tr>

          <!-- ── GRADIENT DIVIDER ────────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:4px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="height:1px;
                           background:linear-gradient(90deg,transparent,#f59e0b 30%,#7eb8f7 70%,transparent);">
              </div>
            </td>
          </tr>

          <!-- ── SECTION 2: AI & TECH ────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:36px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="border-left:3px solid #7eb8f7; padding-left:16px;">
                <p style="margin:0 0 3px 0; color:#7eb8f7; font-size:10px;
                           letter-spacing:0.14em; text-transform:uppercase; font-weight:700;">
                  Section 02
                </p>
                <h2 style="margin:0 0 4px 0; color:#f0f0f0; font-size:20px; font-weight:700;">
                  AI &amp; Tech
                </h2>
                <p style="margin:0; color:#555555; font-size:12px;">
                  Models, chips, data centers, infra &amp; policy
                </p>
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

          <!-- ── SECTION 3: BIOTECH ──────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:36px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="border-left:3px solid #4ade80; padding-left:16px;">
                <p style="margin:0 0 3px 0; color:#4ade80; font-size:10px;
                           letter-spacing:0.14em; text-transform:uppercase; font-weight:700;">
                  Section 03
                </p>
                <h2 style="margin:0 0 4px 0; color:#f0f0f0; font-size:20px; font-weight:700;">
                  Biotech
                </h2>
                <p style="margin:0; color:#555555; font-size:12px;">
                  AI x biotech crossover &amp; general advancements
                </p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background-color:#111111; padding:28px 44px 40px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              {biotech_body}
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
                <a href="https://finance.yahoo.com" style="color:#3d3d3d; text-decoration:none;">Yahoo Finance</a>
                &nbsp;+&nbsp;
                <a href="https://anthropic.com" style="color:#3d3d3d; text-decoration:none;">Claude</a>
                &nbsp;&middot;&nbsp; Daily via GitHub Actions
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
        "Your daily Stocks, AI & Biotech digest is ready. "
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

    # --- Stocks ---
    log.info("Fetching stock data...")
    stock_data = get_stock_summary()

    # --- AI / Tech news ---
    log.info("Fetching AI/tech articles...")
    ai_query = (
        '("artificial intelligence" OR "machine learning" OR "large language model" '
        'OR "GPT" OR "Claude AI" OR "Gemini" OR "AI model" OR "deep learning" '
        'OR "OpenAI" OR "Anthropic" OR "foundation model" OR "AI chip" '
        'OR "GPU" OR "semiconductor" OR "TSMC" OR "NVIDIA" '
        'OR "data center" OR "AI infrastructure" OR "AI startup" OR "AI regulation")'
    )
    ai_articles = fetch_articles(ai_query, days_back=1, page_size=30)
    if not ai_articles:
        log.warning("No AI articles in last 24h — widening to 3 days.")
        ai_articles = fetch_articles(ai_query, days_back=3, page_size=30)
    log.info("AI articles fetched: %d", len(ai_articles))

    # --- Biotech news (general + AI x biotech crossover) ---
    log.info("Fetching biotech articles...")
    biotech_query = (
        '(biotech OR biotechnology OR "drug discovery" OR "clinical trial" '
        'OR "FDA approval" OR "EMA approval" OR "gene therapy" OR "gene editing" '
        'OR "CRISPR" OR mRNA OR immunotherapy OR "novel therapy" '
        'OR "breakthrough therapy" OR "AlphaFold" OR "protein folding" '
        'OR "AI drug discovery" OR "computational biology" OR "synthetic biology")'
    )
    biotech_articles = fetch_articles(biotech_query, days_back=1, page_size=30)
    if not biotech_articles:
        log.warning("No biotech articles in last 24h — widening to 3 days.")
        biotech_articles = fetch_articles(biotech_query, days_back=3, page_size=30)
    log.info("Biotech articles fetched: %d", len(biotech_articles))

    # --- Summarize ---
    log.info("Summarizing AI/tech stories with Claude...")
    ai_stories = summarize_ai_news(ai_articles)
    log.info("AI/tech stories selected: %d", len(ai_stories))

    log.info("Summarizing biotech stories with Claude...")
    biotech_stories = summarize_biotech_news(biotech_articles)
    log.info("Biotech stories selected: %d", len(biotech_stories))

    # --- Build & send ---
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    subject = f"Daily Digest: Stocks, AI & Biotech — {date_str}"
    html_body = build_html(stock_data, ai_stories, biotech_stories, date_str)

    log.info("Sending email...")
    send_email(subject, html_body)

    log.info("=== Digest run complete ===")


if __name__ == "__main__":
    main()
