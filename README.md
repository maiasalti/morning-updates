# Daily AI, X & Biotech Digest

A morning email digest that lands **every day at 8am Singapore time**. A scheduled Claude Code cloud routine researches the news with web search, writes the summaries, renders a dark-themed HTML email, and sends it through the Gmail connector. It runs on a Claude plan's usage, so there are no API keys or secrets to manage.

## Email sections

1. **From X**: up to 5 new AI tools, innovations, and posts worth reading from AI leaders (Karpathy, Dario Amodei, Jensen Huang, Altman, Hassabis, LeCun and others)
2. **AI & Tech**: the top 5 stories across AI/ML, chips, data centers, infrastructure and policy
3. **New Models**: up to 5 models actually released in the last 24 hours (open-weight, proprietary, industry-specific), each compared to existing models where the source supports it
4. **Biotech**: up to 5 stories, AI × biotech crossover first, then general biotech advances

## How it works

```
cloud routine (8am SGT daily)
  └─ reads digest/INSTRUCTIONS.md        what to research and how to write it
  └─ web search / fetch                  gathers the last 24h
  └─ writes /tmp/stories.json
  └─ python3 digest/render.py ...        validates JSON, renders the fixed HTML design
  └─ Gmail send_message                  emails the result
```

The routine lives at [claude.ai/code/routines](https://claude.ai/code/routines) and clones this repo on every run, so **edits here take effect from the next run**.

## Customization

| Thing to change | Where |
|---|---|
| What each section covers, tone, number of items | `digest/INSTRUCTIONS.md` |
| The list of AI leaders swept on X | `digest/INSTRUCTIONS.md`, Section 1 |
| Recipient address | `digest/INSTRUCTIONS.md`, step 3 |
| Email design | `digest/render.py`, all inline CSS |
| Delivery time or model | The routine's settings at claude.ai/code/routines (cron is in UTC; `0 0 * * *` = 8am SGT) |

## Limits

- **X coverage is best-effort.** X blocks reading without a login, so the routine finds posts through web search and news coverage. Notable posts show up; quiet ones can be missed.
- **Plan usage.** Each run uses your Claude plan's usage. If you've hit your limit, the run fails and no email arrives.

## Testing the renderer locally

```
python3 digest/render.py stories.json out.html && open out.html
```
