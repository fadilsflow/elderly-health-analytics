# Rencana Pengerjaan — Analisis Popularitas Topik Lansia di Media Digital

```

├── ✅ Data Collection (Step 1)      → SELESAI
├── ✅ Data Storage (Step 2)          → SELESAI
├── 🧹 Data Preparation (Step 3)      → GOOGLE COLAB
└── 📊 Analysis & Visualization (Step 4) → GOOGLE COLAB

```

---

## ✅ Step 1 — Data Collection (SELESAI)

Tiga collector berjalan dengan API nyata:

| Collector | Data | Records |
|-----------|------|---------|
| WHO GHO API | Hipertensi, diabetes, obesitas, harapan hidup (Indonesia) | 315 |
| Google Trends | Interest over time + region untuk 5 keyword lansia | 0* |
| YouTube Data API v3 | Video engagement + sentimen untuk 8 keyword | 172 |

*Google Trends rawan rate-limit. Records bisa 0 jika kena 429.

Output: `output/who_health_data.json`, `output/youtube_health_data.json`, `output/summary_elderly_digital.json`

### Collector Details

- **WHO**: `$filter=SpatialDim eq 'IDN'`, post-filter `SpatialDim == 'IDN'`. Nilai `"5.1 [4.7-5.6]"` diparse otomatis. Sex codes `SEX_BTSX/SEX_MLE/SEX_FMLE` → Both/Male/Female.
- **Google Trends**: max 5 keywords/request, `hl="en-US"`, single-request. Sering rate-limit (429).
- **YouTube**: search per keyword (8 keywords, 25 results), dedup by video_id, batch fetch stats. Engagement = views + (likes × 2) + (comments × 5). Sentimen: VADER + TextBlob. Menyertakan `video_id`, `channel`, `title` di metadata (via `metadata_extra` param normalizer).

### Perintah

```bash
python collect.py                           # all sources
python collect.py --source WHO              # single source
python collect.py --source YouTube
python collect.py --source "Google Trends"
```

---

## ✅ Step 2 — Data Storage (MongoDB Atlas) — SELESAI

### Storage Strategy

| Source | Mode | Key | Behavior |
|--------|------|-----|----------|
| **WHO** | Upsert | `indicator_code + timestamp + sex` | Update existing, insert new |
| **Google Trends** | Upsert | `keyword + timestamp` | Update existing, insert new |
| **YouTube** | Append | — | Insert setiap kali (simpan semua snapshot) |

### Script: `store_to_mongo.py`

```bash
# Store per source (utk parallel execution di GH Actions)
python store_to_mongo.py --source WHO --batch-id 20260511_001
python store_to_mongo.py --source YouTube --batch-id 20260511_001
python store_to_mongo.py --source "Google Trends" --batch-id 20260511_001

# Log metadata eksekusi
python store_to_mongo.py --log-run --batch-id 20260511_001
```

### Schema MongoDB

**`elderly_analysis.elderly_data`:**
```json
{
  "_id": ObjectId,
  "source": "WHO",
  "keyword": "Hypertension",
  "platform": "who",
  "value": 31.16,
  "metric": "percent",
  "timestamp": "2005-01-01",
  "region": "Indonesia",
  "sentiment": null,
  "sentiment_score": null,
  "fetched_at": "2026-05-07T04:04:08+00:00",
  "indicator_code": "BP_04",
  "age_group": "60+",
  "sex": "Male",
  "batch_id": "20260511_001",
  "collected_at": "2026-05-11T17:55:01+00:00",
  "video_id": "abc123",           // YouTube only
  "channel": "ChannelName",       // YouTube only
  "title": "Video Title"           // YouTube only
}
```

**`elderly_analysis.runs_log`:**
```json
{
  "batch_id": "20260511_001",
  "sources": {
    "WHO": {"records": 315, "status": "success"},
    "YouTube": {"records": 172, "status": "success"}
  },
  "total_records": 487,
  "completed_at": "2026-05-11T17:57:20+00:00"
}
```

### Indexes (sudah dibuat via `scripts/setup_indexes.js`)

| Collection | Index | Tujuan |
|-----------|-------|--------|
| `elderly_data` | `(indicator_code, timestamp, sex)` — unique, partial WHO | Upsert key WHO |
| `elderly_data` | `(keyword, timestamp)` — unique, partial Trends | Upsert key Trends |
| `elderly_data` | `(video_id, batch_id)` — partial | Query YouTube snapshot |
| `elderly_data` | `(source, keyword, timestamp)` | Query umum analisis |
| `elderly_data` | `(batch_id)` | Traceability |
| `runs_log` | `(batch_id)` — unique | Dedup run log |

### Data Current Status

| Source | Records | Batch ID |
|--------|---------|----------|
| WHO | 315 | `20260511_001` |
| YouTube | 172 | `20260511_001` |
| **Total** | **487** | |

### GitHub Actions Workflow ( `.github/workflows/collect.yml` )

```
┌──────────┐  ┌──────────┐  ┌────────────┐
│    WHO   │  │  YouTube  │  │    Trends  │    ← parallel jobs
└────┬─────┘  └────┬─────┘  └─────┬──────┘
     └──────────────┴──────────────┘
                    │
               ┌────▼────┐
               │finalize │   ← store_to_mongo.py --log-run
               └─────────┘
```

- **Schedule**: `0 2 * * *` (02:00 UTC / 09:00 WIB)
- **Trigger manual**: via `workflow_dispatch`
- **Secrets**: `YOUTUBE_API_KEY`, `MONGO_URI`
- **Artifacts**: disimpan 30 hari

---

## 🧹 Step 3 — Data Preparation (Google Colab) — BELUM

### Notebook: `notebooks/02_data_preparation.ipynb`

#### 3.1 Koneksi & Load Data

```python
!pip install pymongo[srv]
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Konek MongoDB Atlas
client = MongoClient(os.getenv("MONGO_URI"), tlsCAFile=certifi.where())
db = client["elderly_analysis"]

# Load per source
who_df = pd.DataFrame(list(db.elderly_data.find({"source": "WHO"})))
youtube_df = pd.DataFrame(list(db.elderly_data.find({"source": "YouTube"})))
trends_df = pd.DataFrame(list(db.elderly_data.find({"source": "Google Trends"})))
```

Field yang tersedia di MongoDB:
- **Semua**: `source`, `keyword`, `platform`, `value`, `metric`, `timestamp`, `region`, `sentiment`, `sentiment_score`, `fetched_at`, `notes`, `batch_id`, `collected_at`
- **WHO**: `indicator_code`, `age_group`, `sex`
- **YouTube**: `video_id`, `channel`, `title`
- **Google Trends**: (sama dengan shared fields)

#### 3.2 Preprocessing per Source

**WHO:**
| Masalah | Penanganan |
|---------|-----------|
| Value sudah numerik | Verifikasi dtype, handle NaN |
| Missing value (`sex`, `age_group`) | `fillna("Unknown")` |
| Duplikat (indikator+tahun+sex) | Sudah terhandle oleh upsert MongoDB — tetap drop manual: `drop_duplicates(subset=["indicator_code","timestamp","sex"])` |
| Timestamp format `YYYY-01-01` | `pd.to_datetime(timestamp).dt.year` |

**YouTube:**
| Masalah | Penanganan |
|---------|-----------|
| Sentiment_score outliers | Clip IQR 1.5x |
| Engagement score right-skewed | `np.log1p()` transform |
| Duplikat video_id antar batch | `drop_duplicates(subset=["video_id"])` untuk dedup atau filter `batch_id` terbaru |
| Timestamp parsing | `pd.to_datetime()` → extract year, month, dayofweek |
| `batch_id` untuk time-series | Group by `batch_id` untuk lihat perubahan engagement |

**Google Trends:**
| Masalah | Penanganan |
|---------|-----------|
| Nilai interest = 0 | Fill 0 — tetap valid |
| Time series pivot | `pivot_table(index="timestamp", columns="keyword", values="value")` |
| Region data | Filter `region != "Indonesia"` untuk data per provinsi |

#### 3.3 Feature Engineering

**WHO:**
- `year` dari timestamp
- Group by `(keyword, sex, year)` → mean value
- Pivot: `pivot_table(index="year", columns=["keyword", "sex"], values="value")`

**YouTube:**
- `publish_year`, `publish_month` dari timestamp
- `is_positive = sentiment == "positive"`
- `log_engagement = np.log1p(value)`
- `is_duplicate = video_id.duplicated(keep=False)` — flag video yang muncul di >1 batch

**Google Trends:**
- Pivot time series: `pivot_table(index="timestamp", columns="keyword", values="value")`
- Fill NaN dengan 0

#### 3.4 Save

```python
who_df.to_csv("clean_who.csv", index=False)
youtube_df.to_csv("clean_youtube.csv", index=False)
trends_df.to_csv("clean_trends.csv", index=False)
```

Mount Google Drive atau langsung simpan di Colab.

---

## 📊 Step 4 — Analysis & Visualization (Google Colab) — BELUM

### Notebook: `notebooks/03_analysis_visualization.ipynb`

#### 4.1 WHO Analysis

**Charts:**
1. **Multi-line chart** — tren 4 indikator kesehatan dari 2000-2020 (facet per sex)
2. **Grouped bar chart** — perbandingan Male vs Female per indikator (tahun terakhir)
3. **Box plot** — distribusi value per indikator

**Analytics:**
- Indikator paling tinggi prevalensinya di Indonesia?
- Tren naik/turun per indikator (regression slope)
- Gap Male vs Female signifikan?

#### 4.2 Google Trends Analysis

**Charts:**
1. **Multi-line chart** — popularitas keyword (time series 5 tahun)
2. **Stacked area chart** — kontribusi relatif keyword per bulan
3. **Heatmap provinsi** — popularitas per keyword per provinsi
4. **Seasonal decomposition** — trend + seasonal + residual

**Analytics:**
- Keyword dengan popularitas tertinggi?
- Musim dengan pencarian tinggi?
- Provinsi dengan awareness tertinggi?

#### 4.3 YouTube Analysis

**Charts:**
1. **Histogram** — distribusi engagement score (raw vs log-transformed)
2. **Top 10 bar chart** — video dengan engagement tertinggi (label: `channel — title`)
3. **Pie chart** — proporsi sentimen (positive/negative/neutral)
4. **Scatter matrix** — engagement vs sentiment_score, grouped by keyword
5. **Bar chart per bulan** — jumlah upload per periode
6. **Box plot** — engagement per keyword
7. **Channel analysis** — top 5 channels by total engagement

**Analytics:**
- Topik lansia yang paling engaging?
- Sentimen cenderung positif atau negatif?
- Channel/channel mana yang paling aktif?
- Korelasi sentimen vs engagement?

#### 4.4 Cross-Source Insights

**Charts:**
1. **Dual-axis chart** — WHO prevalence vs Google Trends popularity (tahun yang sama)
2. **Facet grid** — sentimen YouTube per keyword kesehatan
3. **Summary dashboard** — satu figure multi-panel (4-6 panel) mencakup WHO trends + Google Trends + YouTube engagement + sentimen

**Analytics:**
- Apakah tren pencarian "kesehatan lansia" di Google sejalan dengan data WHO?
- Topik kesehatan mana yang paling banyak dibicarakan di YouTube?
- Insight keseluruhan: kondisi kesehatan lansia di Indonesia dari perspektif media digital

#### 4.5 Output

- Semua chart disimpan sebagai PNG: `visualizations/`
- Insight summary dalam markdown
- Opsional: export HTML dashboard (Plotly)

---

## Dependency Graph

```
Step 2 ✅ (store_to_mongo.py + MongoDB)
    │
    ▼
Step 3 ❓ (02_data_preparation.ipynb) → butuh data di MongoDB + MONGO_URI
    │
    ▼
Step 4 ❓ (03_analysis_viz.ipynb) → butuh clean CSVs
```

## Tools & Libraries

| Step | Tools |
|------|-------|
| 2 ✅ | Python, pymongo, certifi, python-dotenv |
| 3 ❓ | Google Colab, pandas, numpy, pymongo, certifi |
| 4 ❓ | Google Colab, matplotlib, seaborn, plotly (opsional), scipy |

## Timeline

| Step | Status | Estimasi |
|------|--------|----------|
| Step 1 — Data Collection | ✅ Selesai | — |
| Step 2 — MongoDB Storage | ✅ Selesai | ~30 menit |
| Step 3 — Preparation | ❓ Belum | ~1 jam |
| Step 4 — Analysis & Viz | ❓ Belum | ~2 jam |
| **Total** | | **~3 jam tersisa** |
