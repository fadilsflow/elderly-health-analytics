#!/usr/bin/env python3
"""
store_to_mongo.py — Simpan data collection ke MongoDB Atlas (Big Data mode).

Strategi per source:
  WHO            → Upsert  (key: indicator_code + timestamp + sex)
  Google Trends  → Upsert  (key: keyword + timestamp)
  YouTube        → Append  (insert with batch_id, simpan semua snapshot)

Cara Pakai:
    export MONGO_URI="mongodb+srv://..."
    python store_to_mongo.py --source WHO --batch-id 20260511_001
    python store_to_mongo.py --source YouTube --batch-id 20260511_001
    python store_to_mongo.py --source "Google Trends" --batch-id 20260511_001
    python store_to_mongo.py --log-run --batch-id 20260511_001       # (opsional)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne, InsertOne
from pymongo.errors import BulkWriteError, ConnectionFailure

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "elderly_analysis"
COLLECTION_NAME = "elderly_data"
RUNS_LOG_COLLECTION = "runs_log"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Strategi per source
UPSERT_KEYS: Dict[str, List[str]] = {
    "WHO": ["indicator_code", "timestamp", "sex"],
    "Google Trends": ["keyword", "timestamp"],
}
APPEND_SOURCES = {"YouTube"}


def connect():
    """Konek ke MongoDB Atlas."""
    if not MONGO_URI:
        print("ERROR: MONGO_URI tidak ditemukan di .env atau environment")
        sys.exit(1)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000, tlsCAFile=certifi.where())
    try:
        client.admin.command("ping")
        print("  -> Koneksi berhasil")
    except ConnectionFailure as e:
        print(f"ERROR: Gagal konek ke MongoDB: {e}")
        sys.exit(1)
    return client


def get_output_file(source: str) -> str:
    """Cari file JSON output untuk source tertentu."""
    source_to_file = {
        "WHO": "who_health_data.json",
        "Google Trends": "google_trends_health_data.json",
        "YouTube": "youtube_health_data.json",
    }
    filename = source_to_file.get(source)
    if not filename:
        print(f"ERROR: Unknown source '{source}'")
        sys.exit(1)
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        print(f"WARNING: File tidak ditemukan: {path}")
        return None
    return path


def load_records_from_file(filepath: str, source: str, batch_id: str) -> list[dict]:
    """Baca file JSON dan return list dokumen MongoDB siap insert."""
    with open(filepath, "r", encoding="utf-8") as f:
        records = json.load(f)

    docs = []
    result_docs = []
    for idx, rec in enumerate(records):
        metadata = rec.get("metadata", {}) or {}
        doc = {
            "source": rec.get("source"),
            "keyword": rec.get("keyword"),
            "platform": rec.get("platform"),
            "value": rec.get("value"),
            "metric": rec.get("metric"),
            "timestamp": rec.get("timestamp"),
            "region": rec.get("region"),
            "sentiment": rec.get("sentiment"),
            "sentiment_score": rec.get("sentiment_score"),
            "fetched_at": metadata.get("fetched_at"),
            "notes": metadata.get("notes"),
            "indicator_code": metadata.get("indicator_code"),
            "age_group": rec.get("age_group"),
            "sex": rec.get("sex"),
            "batch_id": batch_id,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
        # Extra metadata fields (video_id, channel, title dari YouTube)
        for extra_field in ("video_id", "channel", "title"):
            if metadata.get(extra_field):
                doc[extra_field] = metadata[extra_field]
        # Hapus field None untuk menjaga kebersihan dokumen
        doc = {k: v for k, v in doc.items() if v is not None}
        doc["_source_idx"] = idx
        result_docs.append(doc)
    return result_docs


def upsert_source(collection, docs: list[dict], upsert_keys: list[str]):
    """Upsert documents using bulk_write."""
    if not docs:
        print("  -> Tidak ada dokumen untuk di-upsert")
        return 0, 0

    operations = []
    for doc in docs:
        filter_doc = {k: doc.get(k) for k in upsert_keys}
        # Buang key2 yg dipake buat filter dari $set
        set_doc = {k: v for k, v in doc.items() if k not in upsert_keys and k != "_source_idx"}
        operations.append(UpdateOne(filter_doc, {"$set": set_doc}, upsert=True))

    BATCH_SIZE = 100
    upserted = 0
    errors = 0

    for i in range(0, len(operations), BATCH_SIZE):
        batch = operations[i : i + BATCH_SIZE]
        try:
            result = collection.bulk_write(batch, ordered=False)
            upserted += result.upserted_count + result.modified_count
        except BulkWriteError as bwe:
            details = bwe.details
            upserted += details.get("nUpserted", 0) + details.get("nModified", 0)
            err_count = len(details.get("writeErrors", []))
            errors += err_count
            for err in details.get("writeErrors", [])[:3]:
                print(f"  ⚠  {err.get('errmsg', '')[:120]}")
        except Exception as e:
            print(f"  ⚠  Gagal batch: {e}")
            errors += len(batch)

    return upserted, errors


def append_source(collection, docs: list[dict]):
    """Insert documents (append, simpan semua snapshot)."""
    if not docs:
        print("  -> Tidak ada dokumen untuk di-append")
        return 0, 0

    BATCH_SIZE = 100
    inserted = 0
    errors = 0

    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        try:
            result = collection.insert_many(batch, ordered=False)
            inserted += len(result.inserted_ids)
        except BulkWriteError as bwe:
            details = bwe.details
            inserted += details.get("nInserted", 0)
            err_count = len(details.get("writeErrors", []))
            errors += err_count
        except Exception as e:
            print(f"  ⚠  Gagal batch: {e}")
            errors += len(batch)

    return inserted, errors


def log_run(batch_id: str, client):
    """Catat metadata run di runs_log collection."""
    db = client[DB_NAME]
    log_collection = db[RUNS_LOG_COLLECTION]

    # Hitung record per source untuk batch ini
    pipeline = [
        {"$match": {"batch_id": batch_id}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
    ]
    source_counts = list(db[COLLECTION_NAME].aggregate(pipeline))
    records_per_source = {s["_id"]: s["count"] for s in source_counts}
    total = sum(records_per_source.values())

    log_entry = {
        "batch_id": batch_id,
        "sources": {
            src: {"records": cnt, "status": "success" if cnt > 0 else "empty"}
            for src, cnt in records_per_source.items()
        },
        "total_records": total,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Upsert log (kalau sudah ada batch_id, update)
    log_collection.update_one(
        {"batch_id": batch_id},
        {"$set": log_entry},
        upsert=True,
    )

    print(f"  -> Run {batch_id}: {total} total records dari {len(records_per_source)} source")


def store_source(source: str, batch_id: str):
    """Store one source to MongoDB."""
    filepath = get_output_file(source)
    if not filepath:
        return

    print(f"\n📦 Source: {source}")
    print(f"   File: {os.path.basename(filepath)}")

    docs = load_records_from_file(filepath, source, batch_id)
    if not docs:
        print("   -> 0 records, skip")
        return

    print(f"   Batch ID: {batch_id}")
    print(f"   Records : {len(docs)}")

    client = connect()
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    if source in APPEND_SOURCES:
        inserted, errors = append_source(collection, docs)
        print(f"   Inserted: {inserted}, Errors: {errors}")
    elif source in UPSERT_KEYS:
        upserted, errors = upsert_source(collection, docs, UPSERT_KEYS[source])
        print(f"   Upserted: {upserted}, Errors: {errors}")
    else:
        print(f"   ⚠  No strategy for source '{source}', inserting raw")
        inserted, errors = append_source(collection, docs)
        print(f"   Inserted: {inserted}, Errors: {errors}")

    client.close()


def main():
    parser = argparse.ArgumentParser(description="Store data collection to MongoDB Atlas")
    parser.add_argument("--source", "-s", choices=["WHO", "Google Trends", "YouTube"],
                        help="Source to store")
    parser.add_argument("--batch-id", "-b", required=True,
                        help="Batch ID (e.g. 20260511_001)")
    parser.add_argument("--log-run", action="store_true",
                        help="Log run metadata to runs_log collection")
    args = parser.parse_args()

    print("=" * 60)
    print("  STORE TO MONGODB ATLAS")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    if args.log_run:
        client = connect()
        log_run(args.batch_id, client)
        client.close()
        print("\n✅ Run logged.")
        return

    if args.source:
        store_source(args.source, args.batch_id)
    else:
        for src in ["WHO", "Google Trends", "YouTube"]:
            store_source(src, args.batch_id)

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
