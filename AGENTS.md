# AGENTS.md

## Project
Python data collection system — analisis popularitas topik lansia di media digital (WHO, Google Trends, YouTube). Output JSON, no DB/frontend/ML.

## Entrypoint
- `collect.py` — orchestrator, iterates `COLLECTORS` dict. Run: `python collect.py`

## Architecture
- `collectors/base.py` — `BaseCollector` ABC. Template Method: `collect()` → `fetch()` → `normalize()` → `save()`
- Each collector extends `BaseCollector`, implements `fetch()` + `normalize()`
- Collectors registered in `collect.py` COLLECTORS dict (key=display name, value=class)
- Failure in one collector does NOT abort others (caught by try/except with empty result)

## Collectors
| Class | Source | API | Needs Key |
|-------|--------|-----|-----------|
| WHOCollector | WHO GHO | `ghoapi.azureedge.net/api/{code}` OData | No |
| GoogleTrendsCollector | Google Trends | pytrends (unofficial) | No (rate-limited, single-request strategy) |
| YouTubeCollector | YouTube | Data API v3 via googleapiclient | `YOUTUBE_API_KEY` |

- WHO uses `$filter=SpatialDim eq 'IDN'`, post-filters `SpatialDim == 'IDN'`
- WHO values have interval format `"5.1 [4.7-5.6]"` — parsed by `_parse_value()` via regex
- WHO sex codes: `SEX_BTSX/SEX_MLE/SEX_FMLE` → normalized by `_normalize_sex()`
- Google Trends: max 5 keywords/request, batched, `hl="en-US"` (more stable than id-ID)
- Google Trends prone to 429 rate-limit. Single request strategy. Retry with backoff.
- YouTube: sends search query per keyword, then batch fetches video stats by IDs

## Output Schema (v2)
```json
{"source", "keyword", "platform", "value", "metric", "timestamp",
 "region", "sentiment", "sentiment_score", "metadata": {"fetched_at", "notes"}}
```
Backward compat fields emitted when set: `age_group`, `sex`, `indicator_code` (metadata)

## Sentiment
- `utils/sentiment.py` — VADER + TextBlob combined score
- `analyze(text)` returns `(label, score)` where label: positive/negative/neutral
- Used by YouTube collector on video titles

## Output
- `output/{collector_name_health_data}.json` (per source)
- `output/summary_elderly_digital.json` (aggregated)

## Dependencies
`pip install -r requirements.txt`. Notable: pytrends needs `urllib3<2` (conflict with newer urllib3 Retry API). `google-api-python-client` for YouTube.

## Gotchas
- `Normalizer.normalize_record()` uses `keyword` param, NOT `category` (backward compat `category` → `keyword` alias)
- `save()` filename is auto-generated: `self.name.lower().replace('.', '_') + '_health_data.json'`
- .env loaded via `python-dotenv` at top of collect.py
- WHO has no simulated fallback — API failure raises RuntimeError
- Google Trends: temp rate-limit means retry later or use VPN
- Frontend was deleted. No dashboard.
