"""
Query Runner for Assignment 3 - Part 2 (Queries 1 to 10)
TDT4225 - Very Large, Distributed Data Volumes

Formatted with tabulate and pprint for reporting and presentation.
"""

import os
import sys
import pprint
import statistics
from collections import defaultdict
from tabulate import tabulate
from DbConnector import DbConnector

# Ensure UTF-8 output encoding for symbols and foreign characters on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def connect_to_db():
    """Connects to the MongoDB server and returns the database object."""
    db_connector = DbConnector()
    return db_connector.db


def print_query_header(query_number, query_description):
    """Prints a styled header for a query."""
    print("\n" + "=" * 90)
    print(f"QUERY {query_number}: {query_description}")
    print("=" * 90)


# ------------------------------------------------------------------------------
# Query 1
# ------------------------------------------------------------------------------
def query_1(db):
    """
    1. Considering only crew with job = Director, which 10 directors with >= 5 movies
    have the highest median revenue? Also report each director's movie count and mean vote_average.
    """
    pipeline = [
        {"$unwind": "$crew"},
        {"$match": {"crew.job": "Director"}},
        {"$group": {
            "_id": "$crew.name",
            "movie_count": {"$sum": 1},
            "revenues": {"$push": "$revenue"},
            "mean_vote_average": {"$avg": "$vote_average"}
        }},
        {"$match": {"movie_count": {"$gte": 5}}}
    ]
    raw_results = list(db.movies.aggregate(pipeline))
    for r in raw_results:
        r["median_revenue"] = statistics.median(r["revenues"])
        del r["revenues"]

    raw_results.sort(key=lambda x: x["median_revenue"], reverse=True)
    top_10 = raw_results[:10]

    # Tabulate format
    table_data = []
    for rank, r in enumerate(top_10, 1):
        table_data.append([
            rank,
            r["_id"],
            r["movie_count"],
            f"${r['median_revenue']:>15,.2f}",
            f"{r['mean_vote_average']:.2f}"
        ])

    headers = ["Rank", "Director", "Movies (>= 5)", "Median Revenue ($)", "Mean Vote Average"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return top_10


# ------------------------------------------------------------------------------
# Query 2
# ------------------------------------------------------------------------------
def query_2(db, limit=15):
    """
    2. List actor pairs have co-starred in >= 3 movies together, their number of
    co-appearances, and their average movie vote_average. Sort by number of co-appearances.
    """
    pipeline = [
        {"$project": {
            "actors": {
                "$setUnion": [
                    {
                        "$map": {
                            "input": "$cast",
                            "as": "c",
                            "in": "$$c.name"
                        }
                    }
                ]
            },
            "vote_average": 1
        }}
    ]
    cursor = db.movies.aggregate(pipeline)
    pair_stats = defaultdict(lambda: {"count": 0, "votes": []})

    for m in cursor:
        actors = sorted(list({a for a in m.get("actors", []) if a}))
        n = len(actors)
        vote = m.get("vote_average", 0.0)
        for i in range(n):
            for j in range(i + 1, n):
                pair = (actors[i], actors[j])
                pair_stats[pair]["count"] += 1
                pair_stats[pair]["votes"].append(vote)

    results = []
    for pair, data in pair_stats.items():
        if data["count"] >= 3:
            results.append({
                "actor_pair": list(pair),
                "co_appearances": data["count"],
                "avg_vote_average": round(sum(data["votes"]) / len(data["votes"]), 2)
            })

    results.sort(key=lambda x: (-x["co_appearances"], -x["avg_vote_average"]))
    top_pairs = results[:limit]

    table_data = []
    for rank, r in enumerate(top_pairs, 1):
        table_data.append([
            rank,
            r["actor_pair"][0],
            r["actor_pair"][1],
            r["co_appearances"],
            f"{r['avg_vote_average']:.2f}"
        ])

    headers = ["Rank", "Actor 1", "Actor 2", "Co-appearances", "Avg Vote Average"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return top_pairs


# ------------------------------------------------------------------------------
# Query 3
# ------------------------------------------------------------------------------
def query_3(db):
    """
    3. List the top 10 actors (with >= 10 credited movies) that have the widest genre
    breadth. Report the actor, the number of distinct genres they've appeared in,
    and up to 5 example genres.
    """
    pipeline = [
        {"$unwind": "$cast"},
        {"$unwind": "$genres"},
        {"$group": {
            "_id": {
                "actor": "$cast.name",
                "genre": "$genres.name"
            },
            "movie_ids": {"$addToSet": "$_id"}
        }},
        {"$group": {
            "_id": "$_id.actor",
            "distinct_genres": {"$addToSet": "$_id.genre"},
            "all_movie_ids": {"$push": "$movie_ids"}
        }},
        {"$project": {
            "_id": 1,
            "distinct_genres": 1,
            "genre_count": {"$size": "$distinct_genres"},
            "total_movies": {
                "$size": {
                    "$reduce": {
                        "input": "$all_movie_ids",
                        "initialValue": [],
                        "in": {"$setUnion": ["$$value", "$$this"]}
                    }
                }
            }
        }},
        {"$match": {"total_movies": {"$gte": 10}}},
        {"$sort": {"genre_count": -1, "total_movies": -1}},
        {"$limit": 10},
        {"$project": {
            "actor": "$_id",
            "_id": 0,
            "genre_count": 1,
            "total_movies": 1,
            "example_genres": {"$slice": ["$distinct_genres", 5]}
        }}
    ]
    top_10 = list(db.movies.aggregate(pipeline))

    table_data = []
    for rank, r in enumerate(top_10, 1):
        example_str = ", ".join(r["example_genres"])
        table_data.append([
            rank,
            r["actor"],
            r["genre_count"],
            r["total_movies"],
            example_str
        ])

    headers = ["Rank", "Actor", "Distinct Genres", "Credited Movies", "Example Genres"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return top_10


# ------------------------------------------------------------------------------
# Query 4
# ------------------------------------------------------------------------------
def query_4(db):
    """
    4. For film collections (belongs_to_collection.name not null) with >= 3 movies,
    which 10 collections have the largest total revenue?
    For each, report movie count, total revenue, median vote_average, and the earliest -> latest release date.
    """
    pipeline = [
        {"$match": {
            "belongs_to_collection.name": {"$ne": None, "$exists": True}
        }},
        {"$group": {
            "_id": "$belongs_to_collection.name",
            "movie_count": {"$sum": 1},
            "total_revenue": {"$sum": "$revenue"},
            "votes": {"$push": "$vote_average"},
            "earliest_release_date": {"$min": "$release_date"},
            "latest_release_date": {"$max": "$release_date"}
        }},
        {"$match": {"movie_count": {"$gte": 3}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 10}
    ]
    results = list(db.movies.aggregate(pipeline))
    for r in results:
        r["median_vote_average"] = round(statistics.median(r["votes"]), 2)
        del r["votes"]

    table_data = []
    for rank, r in enumerate(results, 1):
        d_min = r["earliest_release_date"].strftime("%Y-%m-%d") if r.get("earliest_release_date") else "N/A"
        d_max = r["latest_release_date"].strftime("%Y-%m-%d") if r.get("latest_release_date") else "N/A"
        table_data.append([
            rank,
            r["_id"],
            r["movie_count"],
            f"${r['total_revenue']:>15,}",
            f"{r['median_vote_average']:.2f}",
            f"{d_min} -> {d_max}"
        ])

    headers = ["Rank", "Collection", "Movies (>= 3)", "Total Revenue ($)", "Median Vote", "Date Range"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return results


# ------------------------------------------------------------------------------
# Query 5
# ------------------------------------------------------------------------------
def query_5(db, display_limit=25):
    """
    5. By decade (e.g., 1970s, 1980s, ...) and primary genre (first element in genres),
    what is the median runtime and movie count?
    List results sorted by decade then median runtime (desc).
    """
    pipeline = [
        {"$match": {
            "decade": {"$ne": "Unknown"},
            "primary_genre": {"$ne": "Unknown"},
            "runtime": {"$ne": None, "$gt": 0}
        }},
        {"$group": {
            "_id": {
                "decade": "$decade",
                "primary_genre": "$primary_genre"
            },
            "movie_count": {"$sum": 1},
            "runtimes": {"$push": "$runtime"}
        }}
    ]
    raw_results = list(db.movies.aggregate(pipeline))
    results = []
    for r in raw_results:
        results.append({
            "decade": r["_id"]["decade"],
            "primary_genre": r["_id"]["primary_genre"],
            "movie_count": r["movie_count"],
            "median_runtime": round(statistics.median(r["runtimes"]), 1)
        })

    results.sort(key=lambda x: (x["decade"], -x["median_runtime"]))

    table_data = []
    for r in results[:display_limit]:
        table_data.append([
            r["decade"],
            r["primary_genre"],
            f"{r['movie_count']:,}",
            f"{r['median_runtime']:.1f} min"
        ])

    headers = ["Decade", "Primary Genre", "Movie Count", "Median Runtime"]
    print(f"\nShowing top {display_limit} entries (Total combinations: {len(results)}):")
    print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return results


# ------------------------------------------------------------------------------
# Query 6
# ------------------------------------------------------------------------------
def query_6(db):
    """
    6. For each movie's top-billed 5 cast (by order), what is the proportion of female cast?
    Aggregate by decade and list decades sorted by average female proportion (desc),
    including movie counts used. Unknown gender may be ignored.
    """
    pipeline = [
        {"$match": {
            "decade": {"$ne": "Unknown"},
            "cast.0": {"$exists": True}
        }},
        {"$project": {
            "decade": 1,
            "top5_cast": {"$slice": ["$cast", 5]}
        }}
    ]
    cursor = db.movies.aggregate(pipeline)
    decade_stats = defaultdict(lambda: {"proportions": []})

    for m in cursor:
        decade = m.get("decade")
        top5 = m.get("top5_cast", [])
        females = sum(1 for c in top5 if c.get("gender") == 1)
        males = sum(1 for c in top5 if c.get("gender") == 2)
        total_known = females + males
        if total_known > 0:
            decade_stats[decade]["proportions"].append(females / total_known)

    results = []
    for dec, data in decade_stats.items():
        props = data["proportions"]
        avg_prop = sum(props) / len(props)
        results.append({
            "decade": dec,
            "movie_count_used": len(props),
            "avg_female_proportion": round(avg_prop, 4),
            "percentage": f"{avg_prop * 100:.2f}%"
        })

    results.sort(key=lambda x: x["avg_female_proportion"], reverse=True)

    table_data = []
    for rank, r in enumerate(results, 1):
        table_data.append([
            rank,
            r["decade"],
            f"{r['movie_count_used']:,}",
            f"{r['avg_female_proportion']:.4f}",
            r["percentage"]
        ])

    headers = ["Rank", "Decade", "Qualifying Movies", "Avg Female Ratio", "Female %"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return results


# ------------------------------------------------------------------------------
# Query 7
# ------------------------------------------------------------------------------
def query_7(db):
    """
    7. Using a text search over overview and tagline, which 20 movies matching "noir"
    or "neo-noir" (and vote_count >= 50) have the highest vote_average?
    Return title, year, vote_average, and vote_count.
    """
    pipeline = [
        {"$match": {
            "$text": {"$search": "noir"},
            "vote_count": {"$gte": 50},
            "$or": [
                {"overview": {"$regex": r"neo[- ]noir|\bnoir\b", "$options": "i"}},
                {"tagline": {"$regex": r"neo[- ]noir|\bnoir\b", "$options": "i"}}
            ]
        }},
        {"$project": {
            "_id": 0,
            "title": 1,
            "decade": "$decade",
            "release_date": "$release_date_str",
            "vote_average": 1,
            "vote_count": 1
        }},
        {"$sort": {"vote_average": -1}},
        {"$limit": 20}
    ]
    results = list(db.movies.aggregate(pipeline))

    table_data = []
    for rank, r in enumerate(results, 1):
        table_data.append([
            rank,
            r["title"],
            r.get("release_date") or r.get("decade", "N/A"),
            f"{r['vote_count']:,}",
            f"{r['vote_average']:.1f}"
        ])

    headers = ["Rank", "Title", "Release Date", "Vote Count (>= 50)", "Vote Average"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return results


# ------------------------------------------------------------------------------
# Query 8
# ------------------------------------------------------------------------------
def query_8(db):
    """
    8. Which 20 director-actor pairs with >= 3 collaborations (same movie) have the highest
    mean vote_average, considering only movies with vote_count >= 100?
    Include the pair's films count and mean revenue.
    """
    pipeline = [
        {"$match": {"vote_count": {"$gte": 100}}},
        {"$project": {
            "directors": {
                "$filter": {
                    "input": "$crew",
                    "as": "c",
                    "cond": {"$eq": ["$$c.job", "Director"]}
                }
            },
            "cast": 1,
            "vote_average": 1,
            "revenue": 1
        }}
    ]
    cursor = db.movies.aggregate(pipeline)
    collab_stats = defaultdict(lambda: {"count": 0, "votes": [], "revenues": []})

    for m in cursor:
        dirs = {c["name"] for c in m.get("directors", []) if c.get("name")}
        actors = {c["name"] for c in m.get("cast", []) if c.get("name")}
        v = m.get("vote_average", 0.0)
        rev = m.get("revenue", 0)
        for d in dirs:
            for a in actors:
                if d != a:
                    pair = (d, a)
                    collab_stats[pair]["count"] += 1
                    collab_stats[pair]["votes"].append(v)
                    collab_stats[pair]["revenues"].append(rev)

    results = []
    for (d, a), stats in collab_stats.items():
        if stats["count"] >= 3:
            results.append({
                "director": d,
                "actor": a,
                "film_count": stats["count"],
                "mean_vote_average": round(sum(stats["votes"]) / len(stats["votes"]), 2),
                "mean_revenue": round(sum(stats["revenues"]) / len(stats["revenues"]), 2)
            })

    results.sort(key=lambda x: (-x["mean_vote_average"], -x["film_count"]))
    top_20 = results[:20]

    table_data = []
    for rank, r in enumerate(top_20, 1):
        table_data.append([
            rank,
            r["director"],
            r["actor"],
            r["film_count"],
            f"{r['mean_vote_average']:.2f}",
            f"${r['mean_revenue']:>14,.2f}"
        ])

    headers = ["Rank", "Director", "Actor", "Collabs (>= 3)", "Mean Vote", "Mean Revenue ($)"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return top_20


# ------------------------------------------------------------------------------
# Query 9
# ------------------------------------------------------------------------------
def query_9(db):
    """
    9. Among movies where original_language != "en" but at least one production company
    or country is United States, which are the top 10 original languages by count?
    For each language, report the count and one example title.
    """
    pipeline = [
        {"$match": {
            "original_language": {"$ne": "en", "$exists": True, "$nin": ["", None]},
            "$or": [
                {"production_countries.iso_3166_1": "US"},
                {"production_countries.name": "United States of America"},
                {"production_companies.name": {"$regex": r"\b(United States|USA)\b"}}
            ]
        }},
        {"$group": {
            "_id": "$original_language",
            "count": {"$sum": 1},
            "example_title": {"$first": "$title"}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top_10 = list(db.movies.aggregate(pipeline))

    table_data = []
    for rank, r in enumerate(top_10, 1):
        table_data.append([
            rank,
            r["_id"],
            f"{r['count']:,}",
            r["example_title"]
        ])

    headers = ["Rank", "Language Code", "Movie Count", "Example Title"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    return top_10


# ------------------------------------------------------------------------------
# Query 10
# ------------------------------------------------------------------------------
def query_10(db):
    """
    10. For each user, what is their ratings count, population variance of ratings,
    and number of distinct genres rated?
    List the top 10 most genre-diverse users, and separately the top 10
    highest-variance users (only users with >= 20 ratings).
    """
    pipeline = [
        {"$group": {
            "_id": "$userId",
            "ratings_count": {"$sum": 1},
            "ratings": {"$push": "$rating"},
            "movie_ids": {"$addToSet": "$movieId"}
        }},
        {"$match": {"ratings_count": {"$gte": 20}}},
        {"$lookup": {
            "from": "movies",
            "localField": "movie_ids",
            "foreignField": "_id",
            "as": "movies_info"
        }},
        {"$project": {
            "_id": 1,
            "ratings_count": 1,
            "ratings": 1,
            "genres": "$movies_info.genre_names"
        }}
    ]
    cursor = db.ratings.aggregate(pipeline)
    user_results = []
    for u in cursor:
        uid = u["_id"]
        cnt = u["ratings_count"]
        r_list = u["ratings"]
        var = statistics.pvariance(r_list) if len(r_list) > 1 else 0.0
        genres = set()
        for g_list in u.get("genres", []):
            if isinstance(g_list, list):
                for g in g_list:
                    genres.add(g)
        user_results.append({
            "userId": uid,
            "ratings_count": cnt,
            "variance": round(var, 4),
            "genre_count": len(genres)
        })

    top_genre_diverse = sorted(user_results, key=lambda x: (-x["genre_count"], -x["ratings_count"]))[:10]
    top_variance = sorted(user_results, key=lambda x: (-x["variance"], -x["ratings_count"]))[:10]

    print("\n>>> PART A: Top 10 Most Genre-Diverse Users (Users with >= 20 ratings)")
    table_diverse = []
    for rank, r in enumerate(top_genre_diverse, 1):
        table_diverse.append([
            rank,
            r["userId"],
            r["genre_count"],
            f"{r['ratings_count']:,}",
            f"{r['variance']:.4f}"
        ])
    headers_diverse = ["Rank", "User ID", "Distinct Genres", "Ratings Count", "Population Variance"]
    print(tabulate(table_diverse, headers=headers_diverse, tablefmt="fancy_grid"))

    print("\n>>> PART B: Top 10 Highest-Variance Users (Users with >= 20 ratings)")
    table_var = []
    for rank, r in enumerate(top_variance, 1):
        table_var.append([
            rank,
            r["userId"],
            f"{r['variance']:.4f}",
            f"{r['ratings_count']:,}",
            r["genre_count"]
        ])
    headers_var = ["Rank", "User ID", "Population Variance", "Ratings Count", "Distinct Genres"]
    print(tabulate(table_var, headers=headers_var, tablefmt="fancy_grid"))

    return {
        "top_10_most_genre_diverse_users": top_genre_diverse,
        "top_10_highest_variance_users": top_variance
    }


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
def main():
    db = connect_to_db()

    # Query 1
    print_query_header(1, "Considering only crew with job = Director, which 10 directors with >= 5 movies have the highest median revenue? Also report each director's movie count and mean vote_average.")
    r1 = query_1(db)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r1[:2])

    # Query 2
    print_query_header(2, "List actor pairs have co-starred in >= 3 movies together, their number of co-appearances, and their average movie vote_average. Sort by number of co-appearances.")
    r2 = query_2(db, limit=10)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r2[:2])

    # Query 3
    print_query_header(3, "List the top 10 actors (with >= 10 credited movies) that have the widest genre breadth. Report the actor, the number of distinct genres they've appeared in, and up to 5 example genres.")
    r3 = query_3(db)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r3[:2])

    # Query 4
    print_query_header(4, "For film collections (belongs_to_collection.name not null) with >= 3 movies, which 10 collections have the largest total revenue? For each, report movie count, total revenue, median vote_average, and the earliest -> latest release date.")
    r4 = query_4(db)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r4[:2])

    # Query 5
    print_query_header(5, "By decade (e.g., 1970s, 1980s, ...) and primary genre (first element in genres), what is the median runtime and movie count? List results sorted by decade then median runtime (desc).")
    r5 = query_5(db, display_limit=15)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r5[:2])

    # Query 6
    print_query_header(6, "For each movie's top-billed 5 cast (by order), what is the proportion of female cast? Aggregate by decade and list decades sorted by average female proportion (desc), including movie counts used. Unknown gender may be ignored.")
    r6 = query_6(db)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r6[:2])

    # Query 7
    print_query_header(7, "Using a text search over overview and tagline, which 20 movies matching 'noir' or 'neo-noir' (and vote_count >= 50) have the highest vote_average? Return title, year, vote_average, and vote_count.")
    r7 = query_7(db)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r7[:2])

    # Query 8
    print_query_header(8, "Which 20 director-actor pairs with >= 3 collaborations (same movie) have the highest mean vote_average, considering only movies with vote_count >= 100? Include the pair's films count and mean revenue.")
    r8 = query_8(db)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r8[:2])

    # Query 9
    print_query_header(9, "Among movies where original_language != 'en' but at least one production company or country is United States, which are the top 10 original languages by count? For each language, report the count and one example title.")
    r9 = query_9(db)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint(r9[:2])

    # Query 10
    print_query_header(10, "For each user, what is their ratings count, population variance of ratings, and number of distinct genres rated? List the top 10 most genre-diverse users, and separately the top 10 highest-variance users (only users with >= 20 ratings).")
    r10 = query_10(db)
    print("\n[Sample Raw Output from MongoDB (pprint)]:")
    pprint.pprint({
        "diverse_sample": r10["top_10_most_genre_diverse_users"][:1],
        "variance_sample": r10["top_10_highest_variance_users"][:1]
    })


if __name__ == "__main__":
    main()
