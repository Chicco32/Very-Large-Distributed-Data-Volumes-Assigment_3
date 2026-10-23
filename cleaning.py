"""
Data Cleaning and MongoDB Preparation Script
Assignment 3 - Very Large Distributed Data Volumes

Implements:
1. Setup and Data Loading (movies_metadata, credits, keywords, links, ratings)
2. Initial Inspection and Data Types
3. Data Cleaning (Corrupted rows, Duplicates, Missing Values)
4. JSON Parsing (genres, collection, companies, countries, cast, crew, keywords)
5. Univariate & Bivariate Visual Exploration (matplotlib, seaborn)
6. Links Bridging & Ratings Ingestion:
   - links.csv is used in Python as an in-memory bridge (MovieLens movieId -> TMDB id).
   - No separate MongoDB links collection is created.
   - Ratings are ingested with movieId pointing directly to movies._id.
7. MongoDB Insertion (Docker container):
   - Collections: 'movies' and 'ratings'
   - Production indexes for Queries 1-10 (including compound text search and rating lookups).
"""

import argparse
import ast
import json
import os
import sys
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Set

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

try:
    from DbConnector import DbConnector
except ImportError:
    DbConnector = None

# Dataset file paths
MOVIES_METADATA_PATH = "csvs/movies_metadata.csv"
CREDITS_PATH = "csvs/credits.csv"
KEYWORDS_PATH = "csvs/keywords.csv"
LINKS_SMALL_PATH = "csvs/links_small.csv"
LINKS_FULL_PATH = "csvs/links.csv"
RATINGS_SMALL_PATH = "csvs/ratings_small.csv"
RATINGS_FULL_PATH = "csvs/ratings.csv"
PLOTS_DIR = "eda_plots"


# ==============================================================================
# Helper JSON / Literal Parser
# ==============================================================================
def safe_parse_json(val: Any) -> Any:
    """Parses JSON or Python literal representations safely into native objects."""
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


# ==============================================================================
# Step 1: Setup e Caricamento dei Dati
# ==============================================================================
def load_datasets(use_full_ratings: bool = False) -> Dict[str, Any]:
    print("=" * 80)
    print("1. SETUP E CARICAMENTO DEI DATI")
    print("=" * 80)
    print(f"Caricamento di {MOVIES_METADATA_PATH}...")
    movies_df = pd.read_csv(MOVIES_METADATA_PATH, low_memory=False)

    print(f"Caricamento di {CREDITS_PATH}...")
    credits_df = pd.read_csv(CREDITS_PATH, low_memory=False)

    print(f"Caricamento di {KEYWORDS_PATH}...")
    keywords_df = pd.read_csv(KEYWORDS_PATH, low_memory=False)

    links_path = LINKS_FULL_PATH if os.path.exists(LINKS_FULL_PATH) else LINKS_SMALL_PATH
    print(f"Caricamento del file ponte {links_path}...")
    links_df = pd.read_csv(links_path, low_memory=False)

    ratings_path = RATINGS_FULL_PATH if (use_full_ratings and os.path.exists(RATINGS_FULL_PATH)) else RATINGS_SMALL_PATH
    print(f"Dataset dei voti selezionato: {ratings_path}")

    return {
        "movies": movies_df,
        "credits": credits_df,
        "keywords": keywords_df,
        "links": links_df,
        "ratings_path": ratings_path,
        "use_full_ratings": use_full_ratings,
    }


# ==============================================================================
# Step 2: Ispezione Iniziale e Tipi di Dato
# ==============================================================================
def inspect_initial_data(movies_df: pd.DataFrame):
    print("\n" + "=" * 80)
    print("2. ISPEZIONE INIZIALE E TIPI DI DATO")
    print("=" * 80)
    print(f"Dimensioni del DataFrame Movies: {movies_df.shape[0]} righe x {movies_df.shape[1]} colonne")
    print("\n[Colonne e Tipi Rilevati (info)]:")
    print(movies_df.dtypes.to_string())

    print("\n[Prime 3 righe (head)]:")
    print(movies_df[["id", "title", "release_date", "budget", "revenue"]].head(3))


# ==============================================================================
# Step 3: Pulizia dei Dati (Data Cleaning)
# ==============================================================================
def clean_data(data: Dict[str, Any]) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("3. PULIZIA DEI DATI (DATA CLEANING)")
    print("=" * 80)

    movies_df = data["movies"].copy()
    credits_df = data["credits"].copy()
    keywords_df = data["keywords"].copy()
    links_df = data["links"].copy()

    # 3.1 Identificazione e Trattamento Righe Corrotte (movies_metadata)
    numeric_id_mask = movies_df["id"].astype(str).str.isnumeric()
    corrupted_rows = movies_df[~numeric_id_mask]
    print(f"\n[+] Righe corrotte rimosse in movies_metadata: {len(corrupted_rows)}")
    for idx, r in corrupted_rows.iterrows():
        print(f"    - Index {idx} | ID errato: '{r['id']}' | Titolo presunto: '{r.get('poster_path')}'")

    # Filtra solo le righe con ID numerici
    movies_df = movies_df[numeric_id_mask].copy()
    movies_df["id"] = movies_df["id"].astype(int)

    # 3.2 Trattamento dei Duplicati
    movies_df["popularity_clean"] = pd.to_numeric(movies_df["popularity"], errors="coerce").fillna(0)
    movies_df["vote_count_clean"] = pd.to_numeric(movies_df["vote_count"], errors="coerce").fillna(0)
    dup_movies_count = movies_df["id"].duplicated().sum()
    movies_df = movies_df.sort_values(["popularity_clean", "vote_count_clean"], ascending=False)
    movies_df = movies_df.drop_duplicates(subset="id", keep="first").sort_index()
    print(f"[+] Duplicati rimossi in movies_metadata: {dup_movies_count} (rimasti {len(movies_df)} record univoci)")

    # Duplicati in credits.csv
    credits_df = credits_df[pd.to_numeric(credits_df["id"], errors="coerce").notna()].copy()
    credits_df["id"] = credits_df["id"].astype(int)
    dup_credits_count = credits_df["id"].duplicated().sum()
    credits_df = credits_df.drop_duplicates(subset="id", keep="first")
    print(f"[+] Duplicati rimossi in credits.csv: {dup_credits_count} (rimasti {len(credits_df)} record univoci)")

    # Duplicati in keywords.csv
    keywords_df = keywords_df[pd.to_numeric(keywords_df["id"], errors="coerce").notna()].copy()
    keywords_df["id"] = keywords_df["id"].astype(int)
    dup_keywords_count = keywords_df["id"].duplicated().sum()
    keywords_df = keywords_df.drop_duplicates(subset="id", keep="first")
    print(f"[+] Duplicati rimossi in keywords.csv: {dup_keywords_count} (rimasti {len(keywords_df)} record univoci)")

    # 3.3 Pulizia e Preparazione del Dizionario Ponte (links.csv)
    # links.csv viene pulito per creare una mappatura diretta in memoria: MovieLens movieId -> TMDB id
    links_clean = links_df.dropna(subset=["tmdbId", "movieId"]).copy()
    links_clean["tmdbId"] = links_clean["tmdbId"].astype(int)
    links_clean["movieId"] = links_clean["movieId"].astype(int)
    links_clean = links_clean.drop_duplicates(subset="movieId", keep="first")
    links_bridge_map = dict(zip(links_clean["movieId"], links_clean["tmdbId"]))
    print(f"[+] Ponte links.csv pronto: {len(links_bridge_map)} associazioni univoche MovieLens -> TMDB ID create.")

    # 3.4 Trattamento Valori Mancanti e Conversioni di Tipo
    movies_df["tagline"] = movies_df["tagline"].fillna("")
    movies_df["overview"] = movies_df["overview"].fillna("")
    movies_df["budget"] = pd.to_numeric(movies_df["budget"], errors="coerce").fillna(0).astype(int)
    movies_df["revenue"] = pd.to_numeric(movies_df["revenue"], errors="coerce").fillna(0).astype(int)
    movies_df["vote_average"] = pd.to_numeric(movies_df["vote_average"], errors="coerce").fillna(0.0).astype(float)
    movies_df["vote_count"] = pd.to_numeric(movies_df["vote_count"], errors="coerce").fillna(0).astype(int)
    movies_df["runtime"] = pd.to_numeric(movies_df["runtime"], errors="coerce")

    # Formattazione Date e Calcolo Decennio
    movies_df["release_datetime"] = pd.to_datetime(movies_df["release_date"], errors="coerce")
    movies_df["release_date_clean"] = movies_df["release_datetime"].dt.strftime("%Y-%m-%d")
    movies_df["release_year"] = movies_df["release_datetime"].dt.year
    movies_df["decade"] = (movies_df["release_year"] // 10 * 10).apply(
        lambda y: f"{int(y)}s" if pd.notna(y) else "Unknown"
    )

    data["movies"] = movies_df
    data["credits"] = credits_df
    data["keywords"] = keywords_df
    data["links_bridge_map"] = links_bridge_map
    data["valid_movie_ids"] = set(movies_df["id"])
    return data


# ==============================================================================
# Step 4: Parsing dei Campi JSON (Cruciale per MongoDB)
# ==============================================================================
def parse_json_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("4. PARSING DEI CAMPI JSON (CRUCIALE PER MONGODB)")
    print("=" * 80)

    movies_df = data["movies"]
    credits_df = data["credits"]
    keywords_df = data["keywords"]

    print("Parsing dei campi JSON in movies_metadata (genres, collections, countries, companies)...")
    movies_df["genres_parsed"] = movies_df["genres"].apply(safe_parse_json)
    movies_df["genre_names"] = movies_df["genres_parsed"].apply(
        lambda x: [g["name"] for g in x if isinstance(g, dict) and "name" in g] if isinstance(x, list) else []
    )
    movies_df["primary_genre"] = movies_df["genre_names"].apply(
        lambda x: x[0] if len(x) > 0 else "Unknown"
    )

    def parse_collection(val):
        d = safe_parse_json(val)
        if isinstance(d, dict) and d.get("name"):
            return {"id": d.get("id"), "name": d.get("name")}
        return None

    movies_df["collection_parsed"] = movies_df["belongs_to_collection"].apply(parse_collection)
    movies_df["production_countries_parsed"] = movies_df["production_countries"].apply(safe_parse_json)
    movies_df["production_companies_parsed"] = movies_df["production_companies"].apply(safe_parse_json)
    movies_df["spoken_languages_parsed"] = movies_df["spoken_languages"].apply(safe_parse_json)

    print("Parsing dei campi JSON in credits.csv (cast, crew)...")
    credits_df["cast_parsed"] = credits_df["cast"].apply(safe_parse_json)
    credits_df["crew_parsed"] = credits_df["crew"].apply(safe_parse_json)

    print("Parsing dei campi JSON in keywords.csv...")
    keywords_df["keywords_parsed"] = keywords_df["keywords"].apply(safe_parse_json)

    print("Parsing completato.")
    return data


# ==============================================================================
# Step 5: Analisi Univariata e Bivariata (Esplorazione visiva)
# ==============================================================================
def generate_visual_explorations(movies_df: pd.DataFrame):
    print("\n" + "=" * 80)
    print("5. ANALISI UNIVARIATA E BIVARIATA (ESPLORAZIONE VISIVA)")
    print("=" * 80)

    os.makedirs(PLOTS_DIR, exist_ok=True)
    sns.set_theme(style="whitegrid")

    # 5.1 Distribuzione Vote Average
    plt.figure(figsize=(9, 5))
    sns.histplot(movies_df["vote_average"], bins=30, kde=True, color="skyblue")
    plt.title("Distribuzione del Vote Average (Valutazione Media)", fontsize=14)
    plt.xlabel("Vote Average (0 - 10)")
    plt.ylabel("Conteggio Film")
    vote_plot_path = os.path.join(PLOTS_DIR, "vote_average_distribution.png")
    plt.tight_layout()
    plt.savefig(vote_plot_path, dpi=300)
    plt.close()
    print(f"[+] Salvato grafico Vote Average: {vote_plot_path}")

    # 5.2 Distribuzione Revenue per valori > 0
    pos_revenue = movies_df[movies_df["revenue"] > 0]["revenue"] / 1e6
    plt.figure(figsize=(9, 5))
    sns.histplot(pos_revenue, bins=40, kde=True, color="salmon")
    plt.title("Distribuzione Revenue per Film con Dati Registrati (> 0 USD in Milioni)", fontsize=14)
    plt.xlabel("Revenue (Milioni di USD)")
    plt.ylabel("Conteggio Film")
    revenue_plot_path = os.path.join(PLOTS_DIR, "positive_revenue_distribution.png")
    plt.tight_layout()
    plt.savefig(revenue_plot_path, dpi=300)
    plt.close()
    print(f"[+] Salvato grafico Positive Revenue: {revenue_plot_path}")

    # 5.3 Distribuzione Film per Decennio
    valid_decades = movies_df[movies_df["decade"] != "Unknown"]["decade"].value_counts().sort_index()
    plt.figure(figsize=(12, 5))
    sns.barplot(x=valid_decades.index, y=valid_decades.values, hue=valid_decades.index, palette="crest", legend=False)
    plt.title("Distribuzione del Numero di Film per Decennio", fontsize=14)
    plt.xlabel("Decennio")
    plt.ylabel("Numero di Film")
    plt.xticks(rotation=45)
    decade_plot_path = os.path.join(PLOTS_DIR, "movies_by_decade.png")
    plt.tight_layout()
    plt.savefig(decade_plot_path, dpi=300)
    plt.close()
    print(f"[+] Salvato grafico Decenni: {decade_plot_path}")


# ==============================================================================
# Step 6: Preparazione Documenti MongoDB (Movies & Ratings Bridge)
# ==============================================================================
def prepare_movie_documents(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    movies_df = data["movies"]
    credits_df = data["credits"]
    keywords_df = data["keywords"]

    print("\nPreparazione documenti 'movies' con cast, crew e keywords incorporati...")
    credits_map = credits_df.set_index("id")[["cast_parsed", "crew_parsed"]].to_dict(orient="index")
    keywords_map = keywords_df.set_index("id")["keywords_parsed"].to_dict()

    mongo_documents = []
    for _, row in movies_df.iterrows():
        movie_id = int(row["id"])
        c_info = credits_map.get(movie_id, {})
        cast_list = c_info.get("cast_parsed", [])
        crew_list = c_info.get("crew_parsed", [])
        kw_list = keywords_map.get(movie_id, [])

        release_dt = None
        if pd.notna(row["release_datetime"]):
            try:
                release_dt = row["release_datetime"].to_pydatetime()
            except Exception:
                release_dt = None

        doc = {
            "_id": movie_id,
            "title": str(row["title"]) if pd.notna(row["title"]) else "",
            "original_title": str(row["original_title"]) if pd.notna(row["original_title"]) else "",
            "original_language": str(row["original_language"]) if pd.notna(row["original_language"]) else "",
            "overview": str(row["overview"]),
            "tagline": str(row["tagline"]),
            "release_date": release_dt,
            "release_date_str": row["release_date_clean"] if pd.notna(row["release_date_clean"]) else "",
            "decade": row["decade"],
            "runtime": float(row["runtime"]) if pd.notna(row["runtime"]) and row["runtime"] > 0 else None,
            "budget": int(row["budget"]),
            "revenue": int(row["revenue"]),
            "vote_average": float(row["vote_average"]),
            "vote_count": int(row["vote_count"]),
            "genres": row["genres_parsed"],
            "genre_names": row["genre_names"],
            "primary_genre": row["primary_genre"],
            "belongs_to_collection": row["collection_parsed"],
            "production_companies": row["production_companies_parsed"],
            "production_countries": row["production_countries_parsed"],
            "spoken_languages": row["spoken_languages_parsed"],
            "cast": cast_list,
            "crew": crew_list,
            "keywords": kw_list,
        }
        mongo_documents.append(doc)

    print(f"[+] Preparati {len(mongo_documents)} documenti per la collezione 'movies'.")
    return mongo_documents


def process_and_insert_ratings(db, ratings_path: str, links_bridge_map: Dict[int, int], valid_movie_ids: Set[int], batch_size: int = 10000):
    """
    Reads ratings in chunks, bridges movieId via links_bridge_map directly to TMDB ID,
    ensures referential integrity with movies._id, and batch-inserts into MongoDB.
    """
    ratings_col = db["ratings"]
    ratings_col.drop()
    print("\n[+] Collezione 'ratings' inizializzata per l'inserimento.")

    total_inserted = 0
    total_dropped_no_link = 0
    total_dropped_orphan_movie = 0

    chunksize = 100000
    print(f"[+] Elaborazione in streaming dei voti da: {ratings_path} (chunksize={chunksize})...")

    for chunk in pd.read_csv(ratings_path, chunksize=chunksize, low_memory=False):
        # 1. Map MovieLens movieId to TMDB ID
        chunk["tmdb_id"] = chunk["movieId"].map(links_bridge_map)
        missing_link_mask = chunk["tmdb_id"].isna()
        total_dropped_no_link += missing_link_mask.sum()

        valid_chunk = chunk[~missing_link_mask].copy()
        valid_chunk["tmdb_id"] = valid_chunk["tmdb_id"].astype(int)

        # 2. Check referential integrity: ensure movie exists in movies._id
        orphan_mask = ~valid_chunk["tmdb_id"].isin(valid_movie_ids)
        total_dropped_orphan_movie += orphan_mask.sum()

        clean_ratings_chunk = valid_chunk[~orphan_mask].copy()

        # 3. Format documents with movieId = TMDB ID and native ISODate timestamp
        clean_ratings_chunk["timestamp_dt"] = pd.to_datetime(clean_ratings_chunk["timestamp"], unit="s")

        records_to_insert = []
        for _, row in clean_ratings_chunk.iterrows():
            records_to_insert.append({
                "userId": int(row["userId"]),
                "movieId": int(row["tmdb_id"]),  # Direct foreign key pointing to movies._id!
                "rating": float(row["rating"]),
                "timestamp": row["timestamp_dt"].to_pydatetime() if pd.notna(row["timestamp_dt"]) else None,
            })

        # 4. Batch insert
        if records_to_insert:
            for i in range(0, len(records_to_insert), batch_size):
                batch = records_to_insert[i : i + batch_size]
                ratings_col.insert_many(batch, ordered=False)
            total_inserted += len(records_to_insert)
            print(f"    - Inseriti {total_inserted} voti...", end="\r")

    print(f"\n[+] Inserimento voti completato: {total_inserted} documenti inseriti.")
    print(f"    - Voti scartati (nessuna corrispondenza in links.csv): {total_dropped_no_link}")
    print(f"    - Voti scartati (film non presente in movies._id): {total_dropped_orphan_movie}")

    # Indici essenziali per la Query 10
    print("[+] Creazione indici su 'ratings' (userId e movieId)...")
    ratings_col.create_index([("userId", 1)])
    ratings_col.create_index([("movieId", 1)])
    print("[+] Indici su 'ratings' creati con successo.")


# ==============================================================================
# Inserimento MongoDB Completo (Movies + Ratings)
# ==============================================================================
def insert_into_mongodb(data: Dict[str, Any], movie_documents: List[Dict[str, Any]], batch_size: int = 2000):
    print("\n" + "=" * 80)
    print("INSERIMENTO SU MONGODB (CONTAINER DOCKER / SERVER)")
    print("=" * 80)

    if DbConnector is None:
        print("[!] DbConnector non disponibile. Assicurarsi che DbConnector.py sia presente.")
        return

    try:
        connector = DbConnector()
        if not hasattr(connector, "db") or connector.db is None:
            print("[!] Impossibile accedere all'istanza MongoDB. Verificare che il container Docker sia attivo.")
            return

        db = connector.db

        # 1. Inserimento Collezione 'movies'
        movies_col = db["movies"]
        movies_col.drop()
        print("[+] Collezione 'movies' inizializzata.")

        total_movies = len(movie_documents)
        print(f"[+] Inizio inserimento di {total_movies} film...")
        for i in range(0, total_movies, batch_size):
            batch = movie_documents[i : i + batch_size]
            movies_col.insert_many(batch, ordered=False)
            print(f"    - Inseriti {min(i + batch_size, total_movies)} / {total_movies} film", end="\r")

        print(f"\n[+] Inserimento film completato: {total_movies} documenti inseriti.")

        # Indici per 'movies'
        print("[+] Creazione indici su 'movies' per le query...")
        movies_col.create_index([("vote_count", -1)])
        movies_col.create_index([("vote_average", -1)])
        movies_col.create_index([("decade", 1), ("primary_genre", 1)])
        movies_col.create_index([("belongs_to_collection.name", 1)])
        movies_col.create_index([("crew.job", 1), ("crew.name", 1)])
        movies_col.create_index([("cast.name", 1)])
        movies_col.create_index([("overview", "text"), ("tagline", "text")])
        print("[+] Indici su 'movies' creati con successo.")

        # 2. Inserimento Collezione 'ratings' tramite il ponte links_bridge_map
        process_and_insert_ratings(
            db=db,
            ratings_path=data["ratings_path"],
            links_bridge_map=data["links_bridge_map"],
            valid_movie_ids=data["valid_movie_ids"]
        )

        connector.close_connection()
        print("\nProcesso di inserimento di Movies e Ratings completato con successo.")
    except Exception as e:
        print(f"\n[!] Connessione o inserimento MongoDB non riuscito: {e}")
        print("    Suggerimento: Verifica che il container Docker di MongoDB sia in esecuzione.")


# ==============================================================================
# Main Pipeline
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Clean Movies Dataset and prepare MongoDB ingestion.")
    parser.add_argument(
        "--full-ratings",
        action="store_true",
        help="Use full ratings.csv (26M ratings) instead of ratings_small.csv (100k ratings)"
    )
    args = parser.parse_args()

    # 1. Caricamento
    datasets = load_datasets(use_full_ratings=args.full_ratings)

    # 2. Ispezione iniziale
    inspect_initial_data(datasets["movies"])

    # 3. Data Cleaning
    cleaned_datasets = clean_data(datasets)

    # 4. JSON Parsing
    parsed_datasets = parse_json_fields(cleaned_datasets)

    # 5. Visualizzazioni EDA
    generate_visual_explorations(parsed_datasets["movies"])

    # 6. Preparazione Documenti Movies
    movie_docs = prepare_movie_documents(parsed_datasets)

    # 7. Inserimento Completo su MongoDB (Movies + Ratings bridged via links)
    insert_into_mongodb(parsed_datasets, movie_docs)


if __name__ == "__main__":
    main()
