#!/usr/bin/env python3
"""Create or migrate MongoDB indexes required by the daily pipeline."""

import os
import sys

import certifi
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "elderly_analysis"


def ensure_index(collection, keys, *, name, unique=False, partial=None):
    existing = collection.index_information().get(name)
    expected_keys = list(keys)
    incompatible = existing and (
        list(existing.get("key", [])) != expected_keys
        or bool(existing.get("unique", False)) != unique
        or existing.get("partialFilterExpression") != partial
    )
    if incompatible:
        print(f"Migrating index {name}")
        collection.drop_index(name)
        existing = None
    if not existing:
        options = {"name": name, "unique": unique}
        if partial:
            options["partialFilterExpression"] = partial
        collection.create_index(expected_keys, **options)
        print(f"Created index {name}")


def main():
    if not MONGO_URI:
        print("ERROR: MONGO_URI tidak tersedia", file=sys.stderr)
        return 1

    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=15_000,
        tlsCAFile=certifi.where(),
    )
    try:
        db = client[DB_NAME]
        data = db["elderly_data"]
        ensure_index(
            data,
            [("source", ASCENDING), ("indicator_code", ASCENDING), ("timestamp", ASCENDING), ("sex", ASCENDING)],
            name="idx_who_upsert",
            unique=True,
            partial={"source": "WHO"},
        )
        ensure_index(
            data,
            [("source", ASCENDING), ("keyword", ASCENDING), ("timestamp", ASCENDING), ("region", ASCENDING)],
            name="idx_trends_upsert",
            unique=True,
            partial={"source": "Google Trends"},
        )
        ensure_index(
            data,
            [("source", ASCENDING), ("video_id", ASCENDING), ("snapshot_date", ASCENDING)],
            name="idx_youtube_video_batch",
            unique=True,
            partial={"source": "YouTube", "snapshot_date": {"$exists": True}},
        )
        ensure_index(
            data,
            [("source", ASCENDING), ("keyword", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_source_keyword_time",
        )
        ensure_index(
            data,
            [("source", ASCENDING), ("snapshot_date", DESCENDING), ("collected_at", DESCENDING)],
            name="idx_source_snapshot",
        )
        ensure_index(data, [("batch_id", ASCENDING)], name="idx_batch_id")
        ensure_index(
            db["runs_log"],
            [("batch_id", ASCENDING)],
            name="idx_runs_log_batch",
            unique=True,
        )
        client.admin.command("ping")
        print("MongoDB indexes ready")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
