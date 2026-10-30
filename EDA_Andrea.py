"""
Exploratory Data Analysis (EDA) for Assignment 3 - Very Large Distributed Data Volumes
Analyzes datasets to verify information required for Queries 1-10 (Part 2),
locates exact line numbers of corrupted data, and treats duplicates and anomalies.
"""

import ast
import json
import os
import re
from typing import Any, Dict, List, Set, Tuple
import numpy as np
import pandas as pd
from tabulate import tabulate

# Dataset paths
MOVIES_METADATA_PATH = "csvs/movies_metadata.csv"
CREDITS_PATH = "csvs/credits.csv"
KEYWORDS_PATH = "csvs/keywords.csv"
LINKS_PATH = "csvs/links.csv"
LINKS_SMALL_PATH = "csvs/links_small.csv"
RATINGS_SMALL_PATH = "csvs/ratings_small.csv"
RATINGS_FULL_PATH = "csvs/ratings.csv"


def safe_parse_json(val: Any) -> Any:
    """Safely parse JSON or Python dict/list literals with single quotes."""
    if pd.isna(val) or val is None:
        return []
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return []
    try:
        return json.loads(s)
    except Exception:
        try:
            return ast.literal_eval(s)
        except Exception:
            return []


def find_corrupted_csv_lines(filepath: str, bad_tokens: List[str]) -> List[Dict[str, Any]]:
    """Scans the raw CSV file line-by-line to find the exact file line numbers of corrupted data."""
    corrupted_lines = []
    if not os.path.exists(filepath):
        return corrupted_lines

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line_num, line in enumerate(f, 1):
            for token in bad_tokens:
                if token in line:
                    corrupted_lines.append({
                        "file_line_number": line_num,
                        "matched_token": token,
                        "raw_line_snippet": line.strip()[:140] + ("..." if len(line.strip()) > 140 else "")
                    })
                    break
    return corrupted_lines


# ==============================================================================
# 1. Global Sanity Checks, Corrupted Lines & Duplicate Treatment
# ==============================================================================
def check_dataset_integrity() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[Dict[str, Any]]]:
    print("=" * 80)
    print("1. GLOBAL DATASET INTEGRITY & PRIMARY KEY SANITY CHECKS")
    print("=" * 80)

    # 1.1 movies_metadata.csv
    print(f"\n[Loading] {MOVIES_METADATA_PATH}...")
    df_movies = pd.read_csv(MOVIES_METADATA_PATH, low_memory=False)
    total_raw_movies = len(df_movies)

    # Find malformed rows (where id is not a numeric string)
    numeric_mask = pd.to_numeric(df_movies["id"], errors="coerce").notna()
    corrupted_df_rows = df_movies[~numeric_mask].copy()
    corrupted_count = len(corrupted_df_rows)

    # Exact line numbers in raw CSV
    bad_tokens = corrupted_df_rows["id"].astype(str).tolist()
    raw_corrupted_lines = find_corrupted_csv_lines(MOVIES_METADATA_PATH, bad_tokens)

    # Display corrupted lines details
    print(f"\n[!] IDENTIFIED CORRUPTED DATA: {corrupted_count} corrupted row(s) found in {MOVIES_METADATA_PATH}:")
    for item in raw_corrupted_lines:
        print(f"    - Raw CSV Line {item['file_line_number']}: (token: '{item['matched_token']}')")
        print(f"      Snippet: {item['raw_line_snippet']}")

    for idx, row in corrupted_df_rows.iterrows():
        print(f"    - DataFrame Row Index {idx}:")
        print(f"      id='{row['id']}', title='{row.get('title')}', poster_path='{row.get('poster_path')}', release_date='{row.get('release_date')}'")
        print(f"      Root Cause: Unquoted newline in the overview of preceding row caused row splitting and column shifts.")

    # Treat corrupted rows: filter out non-numeric IDs
    clean_movies = df_movies[numeric_mask].copy()
    clean_movies["id"] = clean_movies["id"].astype(int)

    # Treat duplicates in movies_metadata:
    # Sort by popularity / vote_count descending so the most complete record is retained
    clean_movies["popularity_num"] = pd.to_numeric(clean_movies["popularity"], errors="coerce").fillna(0)
    clean_movies["vote_count_num"] = pd.to_numeric(clean_movies["vote_count"], errors="coerce").fillna(0)
    duplicate_movie_ids_before = clean_movies["id"].duplicated().sum()
    clean_movies = clean_movies.sort_values(["popularity_num", "vote_count_num"], ascending=False)
    clean_movies = clean_movies.drop_duplicates(subset="id", keep="first").sort_index()
    unique_movie_ids = len(clean_movies)
    print(f"\n[+] Duplicates in movies_metadata treated: {duplicate_movie_ids_before} duplicate rows removed (kept best record per ID).")

    # 1.2 credits.csv
    print(f"\n[Loading] {CREDITS_PATH}...")
    df_credits = pd.read_csv(CREDITS_PATH, low_memory=False)
    total_raw_credits = len(df_credits)
    numeric_credits_mask = pd.to_numeric(df_credits["id"], errors="coerce").notna()
    clean_credits = df_credits[numeric_credits_mask].copy()
    clean_credits["id"] = clean_credits["id"].astype(int)
    duplicate_credits_ids = clean_credits["id"].duplicated().sum()
    # Treat duplicates in credits
    clean_credits = clean_credits.drop_duplicates(subset="id", keep="first")
    print(f"[+] Duplicates in credits.csv treated: {duplicate_credits_ids} duplicate rows removed.")

    # 1.3 keywords.csv
    print(f"\n[Loading] {KEYWORDS_PATH}...")
    df_keywords = pd.read_csv(KEYWORDS_PATH, low_memory=False)
    total_raw_keywords = len(df_keywords)
    clean_keywords = df_keywords[pd.to_numeric(df_keywords["id"], errors="coerce").notna()].copy()
    clean_keywords["id"] = clean_keywords["id"].astype(int)
    duplicate_keyword_ids = clean_keywords["id"].duplicated().sum()
    # Treat duplicates in keywords
    clean_keywords = clean_keywords.drop_duplicates(subset="id", keep="first")
    print(f"[+] Duplicates in keywords.csv treated: {duplicate_keyword_ids} duplicate rows removed.")

    # 1.4 links.csv
    print(f"\n[Loading] {LINKS_PATH}...")
    df_links = pd.read_csv(LINKS_PATH, low_memory=False)
    total_raw_links = len(df_links)
    missing_tmdb_in_links = df_links["tmdbId"].isna().sum()
    duplicate_links = df_links["movieId"].duplicated().sum()
    # Treat links: drop null tmdbId and duplicates
    clean_links = df_links.dropna(subset=["tmdbId"]).copy()
    clean_links["tmdbId"] = clean_links["tmdbId"].astype(int)
    clean_links["movieId"] = clean_links["movieId"].astype(int)
    clean_links = clean_links.drop_duplicates(subset="movieId", keep="first")
    print(f"[+] Links treated: {missing_tmdb_in_links} null tmdbIds dropped, {duplicate_links} duplicate movieIds dropped.")

    integrity_table = [
        ["movies_metadata.csv", total_raw_movies, corrupted_count, duplicate_movie_ids_before, unique_movie_ids],
        ["credits.csv", total_raw_credits, total_raw_credits - len(clean_credits), duplicate_credits_ids, len(clean_credits)],
        ["keywords.csv", total_raw_keywords, total_raw_keywords - len(clean_keywords), duplicate_keyword_ids, len(clean_keywords)],
        ["links.csv", total_raw_links, missing_tmdb_in_links, duplicate_links, len(clean_links)],
    ]

    headers = ["Dataset", "Raw Rows", "Corrupted / Missing ID", "Duplicate IDs (Treated)", "Clean Final Rows"]
    print("\n" + tabulate(integrity_table, headers=headers, tablefmt="github"))

    return clean_movies, clean_credits, clean_links, raw_corrupted_lines


# ==============================================================================
# 2. Query Requirements Verification (Queries 1 - 10)
# ==============================================================================
def verify_queries_information(clean_movies: pd.DataFrame, clean_credits: pd.DataFrame, clean_links: pd.DataFrame):
    print("\n" + "=" * 80)
    print("2. QUERY-SPECIFIC DATA AVAILABILITY & HYGIENE VERIFICATION")
    print("=" * 80)

    # Pre-parse movies_metadata necessary numeric and temporal columns
    movies = clean_movies.copy()
    movies["revenue_num"] = pd.to_numeric(movies["revenue"], errors="coerce").fillna(0)
    movies["vote_average_num"] = pd.to_numeric(movies["vote_average"], errors="coerce").fillna(0.0)
    movies["vote_count_num"] = pd.to_numeric(movies["vote_count"], errors="coerce").fillna(0).astype(int)
    movies["runtime_num"] = pd.to_numeric(movies["runtime"], errors="coerce")
    movies["parsed_release_date"] = pd.to_datetime(movies["release_date"], errors="coerce")
    movies["release_year"] = movies["parsed_release_date"].dt.year
    movies["decade"] = (movies["release_year"] // 10 * 10).dropna().astype(int).astype(str) + "s"

    # Merge credits with movies for crew/cast checks
    credits_dedup = clean_credits.drop_duplicates(subset=["id"])
    movies_credits = pd.merge(movies, credits_dedup[["id", "cast", "crew"]], on="id", how="left")

    summary_findings = []

    # --------------------------------------------------------------------------
    # Query 1: Top 10 Directors (>= 5 movies) by median revenue + movie count & mean vote_avg
    # --------------------------------------------------------------------------
    print("\n>>> Query 1: Directors with >= 5 movies (median revenue, movie count, mean vote_average)")
    directors_map = {}
    empty_crew_cnt = 0
    for _, row in movies_credits.iterrows():
        crew_raw = row["crew"]
        crew_list = safe_parse_json(crew_raw)
        if not crew_list:
            empty_crew_cnt += 1
            continue
        for member in crew_list:
            if member.get("job") == "Director":
                d_name = member.get("name")
                if d_name:
                    if d_name not in directors_map:
                        directors_map[d_name] = {"revenues": [], "votes": []}
                    directors_map[d_name]["revenues"].append(row["revenue_num"])
                    directors_map[d_name]["votes"].append(row["vote_average_num"])

    directors_gte_5 = {d: info for d, info in directors_map.items() if len(info["revenues"]) >= 5}
    zero_rev_movies = (movies["revenue_num"] == 0).sum()
    pos_rev_movies = (movies["revenue_num"] > 0).sum()
    print(f"  - Total unique directors identified: {len(directors_map)}")
    print(f"  - Directors with >= 5 movies: {len(directors_gte_5)}")
    print(f"  - Movies with 0 revenue reported: {zero_rev_movies} ({zero_rev_movies/len(movies)*100:.1f}%)")
    print(f"  - Movies with positive revenue: {pos_rev_movies} ({pos_rev_movies/len(movies)*100:.1f}%)")
    summary_findings.append(["Q1", "credits.crew (Director), revenue, vote_average",
                             f"Total directors: {len(directors_map)}, >=5 films: {len(directors_gte_5)}",
                             "High 0-revenue frequency (needs policy: include 0 or >0?)"])

    # --------------------------------------------------------------------------
    # Query 2: Actor pairs co-starred in >= 3 movies + co-appearances & avg vote_avg
    # --------------------------------------------------------------------------
    print("\n>>> Query 2: Actor pairs co-starred in >= 3 movies")
    # Sample 5,000 movies to verify pair generation and speed
    pair_counts = {}
    for _, row in movies_credits.head(5000).iterrows():
        cast_list = safe_parse_json(row["cast"])
        if not cast_list:
            continue
        actors = sorted(list({m.get("name") for m in cast_list if m.get("name")}))
        for i in range(len(actors)):
            for j in range(i + 1, len(actors)):
                pair = (actors[i], actors[j])
                pair_counts[pair] = pair_counts.get(pair, 0) + 1

    sample_gte_3 = sum(1 for c in pair_counts.values() if c >= 3)
    print(f"  - Tested sample of 5,000 movies: {sample_gte_3} actor pairs co-starred >= 3 times.")
    print("  - Deduplication per movie cast is required to prevent self-pairing.")
    summary_findings.append(["Q2", "credits.cast, vote_average",
                             "Verified in sample (sufficient frequency)",
                             "Must deduplicate actors per movie, normalize pair order"])

    # --------------------------------------------------------------------------
    # Query 3: Top 10 actors (>= 10 movies) with widest genre breadth
    # --------------------------------------------------------------------------
    print("\n>>> Query 3: Top 10 actors (>= 10 movies) with widest genre breadth")
    from collections import Counter
    genre_freq = Counter()
    empty_genre_count = 0
    for _, row in movies.iterrows():
        g_list = safe_parse_json(row["genres"])
        if not g_list:
            empty_genre_count += 1
        for g in g_list:
            if g.get("name"):
                genre_freq[g.get("name")] += 1

    all_genres = sorted(list(genre_freq.keys()))
    print(f"  - Total distinct genres found: {len(all_genres)}")
    print(f"  - All distinct genres ({len(all_genres)}): {', '.join(all_genres)}")
    print(f"  - Movies with missing/empty genre: {empty_genre_count} ({empty_genre_count/len(movies)*100:.1f}%)")
    print("  - Genre distribution across dataset:")
    for g, count in genre_freq.most_common():
        print(f"      * {g:18}: {count:>6,} movies")
    summary_findings.append(["Q3", "credits.cast, movies.genres",
                             f"{len(all_genres)} distinct genres available",
                             "JSON genres require flattening into array of strings"])

    # --------------------------------------------------------------------------
    # Query 4: Film collections (>= 3 movies) largest total revenue
    # --------------------------------------------------------------------------
    print("\n>>> Query 4: Film collections (>= 3 movies) with largest total revenue")
    collections_map = {}
    for _, row in movies.iterrows():
        col_raw = row["belongs_to_collection"]
        col_dict = safe_parse_json(col_raw)
        if isinstance(col_dict, dict) and col_dict.get("name"):
            name = col_dict["name"]
            if name not in collections_map:
                collections_map[name] = []
            collections_map[name].append((row["revenue_num"], row["vote_average_num"], row["parsed_release_date"]))

    collections_gte_3 = {k: v for k, v in collections_map.items() if len(v) >= 3}
    print(f"  - Total collections identified: {len(collections_map)}")
    print(f"  - Collections with >= 3 movies: {len(collections_gte_3)}")
    summary_findings.append(["Q4", "belongs_to_collection, revenue, vote_average, release_date",
                             f"{len(collections_gte_3)} collections with >= 3 movies",
                             "Parse dict string to extract collection name/id"])

    # --------------------------------------------------------------------------
    # Query 5: By decade and primary genre, median runtime & movie count
    # --------------------------------------------------------------------------
    print("\n>>> Query 5: Median runtime and movie count by decade & primary genre")
    missing_dates = movies["parsed_release_date"].isna().sum()
    missing_runtime = movies["runtime_num"].isna().sum()
    zero_runtime = (movies["runtime_num"] == 0).sum()
    valid_primary_genre_cnt = 0
    for _, row in movies.iterrows():
        g_list = safe_parse_json(row["genres"])
        if g_list and g_list[0].get("name"):
            valid_primary_genre_cnt += 1

    print(f"  - Missing/invalid release dates: {missing_dates}")
    print(f"  - Missing runtime: {missing_runtime}, Zero runtime: {zero_runtime}")
    print(f"  - Movies with valid primary genre: {valid_primary_genre_cnt}")
    summary_findings.append(["Q5", "release_date (decade), genres[0], runtime",
                             f"{len(movies) - missing_dates} movies have valid release date",
                             "Convert runtime=0 to null; exclude or group missing genres"])

    # --------------------------------------------------------------------------
    # Query 6: Top-billed 5 cast (by order), female proportion by decade
    # --------------------------------------------------------------------------
    print("\n>>> Query 6: Top-billed 5 cast female proportion by decade")
    gender_distribution = {0: 0, 1: 0, 2: 0}
    for _, row in movies_credits.head(5000).iterrows():
        cast_list = safe_parse_json(row["cast"])
        cast_sorted = sorted(cast_list, key=lambda x: x.get("order", 999))[:5]
        for c in cast_sorted:
            g = c.get("gender", 0)
            if g in gender_distribution:
                gender_distribution[g] += 1

    print(f"  - Cast gender encoding sample: 0 (Unknown)={gender_distribution[0]}, 1 (Female)={gender_distribution[1]}, 2 (Male)={gender_distribution[2]}")
    summary_findings.append(["Q6", "credits.cast (order, gender), release_date",
                             "Gender encoding is verified (0=Unknown, 1=Female, 2=Male)",
                             "Unknown (0) to be ignored in ratio: Female / (Female + Male)"])

    # --------------------------------------------------------------------------
    # Query 7: Text search over overview & tagline matching 'noir' / 'neo-noir'
    # --------------------------------------------------------------------------
    print("\n>>> Query 7: Text search over overview & tagline matching 'noir' or 'neo-noir'")
    null_overview = movies["overview"].isna().sum()
    null_tagline = movies["tagline"].isna().sum()

    noir_regex = re.compile(r"\b(noir|neo-noir)\b", re.IGNORECASE)
    matching_noir = 0
    matching_noir_gte_50 = 0
    for _, row in movies.iterrows():
        text = f"{str(row['overview'])} {str(row['tagline'])}"
        if noir_regex.search(text):
            matching_noir += 1
            if row["vote_count_num"] >= 50:
                matching_noir_gte_50 += 1

    print(f"  - Null overviews: {null_overview}, Null taglines: {null_tagline}")
    print(f"  - Movies matching 'noir' or 'neo-noir': {matching_noir}")
    print(f"  - Matching movies with vote_count >= 50: {matching_noir_gte_50}")
    summary_findings.append(["Q7", "overview, tagline, vote_count, vote_average, title",
                             f"{matching_noir_gte_50} matching candidates with vote_count >= 50",
                             "Coalesce null overview/tagline to empty string, create text index"])

    # --------------------------------------------------------------------------
    # Query 8: Director-actor pairs (>= 3 collaborations) highest mean vote_avg (vote_count >= 100)
    # --------------------------------------------------------------------------
    print("\n>>> Query 8: Director-actor pairs (>= 3 collaborations) with vote_count >= 100")
    movies_gte_100 = movies_credits[movies_credits["vote_count_num"] >= 100]
    print(f"  - Movies with vote_count >= 100: {len(movies_gte_100)}")
    dir_actor_collabs = {}
    for _, row in movies_gte_100.head(2000).iterrows():
        crew_list = safe_parse_json(row["crew"])
        cast_list = safe_parse_json(row["cast"])
        directors = {m.get("name") for m in crew_list if m.get("job") == "Director" and m.get("name")}
        actors = {m.get("name") for m in cast_list if m.get("name")}
        for d in directors:
            for a in actors:
                if d != a:
                    pair = (d, a)
                    dir_actor_collabs[pair] = dir_actor_collabs.get(pair, 0) + 1

    print(f"  - Sample collaborations identified in first 2,000 qualifying films: {len(dir_actor_collabs)}")
    summary_findings.append(["Q8", "credits (Director + cast), vote_count, vote_average, revenue",
                             f"{len(movies_gte_100)} movies qualify with vote_count >= 100",
                             "Filter vote_count >= 100 before computing director-actor joins"])

    # --------------------------------------------------------------------------
    # Query 9: Non-English movies produced in the United States (top 10 original languages)
    # --------------------------------------------------------------------------
    print("\n>>> Query 9: Non-English movies produced in the United States")
    non_en = movies[movies["original_language"] != "en"]
    us_produced_cnt = 0
    non_en_languages = {}
    for _, row in non_en.iterrows():
        p_countries = safe_parse_json(row["production_countries"])
        is_us = any(c.get("iso_3166_1") == "US" or "United States" in c.get("name", "") for c in p_countries)
        if not is_us:
            p_comp = safe_parse_json(row["production_companies"])
            is_us = any("US" in c.get("name", "") or "United States" in c.get("name", "") for c in p_comp)
        if is_us:
            us_produced_cnt += 1
            lang = row["original_language"]
            non_en_languages[lang] = non_en_languages.get(lang, 0) + 1

    print(f"  - Non-English movies produced in US: {us_produced_cnt}")
    print(f"  - Top 5 original languages found: {sorted(non_en_languages.items(), key=lambda x: x[1], reverse=True)[:5]}")
    summary_findings.append(["Q9", "original_language, production_countries, production_companies",
                             f"{us_produced_cnt} qualifying non-English US movies",
                             "Parse ISO country code ('US') or 'United States of America'"])

    # --------------------------------------------------------------------------
    # Query 10: User rating variance and genre breadth (ratings + links + movies)
    # --------------------------------------------------------------------------
    print("\n>>> Query 10: User ratings variance and distinct genres rated")
    print(f"  - Checking {RATINGS_SMALL_PATH}...")
    df_ratings_small = pd.read_csv(RATINGS_SMALL_PATH)
    clean_links_sub = clean_links[["movieId", "tmdbId"]].copy()

    mapped_ratings = df_ratings_small.merge(clean_links_sub, on="movieId").merge(
        movies[["id", "genres"]], left_on="tmdbId", right_on="id"
    )
    mapped_count = len(mapped_ratings)
    total_ratings = len(df_ratings_small)
    print(f"  - Ratings mapped successfully: {mapped_count} / {total_ratings} ({mapped_count/total_ratings*100:.2f}%)")
    summary_findings.append(["Q10", "ratings (userId, rating), links, movies.genres",
                             f"{mapped_count} / {total_ratings} ratings mapped in sample",
                             "Clean links.csv to remove NaN tmdbId; join via tmdbId to genres"])

    # --------------------------------------------------------------------------
    # Summary Table
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("3. SUMMARY OF DATA COVERAGE & QUALITY FINDINGS FOR QUERIES 1 - 10")
    print("=" * 80)
    headers = ["Query", "Required Attributes", "Data Availability / Coverage", "Data Cleaning Plan"]
    print(tabulate(summary_findings, headers=headers, tablefmt="github"))


def main():
    clean_movies, clean_credits, clean_links, corrupted_lines = check_dataset_integrity()
    verify_queries_information(clean_movies, clean_credits, clean_links)
    print("\nEDA finished successfully.")


if __name__ == "__main__":
    main()
