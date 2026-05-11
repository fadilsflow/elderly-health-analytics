// setup_indexes.js — MongoDB indexes untuk elderly_analysis
// Jalankan via: mongosh "mongodb+srv://..." < scripts/setup_indexes.js

db = db.getSiblingDB("elderly_analysis");

print("Setting up indexes for elderly_data...");

// Upsert key untuk WHO: indicator_code + timestamp + sex (unique in source)
db.elderly_data.createIndex(
  { indicator_code: 1, timestamp: 1, sex: 1 },
  {
    unique: true,
    partialFilterExpression: { source: "WHO" },
    name: "idx_who_upsert",
  }
);

// Upsert key untuk Google Trends: keyword + timestamp (unique in source)
db.elderly_data.createIndex(
  { keyword: 1, timestamp: 1 },
  {
    unique: true,
    partialFilterExpression: { source: "Google Trends" },
    name: "idx_trends_upsert",
  }
);

// Query YouTube by video_id + batch_id
db.elderly_data.createIndex(
  { video_id: 1, batch_id: -1 },
  {
    partialFilterExpression: { video_id: { $exists: true } },
    name: "idx_youtube_video_batch",
  }
);

// Query umum: source + keyword + timestamp
db.elderly_data.createIndex(
  { source: 1, keyword: 1, timestamp: -1 },
  { name: "idx_source_keyword_time" }
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
