<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/elderly--health--analytics-20232A?style=for-the-badge&logo=github&logoColor=white">
    <img alt="elderly-health-analytics" src="https://img.shields.io/badge/elderly--health--analytics-20232A?style=for-the-badge&logo=github&logoColor=white">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/fadilsflow/elderly-health-analytics/actions"><img src="https://img.shields.io/github/actions/workflow/status/fadilsflow/elderly-health-analytics/collect.yml?branch=master&label=collection&logo=githubactions&logoColor=white" alt="CI"></a>
  <a href="https://github.com/fadilsflow/elderly-health-analytics"><img src="https://img.shields.io/github/last-commit/fadilsflow/elderly-health-analytics?logo=git&logoColor=white" alt="Last Commit"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://www.mongodb.com/atlas"><img src="https://img.shields.io/badge/MongoDB_Atlas-47A248?logo=mongodb&logoColor=white" alt="MongoDB Atlas"></a>
  <a href="https://github.com/fadilsflow/elderly-health-analytics"><img src="https://img.shields.io/github/repo-size/fadilsflow/elderly-health-analytics?logo=dropbox&logoColor=white" alt="Repo Size"></a>
</p>

---

# elderly-health-analytics

**Big Data pipeline** untuk mengumpulkan, menyimpan, dan menganalisis popularitas serta sentimen topik kesehatan lansia di media digital Indonesia.

| Sumber | Metode | Data |
|--------|--------|------|
| **WHO** — GHO OData API | `GET /api/{indicator}?$filter=SpatialDim eq 'IDN'` | Hipertensi, diabetes, obesitas, harapan hidup |
| **Google Trends** — pytrends | `interest_over_time()` + `interest_by_region()` | Popularitas keyword (time series + per provinsi) |
| **YouTube** — Data API v3 | `search.list()` → `videos.list()` | Engagement score + sentimen video |

---

## Pipeline

```
collect.py ──→ normalize() ──→ save JSON
                │
                ▼
        store_to_mongo.py ──→ MongoDB Atlas
                │                ├── WHO:       upsert (indicator_code + year + sex)
                │                ├── Trends:    upsert (keyword + timestamp)
                │                └── YouTube:   append (batch_id per run)
                │
                ▼
        runs_log ──→ metadata tiap eksekusi
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Setup credentials
cp .env.example .env
# Isi YOUTUBE_API_KEY dan MONGO_URI

# Collect semua sumber data
python collect.py

# Atau per sumber (untuk parallel execution)
python collect.py --source WHO
python collect.py --source YouTube
python collect.py --source "Google Trends"

# Simpan ke MongoDB Atlas
python store_to_mongo.py --source WHO --batch-id $(date +%Y%m%d_001)
python store_to_mongo.py --log-run --batch-id $(date +%Y%m%d_001)
```

Hasil sementara di `output/` sebagai file JSON.

## Keys & Credentials

| Key | Diperlukan? | Cara Dapatkan |
|-----|-------------|---------------|
| `YOUTUBE_API_KEY` | ✅ YouTube | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) — gratis, quota 10k unit/hari |
| `MONGO_URI` | ✅ MongoDB | [MongoDB Atlas](https://www.mongodb.com/atlas) — free tier M0, 512 MB |
| Google Trends | ❌ | Tidak perlu key |
| WHO | ❌ | Public OData API |

## GitHub Actions

Pipeline berjalan otomatis setiap hari pukul **02:00 UTC** (09:00 WIB).

```
┌──────────┐  ┌──────────┐  ┌────────────┐
│    WHO   │  │  YouTube  │  │    Trends  │    ← parallel
└────┬─────┘  └────┬─────┘  └─────┬──────┘
     └──────────────┴──────────────┘
                    │
               ┌────▼────┐
               │finalize │   ← log run ke MongoDB
               └─────────┘
```

Set `YOUTUBE_API_KEY` dan `MONGO_URI` sebagai [Actions secrets](https://github.com/fadilsflow/elderly-health-analytics/settings/secrets/actions).

## Arsitektur

```
collect.py                         store_to_mongo.py
  ├── BaseCollector (ABC)            ├── WHO       → UpdateOne + upsert
  │   ├── fetch()   → API            ├── Trends    → UpdateOne + upsert
  │   ├── normalize() → schema       └── YouTube   → InsertMany + append
  │   └── save()    → JSON
  └── save_summary() → aggregated
```

Schema standar tiap record:

```json
{
  "source": "WHO",              "keyword": "Hypertension",
  "value": 31.16,               "metric": "percent",
  "timestamp": "2005-01-01",    "region": "Indonesia",
  "sentiment": null,            "batch_id": "20260511_001",
  "indicator_code": "BP_04",    "age_group": "60+",
  "sex": "Male"
}
```

## Tech Stack

| Layer | Tool |
|-------|------|
| Language | Python 3.12+ |
| Collectors | `requests`, `pytrends`, `google-api-python-client` |
| Sentiment | VADER + TextBlob (averaged) |
| Storage | MongoDB Atlas, `pymongo[srv]` |
| Orchestration | GitHub Actions (parallel jobs) |
| Analysis | Google Colab — pandas, matplotlib, seaborn |

## Project Structure

```
├── collect.py                  # Orchestrator
├── store_to_mongo.py           # MongoDB writer
├── collectors/
│   ├── base.py                 # BaseCollector (Template Method)
│   ├── who_collector.py        # WHO GHO API
│   ├── googletrends_collector.py
│   └── youtube_collector.py
├── utils/
│   ├── normalizer.py           # Schema v2
│   ├── sentiment.py            # VADER + TextBlob
│   ├── http_client.py          # Retry + timeout
│   └── logger.py
├── .github/workflows/
│   └── collect.yml             # Daily pipeline
├── scripts/
│   └── setup_indexes.js        # MongoDB indexes
└── output/                     # JSON artifacts
```

---

<p align="center">
  <sub>Capstone Project — Big Data · Analisis Popularitas Topik Lansia di Media Digital</sub>
</p>
