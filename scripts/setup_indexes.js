// setup_indexes.js — MongoDB indexes untuk elderly_analysis
// Jalankan via: mongosh "mongodb+srv://..." < scripts/setup_indexes.js

db = db.getSiblingDB("elderly_analysis");

print("Setting up indexes for elderly_data...");

// Hapus versi lama agar script aman dijalankan ulang setelah perubahan schema.
const existingIndexNames = db.elderly_data.getIndexes().map((index) => index.name);
for (const name of ["idx_who_upsert", "idx_trends_upsert", "idx_youtube_video_batch", "idx_source_keyword_time"]) {
  if (existingIndexNames.includes(name)) db.elderly_data.dropIndex(name);
}

// Upsert key untuk WHO: indicator_code + timestamp + sex (unique in source)
db.elderly_data.createIndex(
  { source: 1, indicator_code: 1, timestamp: 1, sex: 1 },
  {
    unique: true,
    partialFilterExpression: { source: "WHO" },
    name: "idx_who_upsert",
  }
);

// Upsert key untuk Google Trends: keyword + timestamp (unique in source)
db.elderly_data.createIndex(
  { source: 1, keyword: 1, timestamp: 1, region: 1 },
  {
    unique: true,
    partialFilterExpression: { source: "Google Trends" },
    name: "idx_trends_upsert",
  }
);

// Satu snapshot per video per hari; rerun workflow tidak membuat duplikat.
db.elderly_data.createIndex(
  { source: 1, video_id: 1, snapshot_date: 1 },
  {
    unique: true,
    partialFilterExpression: { source: "YouTube", snapshot_date: { $exists: true } },
    name: "idx_youtube_video_batch",
  }
);

// Query umum: source + keyword + timestamp
db.elderly_data.createIndex(
  { source: 1, keyword: 1, timestamp: -1 },
  { name: "idx_source_keyword_time" }
);

// Ambil batch/snapshot terbaru tanpa scan seluruh histori.
db.elderly_data.createIndex(
  { source: 1, snapshot_date: -1, collected_at: -1 },
  { name: "idx_source_snapshot" }
);

// Traceability by batch_id
db.elderly_data.createIndex(
  { batch_id: 1 },
  { name: "idx_batch_id" }
);

// runs_log unique by batch_id
db.runs_log.createIndex(
  { batch_id: 1 },
  { unique: true, name: "idx_runs_log_batch" }
);

print("Indexes created successfully!");
print(db.elderly_data.getIndexes({ name: 1 }));
