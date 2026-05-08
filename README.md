# Analisis Popularitas Topik Lansia di Media Digital

Proyek Big Data — mengumpulkan data popularitas, engagement, dan sentimen topik lansia dari berbagai platform digital.

## Sumber Data

| Sumber | API | Data | Real? |
|--------|-----|------|-------|
| **WHO** | Global Health Observatory OData | Hipertensi, diabetes, obesitas, harapan hidup (Indonesia) | ✅ API Nyata |
| **Google Trends** | unofficial pytrends | Popularitas keyword lansia di Indonesia (time series + region) | ✅ API Nyata |
| **YouTube** | YouTube Data API v3 | Video tentang lansia + engagement + sentimen | ✅ API Nyata |

## Cara Menjalankan

```bash
pip install -r requirements.txt
cp .env.example .env
# Isi YOUTUBE_API_KEY di .env
python collect.py
```

Hasil ada di folder `output/` sebagai file JSON per sumber + satu file summary.

## API Keys yang Dibutuhkan

| Key | Daftar di | Gratis? |
|-----|-----------|---------|
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) | ✅ (quota 10k unit/hari) |
| Google Trends | — | ✅ (tidak perlu key) |
| WHO | — | ✅ (public OData) |

## Struktur Proyek

```
├── collect.py                     # Main orchestrator
├── collectors/
│   ├── base.py                   # ABC BaseCollector
│   ├── who_collector.py          # WHO GHO API
│   ├── googletrends_collector.py # Google Trends (pytrends)
│   └── youtube_collector.py      # YouTube Data API v3
├── utils/
│   ├── http_client.py            # requests Session + retry
│   ├── logger.py                 # Logging config
│   ├── normalizer.py             # Schema normalization
│   └── sentiment.py              # VADER + TextBlob
├── output/                       # JSON results
├── requirements.txt
└── .env.example
```

## Arsitektur

Setiap collector meng-extend `BaseCollector` (Template Method pattern):

```
BaseCollector.collect()
    ├── fetch()       → ambil data dari API
    ├── normalize()   → transform ke schema standar
    └── save()        → simpan ke JSON
```

Schema output standar:
```json
{
  "source": "YouTube",
  "keyword": "lansia",
  "platform": "youtube",
  "value": 50734,
  "metric": "engagement_score",
  "timestamp": "2026-02-15",
  "region": "Indonesia",
  "sentiment": "negative",
  "sentiment_score": -0.1366,
  "metadata": {
    "fetched_at": "2026-05-07T04:04:25+00:00",
    "notes": "YouTube ChannelName — Sentimen: negative (-0.14)"
  }
}
```

## Catatan

- **WHO**: Nilai dengan confidence interval seperti `"5.1 [4.7-5.6]"` diparse otomatis.
- **Google Trends**: Terkadang kena rate-limit (429). Tunggu 10 menit atau pakai VPN.
- **YouTube**: Pakai engagement score = views + (likes × 2) + (comments × 5).
- **Sentimen**: Kombinasi VADER + TextBlob, range -1 sampai +1.
- Tidak ada database — output langsung ke JSON.
- Tidak ada frontend/dashboard.
