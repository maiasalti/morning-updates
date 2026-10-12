"""
Daily AI, X & Biotech Digest: HTML renderer.

The cloud routine (see digest/INSTRUCTIONS.md) does the research and writing
and saves it as JSON. This script turns that JSON into the email HTML, so the
design stays fixed no matter what the model writes. Standard library only.

Usage:
    python3 digest/render.py stories.json out.html

Input shape:
    {
      "date": "October 12, 2026",
      "x_posts":         [{"author", "handle", "category", "title", "summary", "url"}],
      "ai_stories":      [{"title", "summary", "url", "source"}],
      "model_stories":   [{"title", "summary", "url", "source", "category"}],
      "biotech_stories": [{"title", "summary", "url", "source", "category"}]
    }
"""

import json
import sys
from html import escape

SECTIONS = ["x_posts", "ai_stories", "model_stories", "biotech_stories"]
REQUIRED = {
    "x_posts": ["author", "handle", "title", "summary", "url"],
    "ai_stories": ["title", "summary", "url", "source"],
    "model_stories": ["title", "summary", "url", "source", "category"],
    "biotech_stories": ["title", "summary", "url", "source", "category"],
}
MODEL_CATEGORIES = {"Open-Weight", "Proprietary", "Industry-Specific"}
BIOTECH_CATEGORIES = {"AI x Biotech", "Biotech"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(data: dict) -> list[str]:
    """Return a list of problems; empty means the JSON is safe to render."""
    problems = []
    if not isinstance(data.get("date"), str) or not data["date"].strip():
        problems.append("missing 'date'")
    for section in SECTIONS:
        items = data.get(section)
        if not isinstance(items, list):
            problems.append(f"'{section}' must be a list (use [] if empty)")
            continue
        if len(items) > 5:
            problems.append(f"'{section}' has {len(items)} items; max is 5")
        for i, item in enumerate(items):
            for key in REQUIRED[section]:
                if not str(item.get(key, "")).strip():
                    problems.append(f"{section}[{i}] missing '{key}'")
            url = str(item.get("url", ""))
            if url and not url.startswith(("https://", "http://")):
                problems.append(f"{section}[{i}] url is not http(s): {url}")
            cat = item.get("category")
            if section == "model_stories" and cat and cat not in MODEL_CATEGORIES:
                problems.append(f"{section}[{i}] category '{cat}' not in {sorted(MODEL_CATEGORIES)}")
            if section == "biotech_stories" and cat and cat not in BIOTECH_CATEGORIES:
                problems.append(f"{section}[{i}] category '{cat}' not in {sorted(BIOTECH_CATEGORIES)}")
    if not data.get("ai_stories"):
        problems.append("'ai_stories' is empty; there is always AI news, search again")
    return problems


# ---------------------------------------------------------------------------
# HTML pieces
# ---------------------------------------------------------------------------

def _story_card(story: dict, index: int, accent: str, show_category: bool = False) -> str:
    title = escape(story.get("title", "Untitled"))
    summary = escape(story.get("summary", ""))
    url = escape(story.get("url", "#"), quote=True)
    source = escape(story.get("source", ""))
    category = escape(story.get("category", ""))

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


def _x_card(post: dict, index: int, accent: str) -> str:
    """Like a story card, but the meta line names who posted it."""
    handle = post.get("handle", "").lstrip("@")
    card = dict(post)
    card["source"] = f"{post.get('author', '')} (@{handle})"
    return _story_card(card, index, accent, show_category=True).replace(
        "Read more &rarr;", "View on X &rarr;"
    )


def _empty(text: str) -> str:
    return (
        '<p style="color:#888888; font-size:14px; line-height:1.7; '
        f'font-style:italic; margin:0;">{text}</p>'
    )


def _section_header(number: int, color: str, title: str, subtitle: str) -> str:
    return f"""
          <tr>
            <td style="background-color:#111111; padding:36px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="border-left:3px solid {color}; padding-left:16px;">
                <p style="margin:0 0 3px 0; color:{color}; font-size:10px;
                           letter-spacing:0.14em; text-transform:uppercase; font-weight:700;">
                  Section {number:02d}
                </p>
                <h2 style="margin:0 0 4px 0; color:#f0f0f0; font-size:20px; font-weight:700;">
                  {title}
                </h2>
                <p style="margin:0; color:#555555; font-size:12px;">
                  {subtitle}
                </p>
              </div>
            </td>
          </tr>"""


def _section_body(body: str, bottom_padding: int = 20) -> str:
    return f"""
          <tr>
            <td style="background-color:#111111; padding:28px 44px {bottom_padding}px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              {body}
            </td>
          </tr>"""


def _divider(left: str, right: str) -> str:
    return f"""
          <tr>
            <td style="background-color:#111111; padding:4px 44px 4px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <div style="height:1px;
                           background:linear-gradient(90deg,transparent,{left} 30%,{right} 70%,transparent);">
              </div>
            </td>
          </tr>"""


# ---------------------------------------------------------------------------
# Full email
# ---------------------------------------------------------------------------

X_COLOR = "#f59e0b"
AI_COLOR = "#7eb8f7"
MODELS_COLOR = "#c084fc"
BIOTECH_COLOR = "#4ade80"


def build_html(data: dict) -> str:
    date_str = escape(data["date"])

    x_body = (
        "".join(_x_card(p, i + 1, X_COLOR) for i, p in enumerate(data["x_posts"]))
        or _empty("Nothing worth your time on X in the last 24 hours.")
    )
    ai_body = "".join(
        _story_card(s, i + 1, AI_COLOR) for i, s in enumerate(data["ai_stories"])
    )
    model_body = (
        "".join(_story_card(s, i + 1, MODELS_COLOR, show_category=True)
                for i, s in enumerate(data["model_stories"]))
        or _empty("No notable model releases in the last 24 hours.")
    )
    biotech_body = (
        "".join(_story_card(s, i + 1, BIOTECH_COLOR, show_category=True)
                for i, s in enumerate(data["biotech_stories"]))
        or _empty("Quiet day in biotech. No genuinely meaningful advances surfaced — "
                  "we'd rather say nothing than fill space with noise.")
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
                AI, X &amp; Biotech
              </h1>
              <p style="margin:0; color:#5a6a82; font-size:14px;">{date_str}</p>
            </td>
          </tr>

          <!-- ── INTRO BAR ───────────────────────────────────────── -->
          <tr>
            <td style="background-color:#111111; padding:18px 44px;
                        border-left:1px solid #1c1c1c; border-right:1px solid #1c1c1c;">
              <p style="margin:0; color:#666666; font-size:13px; line-height:1.65;">
                What happened overnight and what to know this morning.
                Four sections, curated by AI, zero noise.
              </p>
            </td>
          </tr>
{_section_header(1, X_COLOR, "From X", "New AI tools, innovations &amp; what AI leaders are saying")}
{_section_body(x_body)}
{_divider(X_COLOR, AI_COLOR)}
{_section_header(2, AI_COLOR, "AI &amp; Tech", "Models, chips, data centers, infra &amp; policy")}
{_section_body(ai_body)}
{_divider(AI_COLOR, MODELS_COLOR)}
{_section_header(3, MODELS_COLOR, "New Models", "Released in the last 24h — open-weight, proprietary &amp; industry-specific")}
{_section_body(model_body)}
{_divider(MODELS_COLOR, BIOTECH_COLOR)}
{_section_header(4, BIOTECH_COLOR, "Biotech", "AI x biotech crossover &amp; general advancements")}
{_section_body(biotech_body, bottom_padding=40)}

          <!-- ── FOOTER ──────────────────────────────────────────── -->
          <tr>
            <td style="background-color:#0a0a0a; border:1px solid #181818;
                        border-radius:0 0 12px 12px; padding:28px 44px;">
              <p style="margin:0 0 8px 0; color:#333333; font-size:12px;
                         line-height:1.6; text-align:center;">
                Researched &amp; written by
                <a href="https://claude.com/claude-code" style="color:#3d3d3d; text-decoration:none;">Claude Code</a>
                &nbsp;&middot;&nbsp; Daily via a scheduled cloud routine
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


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: python3 digest/render.py stories.json out.html")
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    problems = validate(data)
    if problems:
        sys.exit("Invalid stories JSON:\n  - " + "\n  - ".join(problems))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(build_html(data))
    counts = ", ".join(f"{s}={len(data[s])}" for s in SECTIONS)
    print(f"Rendered {sys.argv[2]} ({counts})")


if __name__ == "__main__":
    main()
