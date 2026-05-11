# AGENTS.md

## Project
Python data collection + MongoDB storage — analisis popularitas topik lansia di media digital (WHO, Google Trends, YouTube). Output JSON + MongoDB Atlas.

## Entrypoints
- `python collect.py` — runs all collectors (or `--source WHO` for single source)
- `python store_to_mongo.py --source WHO --batch-id <id>` — push single source to MongoDB Atlas
- `python store_to_mongo.py --log-run --batch-id <id>` — log run metadata to `runs_log`
- `python collect.py` then `python store_to_mongo.py` — local dev flow (all sources)

## GitHub Actions
- `.github/workflows/collect.yml` — runs daily at 02:00 UTC
- **Parallel jobs** per source (WHO, YouTube, Google Trends) + `finalize` to log run
- Needs secrets: `YOUTUBE_API_KEY`, `MONGO_URI`
- Artifacts stored 30 days

## Architecture
- `collectors/base.py` — `BaseCollector` ABC. Template method: `collect()` → `fetch()` → `normalize()` → `save()`
- Each collector extends `BaseCollector`, implements `fetch()` + `normalize()`
- Collectors registered in `collect.py` `COLLECTORS` dict
- `collect.py --source <name>` runs a single collector (for parallel GH Actions)
- `collect.py` catches each collector failure so one failing doesn't abort others.

## Collectors
| Class | Source | API | Needs Key |
|-------|--------|-----|-----------|
| WHOCollector | WHO GHO | `ghoapi.azureedge.net/api/{code}` OData | No |
| GoogleTrendsCollector | Google Trends | pytrends (unofficial) | No |
| YouTubeCollector | YouTube | Data API v3 via googleapiclient | `YOUTUBE_API_KEY` |

- WHO: uses `$filter=SpatialDim eq 'IDN'`, post-filters `SpatialDim == 'IDN'`, passes `category=` to normalizer. Values in `"5.1 [4.7-5.6]"` format parsed by `_parse_value()` regex. Sex codes mapped by `_normalize_sex()`. Uses shared `HttpClient` from `utils/http_client.py` (retry + timeout).
- Google Trends: max 5 keywords/request, `hl="en-US"`, single-request strategy. Retries once with backoff.
- YouTube: sends search query per keyword (8 keywords, 25 results each), deduplicates by video_id, batch fetches stats. Engagement = views + (likes × 2) + (comments × 5). Includes `video_id`, `channel`, `title` in metadata.

## MongoDB Storage Strategy
| Source | Mode | Key | Behavior |
|--------|------|-----|----------|
| WHO | Upsert | `indicator_code + timestamp + sex` | Replace existing, insert new |
| Google Trends | Upsert | `keyword + timestamp` | Replace existing, insert new |
| YouTube | Append | — | Insert every time (all snapshots kept) |

- All documents tagged with `batch_id` (e.g. `20260511_001`) for traceability
- `runs_log` collection records each run's metadata
- Indexes: `scripts/setup_indexes.js`

## Output
- `output/{name.lower().replace('.', '_')}_health_data.json` — per-source
- `output/summary_elderly_digital.json` — aggregated (all-sources mode only)
- Google Trends often fails (rate-limited), so only WHO/YouTube files reliably appear

## Schema (v2)
```json
{"source", "keyword", "platform", "value", "metric", "timestamp",
 "region", "sentiment", "sentiment_score", "batch_id", "collected_at",
 "fetched_at", "notes", "indicator_code", "age_group", "sex",
 "video_id", "channel", "title"}
```
`platform` defaults to `source.lower()`. Extra metadata per source pulled to top level.

## Sentiment
- `utils/sentiment.py` — `SentimentAnalyzer` class
- `analyze(text)` → `(label, score)` — VADER compound + TextBlob polarity averaged. Thresholds: >0.05 positive, <-0.05 negative, else neutral.
- Used by YouTube collector on video titles

## Dependencies
`requirements.txt` notable: `pytrends` (`urllib3<2`), `google-api-python-client`, `pymongo[srv]`, `certifi`, `beautifulsoup4`/`lxml` (unused/legacy).

## Scripts
- `scripts/setup_indexes.js` — MongoDB indexes (run once via `mongosh`)

## Gotchas
- `Normalizer.normalize_record()` now supports `metadata_extra` param for arbitrary metadata fields
- YouTube normalizer passes `video_id`, `channel`, `title` via `metadata_extra`
- `collect.py` supports `--source WHO|YouTube|"Google Trends"|all` for filtering
- WHO has no simulated fallback — API failure raises RuntimeError.
- Google Trends: temp rate-limit means retry later or use VPN.
- MongoDB: `store_to_mongo.py` uses `certifi.where()` for TLS on macOS.
- `.env` loaded via `python-dotenv` at top of scripts.
