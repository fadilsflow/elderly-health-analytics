#!/usr/bin/env python3
"""
data_preparation.py — Load data from MongoDB Atlas into pandas DataFrames.

Usage:
    python data_preparation.py
"""

import os
import sys
from datetime import datetime

import certifi
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "elderly_analysis"
COLLECTION_NAME = "elderly_data"


def connect():
    if not MONGO_URI:
        print("ERROR: MONGO_URI tidak ditemukan di .env atau environment")
        sys.exit(1)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000, tlsCAFile=certifi.where())
    try:
        client.admin.command("ping")
        print("  -> Koneksi MongoDB berhasil")
    except ConnectionFailure as e:
        print(f"ERROR: Gagal konek ke MongoDB: {e}")
        sys.exit(1)
    return client


def load_source(collection, source: str) -> pd.DataFrame:
    cursor = collection.find({"source": source})
    df = pd.DataFrame(list(cursor))
    if df.empty:
        print(f"  -> {source}: 0 records")
        return df
    print(f"  -> {source}: {len(df)} records, {len(df.columns)} columns")
    return df


def prepare_dataframes():
    print("=" * 60)
    print("  DATA PREPARATION — MongoDB Atlas → pandas")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)

    client = connect()
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    total = collection.count_documents({})
    print(f"\nTotal dokumen di collection: {total}\n")

    sources = ["WHO", "YouTube", "Google Trends"]
    dataframes = {}

    for source in sources:
        df = load_source(collection, source)
        dataframes[source] = df

    client.close()

    print("\n" + "=" * 60)
    print("  RINGKASAN DATA")
    print("=" * 60)

    for source, df in dataframes.items():
        if df.empty:
            print(f"\n--- {source} ---")
            print("  (tidak ada data)")
            continue

        print(f"\n--- {source} ---")
        print(f"  Records : {len(df)}")
        print(f"  Columns : {list(df.columns)}")

        for col in df.columns:
            dtype = df[col].dtype
            nulls = df[col].isna().sum()
            if dtype in ("float64", "int64"):
                print(f"    {col}: {dtype}, min={df[col].min()}, max={df[col].max()}, nulls={nulls}")
            elif dtype == "object":
                uniq = df[col].nunique()
                print(f"    {col}: {dtype}, unique={uniq}, nulls={nulls}")

    # Gabung semua source jadi satu DataFrame untuk analisis lintas source
    all_dfs = [df for df in dataframes.values() if not df.empty]
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        print(f"\n--- Combined ({len(combined)} records) ---")
        print(f"  Sources  : {combined['source'].value_counts().to_dict()}")
        print(f"  Keywords : {combined['keyword'].nunique()}")
        print(f"  Timerange: {combined['timestamp'].min()} s/d {combined['timestamp'].max()}")
        dataframes["_combined"] = combined

    return dataframes


if __name__ == "__main__":
    dfs = prepare_dataframes()
