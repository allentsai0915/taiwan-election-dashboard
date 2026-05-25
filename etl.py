"""
ETL Pipeline: 2024 Taiwan Election Data
Extracts from SQLite DB, transforms into clean DataFrames, loads to CSV cache.
"""

import sqlite3
import pandas as pd
import os

DB_PATH = "taiwan_election_2024.db"
CACHE_DIR = "data_cache"


def get_connection():
    return sqlite3.connect(DB_PATH)


# ── 1. 總統選舉：各縣市候選人得票彙總 ──────────────────────────────────────
def extract_president_by_county() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT
            d.county,
            c.name   AS candidate,
            pa.name  AS party,
            SUM(p.votes) AS votes
        FROM presidents p
        JOIN districts  d  ON p.district_id  = d.id
        JOIN candidates c  ON p.candidate_id = c.id
        JOIN parties    pa ON c.party_id      = pa.id
        GROUP BY d.county, c.name, pa.name
        ORDER BY d.county, votes DESC
    """, conn)
    conn.close()

    # 計算各縣市總票數與得票率
    county_total = df.groupby("county")["votes"].sum().rename("county_total")
    df = df.join(county_total, on="county")
    df["vote_share"] = df["votes"] / df["county_total"]

    # 標記各縣市贏家
    winner_idx = df.groupby("county")["votes"].idxmax()
    df["is_winner"] = False
    df.loc[winner_idx, "is_winner"] = True

    return df


# ── 2. 總統選舉：全台彙總 ───────────────────────────────────────────────────
def extract_president_national() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT
            c.name  AS candidate,
            pa.name AS party,
            SUM(p.votes) AS votes
        FROM presidents p
        JOIN candidates c  ON p.candidate_id = c.id
        JOIN parties    pa ON c.party_id      = pa.id
        GROUP BY c.name, pa.name
        ORDER BY votes DESC
    """, conn)
    conn.close()

    total = df["votes"].sum()
    df["vote_share"] = df["votes"] / total
    return df


# ── 3. 投票率：各縣市 ──────────────────────────────────────────────────────
def extract_turnout_by_county() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT
            d.county,
            SUM(pp.effective_votes + pp.wasted_votes)    AS total_voted,
            SUM(pp.issued_votes   + pp.remained_votes)   AS total_eligible
        FROM polling_places pp
        JOIN districts d ON pp.district_id = d.id
        WHERE pp.election_type_id = 1
        GROUP BY d.county
    """, conn)
    conn.close()

    df["turnout"] = df["total_voted"] / df["total_eligible"]
    return df.sort_values("turnout", ascending=False)


# ── 4. 區域立委：各縣市各黨得票彙總 ───────────────────────────────────────
def extract_legislator_by_county() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT
            d.county,
            rl.legislator_region AS region,
            c.name  AS candidate,
            pa.name AS party,
            SUM(rl.votes) AS votes
        FROM regional_legislators rl
        JOIN districts  d  ON rl.district_id  = d.id
        JOIN candidates c  ON rl.candidate_id = c.id
        JOIN parties    pa ON c.party_id       = pa.id
        GROUP BY d.county, rl.legislator_region, c.name, pa.name
        ORDER BY rl.legislator_region, votes DESC
    """, conn)
    conn.close()

    # 標記各選區贏家
    winner_idx = df.groupby("region")["votes"].idxmax()
    df["is_winner"] = False
    df.loc[winner_idx, "is_winner"] = True

    return df


# ── 5. 各黨立委席次統計 ────────────────────────────────────────────────────
def extract_legislator_seats() -> pd.DataFrame:
    df = extract_legislator_by_county()
    winners = df[df["is_winner"]].copy()
    seats = winners.groupby("party")["region"].count().reset_index()
    seats.columns = ["party", "seats"]
    return seats.sort_values("seats", ascending=False)


# ── 6. 主要 Pipeline 執行（快取到 CSV）─────────────────────────────────────
def run_pipeline(use_cache: bool = True) -> dict[str, pd.DataFrame]:
    os.makedirs(CACHE_DIR, exist_ok=True)

    tasks = {
        "president_by_county":  extract_president_by_county,
        "president_national":   extract_president_national,
        "turnout_by_county":    extract_turnout_by_county,
        "legislator_by_county": extract_legislator_by_county,
        "legislator_seats":     extract_legislator_seats,
    }

    results = {}
    for name, func in tasks.items():
        cache_path = os.path.join(CACHE_DIR, f"{name}.csv")
        if use_cache and os.path.exists(cache_path):
            results[name] = pd.read_csv(cache_path)
        else:
            df = func()
            df.to_csv(cache_path, index=False)
            results[name] = df
        print(f"[ETL] {name}: {len(results[name])} rows")

    return results


if __name__ == "__main__":
    print("Running ETL pipeline (force refresh)...")
    data = run_pipeline(use_cache=False)
    print("\n✅ Pipeline complete. Summary:")
    for name, df in data.items():
        print(f"  {name}: {df.shape}")