import pprint
from DbConnector import DbConnector

def connect_to_db():
    """
    Connects to the MongoDB server and returns the database object.
    """
    db_connector = DbConnector()
    return db_connector.db

def print_query_header(query_number, query_description):
    """
    Prints the header for a query.
    """
    print("\n-----------------------------------------------")
    print(f"Query {query_number}: {query_description}")
    print("-----------------------------------------------\n")

# 1. Considering only crew with job = Director, 
# which 10 directors with ≥ 5 movies have the highest median revenue? 
# Also report each director’s movie count and mean vote_average.

def query_1(db):
    """
    Query 1: Considering only crew with job = Director, 
    which 10 directors with ≥ 5 movies have the highest median revenue? 
    Also report each director’s movie count and mean vote_average.
    """
    pipeline = [
        {"$match": {"crew.job": "Director"}},
        {"$group": {
            "_id": "$crew.name",
            "movie_count": {"$sum": 1},
            "median_revenue": {"$avg": "$revenue"},
            "mean_vote_average": {"$avg": "$vote_average"}
        }},
        {"$match": {"movie_count": {"$gte": 5}}},
        {"$sort": {"median_revenue": -1}},
        {"$limit": 10}
    ]
    
    result = db.movies.aggregate(pipeline)
    return list(result)


# 2. List actor pairs have co-starred in ≥ 3 movies together, 
# their number of co-appearances, 
# and their average movie vote_average. 
# Sort by number of co-appearances.

def query_2(db):
    """
    Query 2: List actor pairs have co-starred in ≥ 3 movies together, 
    their number of co-appearances, 
    and their average movie vote_average. 
    Sort by number of co-appearances.
    """
    #crate a pipllin that generate all possible pairs of actors in the cast of each movie,
    #then filter the pairs that have co-starred in ≥ 3 movies together, and finally sort by number of co-appearances.
    pipeline = [
        {"$unwind": "$cast"},
        {"$group": {
            "_id": "$_id",
            "cast": {"$push": "$cast.name"},
            "vote_average": {"$first": "$vote_average"}
        }},
        {"$project": {
            "pairs": {"$setUnion": [{"$map": {
                "input": "$cast",
                "as": "actor1",
                "in": {"$map": {
                    "input": "$cast",
                    "as": "actor2",
                    "in": {"$cond": [{"$ne": ["$$actor1", "$$actor2"]}, ["$$actor1", "$$actor2"], None]}
                }}
            }}]},
            "vote_average": 1
        }},
        {"$unwind": "$pairs"},
        {"$group": {
            "_id": "$pairs",
            "co_appearances": {"$sum": 1},
            "avg_vote_average": {"$avg": "$vote_average"}
        }},
        {"$match": {"co_appearances": {"$gte": 3}}},
        {"$sort": {"co_appearances": -1}}
    ]
    
    result = db.movies.aggregate(pipeline)
    return list(result)


#3. List the top 10 actors (with ≥ 10 credited movies) that have the widest genre breadth. 
# Report the actor, the number of distinct genres they’ve appeared in, and up to 5 example genres.

def query_3(db):
    """
    Query 3: List the top 10 actors (with ≥ 10 credited movies) that have the widest genre breadth. 
    Report the actor, the number of distinct genres they’ve appeared in, and up to 5 example genres.
    """
    pipeline = [
        {"$unwind": "$cast"},
        {"$group": {
            "_id": "$cast.name",
            "distinct_genres": {"$addToSet": "$genres.name"},
            "movie_count": {"$sum": 1}
        }},
        {"$project": {
            "genre_count": {"$size": "$distinct_genres"},
            "example_genres": {"$slice": ["$distinct_genres", 5]},
            "movie_count": 1
        }},
        {"$match": {"movie_count": {"$gte": 10}}},
        {"$sort": {"genre_count": -1}},
        {"$limit": 10}
    ]
    
    result = db.movies.aggregate(pipeline)
    return list(result)


# 4. For fi lm collections (belongs_to_collection.name not null) with ≥ 3 movies,
# which 10 collections have the largest total revenue? 
# For each, report movie count, total revenue, median vote_average, 
# and the earliest → latest release date.

def query_4(db):
    """
    Query 4: For film collections (belongs_to_collection.name not null) with ≥ 3 movies,
    which 10 collections have the largest total revenue? 
    For each, report movie count, total revenue, median vote_average, 
    and the earliest → latest release date.
    """
    pipeline = [
        {"$match": {"belongs_to_collection.name": {"$ne": None}}},
        {"$group": {
            "_id": "$belongs_to_collection.name",
            "movie_count": {"$sum": 1},
            "total_revenue": {"$sum": "$revenue"},
            "median_vote_average": {"$avg": "$vote_average"},
            "earliest_release_date": {"$min": "$release_date"},
            "latest_release_date": {"$max": "$release_date"}
        }},
        {"$match": {"movie_count": {"$gte": 3}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 10}
    ]
    
    result = db.movies.aggregate(pipeline)
    return list(result)

# 5. By decade (e.g., 1970s, 1980s, …) and primary genre (fi rst element in genres),
# what is the median runtime and movie count? 
# List results sorted by decade then median runtime (desc).

def query_5(db):
    """
    Query 5: By decade (e.g., 1970s, 1980s, …) and primary genre (first element in genres),
    what is the median runtime and movie count? 
    List results sorted by decade then median runtime (desc).
    """
    pipeline = [
        {"$project": {
            "decade": {"$concat": [
                {"$toString": {"$multiply": [
                    {"$floor": {"$divide": [{"$year": "$release_date"}, 10]}},
                    10
                ]}},
                "s"
            ]},
            "runtime": 1
        }},
        {"$group": {
            "_id": "$decade",
            "median_runtime": {"$avg": "$runtime"},
            "movie_count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1, "median_runtime": -1}}
    ]
    
    result = db.movies.aggregate(pipeline)
    return list(result)

# For each movie’s top-billed 5 cast (by order), 
# what is the proportion of female cast? Aggregate by decade 
# and list decades sorted by average female proportion (desc),
# including movie counts used. Unknown gender may be ignored

def query_6(db):
    """
    Query 6: For each movie’s top-billed 5 cast (by order), 
    what is the proportion of female cast? Aggregate by decade 
    and list decades sorted by average female proportion (desc),
    including movie counts used. Unknown gender may be ignored.
    """
    
    pipeline = [
        {"$match": {"release_date": {"$ne": None}}},

        # decade + solo i gender dei primi 5 (order < 5), scartando gender 0 (sconosciuto)
        {"$project": {
            "decade": {"$concat": [
                {"$toString": {"$multiply": [
                    {"$floor": {"$divide": [{"$year": "$release_date"}, 10]}},
                    10
                ]}},
                "s"
            ]},
            "known": {"$filter": {
                "input": {"$map": {
                    "input": {"$filter": {
                        "input": "$cast",
                        "as": "c",
                        "cond": {"$lt": ["$$c.order", 5]}
                    }},
                    "as": "c",
                    "in": "$$c.gender"
                }},
                "as": "g",
                "cond": {"$in": ["$$g", [1, 2]]}
            }}
        }},

        # tengo solo i film con almeno un attore di genere noto
        {"$match": {"known": {"$ne": []}}},

        # proporzione di donne per ogni film
        {"$project": {
            "decade": 1,
            "female_prop": {"$divide": [
                {"$size": {"$filter": {
                    "input": "$known",
                    "as": "g",
                    "cond": {"$eq": ["$$g", 1]}
                }}},
                {"$size": "$known"}
            ]}
        }},

        # media per decennio + numero di film usati
        {"$group": {
            "_id": "$decade",
            "avg_female_proportion": {"$avg": "$female_prop"},
            "movie_count": {"$sum": 1}
        }},

        {"$project": {
            "_id": 0,
            "decade": "$_id",
            "avg_female_proportion": {"$round": ["$avg_female_proportion", 3]},
            "movie_count": 1
        }},

        {"$sort": {"avg_female_proportion": -1}}
    ]
    return list(db.movies.aggregate(pipeline))

# Using a text search over overview and tagline, 
# which 20 movies matching “noir” or “neo-noir” (and vote_count ≥ 50) 
# have the highest vote_average? Return title, year, vote_average, and vote_count.

def query_7(db):
    """
    Query 7: Using a text search over overview and tagline, 
    which 20 movies matching “noir” or “neo-noir” (and vote_count ≥ 50) 
    have the highest vote_average? Return title, year, vote_average, and vote_count.
    """
    pipeline = [
        {"$match": {
            "$text": {"$search": "noir"},
            "vote_count": {"$gte": 50}
        }},
        {"$project": {
            "title": 1,
            "year": {"$year": "$release_date"},
            "vote_average": 1,
            "vote_count": 1
        }},
        {"$sort": {"vote_average": -1}},
        {"$limit": 20}
    ]
    
    result = db.movies.aggregate(pipeline)
    return list(result)

# 8. Which 20 director–actor pairs with ≥ 3 collaborations (same movie) 
# have the highest mean vote_average, c
# onsidering only movies with vote_count ≥ 100?
# Include the pair’s films count and mean revenue.

def query_8(db):
    """
    Query 8: Which 20 director–actor pairs with ≥ 3 collaborations (same movie) 
    have the highest mean vote_average, considering only movies with vote_count ≥ 100?
    Include the pair’s films count and mean revenue.
    """
    pipeline = [
        {"$match": {"vote_count": {"$gte": 100}}},
        {"$unwind": "$crew"},
        {"$match": {"crew.job": "Director"}},
        {"$unwind": "$cast"},
        {"$group": {
            "_id": {"director": "$crew.name", "actor": "$cast.name"},
            "collaborations": {"$sum": 1},
            "mean_vote_average": {"$avg": "$vote_average"},
            "mean_revenue": {"$avg": "$revenue"}
        }},
        {"$match": {"collaborations": {"$gte": 3}}},
        {"$sort": {"mean_vote_average": -1}},
        {"$limit": 20}
    ]
    
    result = db.movies.aggregate(pipeline)
    return list(result)

# 9. Among movies where original_language ≠ "en" 
# but at least one production company or country is United States, 
# which are the top 10 original languages by count? For each language,
# report the count and one example title.

def query_9(db):
    """
    Query 9: Among movies where original_language ≠ "en" 
    but at least one production company or country is United States, 
    which are the top 10 original languages by count? For each language,
    report the count and one example title.
    """
    pipeline = [
        {"$match": {
            "original_language": {"$ne": "en"},
            "production_countries.name": {"$eq": "United States of America"}
        }},
        {"$group": {
            "_id": "$original_language",
            "count": {"$sum": 1},
            "example_title": {"$first": "$title"}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    
    result = db.movies.aggregate(pipeline)
    return list(result)

# 10. For each user, what is their ratings count,
# population variance of ratings, and number of distinct genres rated? 
# List the top 10 most genre-diverse users, and separately the top 10 highest-variance users 
# (only users with ≥ 20 ratings).

def query_10(db):
    """
    Query 10: For each user, what is their ratings count,
    population variance of ratings, and number of distinct genres rated? 
    List the top 10 most genre-diverse users, and separately the top 10 highest-variance users 
    (only users with ≥ 20 ratings).
    """
    pipeline = [
        {"$lookup": {
            "from": "movies",
            "localField": "movieId",
            "foreignField": "_id",   # <-- metti qui il campo reale (vedi check sotto)
            "as": "movie"
        }},
        {"$unwind": "$movie"},

        {"$group": {
            "_id": "$userId",
            "ratings_count": {"$sum": 1},
            "ratings_stddev": {"$stdDevPop": "$rating"},
            "genre_lists": {"$push": "$movie.genres.name"}
        }},

        # filtro ≥ 20 voti
        {"$match": {"ratings_count": {"$gte": 20}}},

        {"$project": {
            "ratings_count": 1,
            "ratings_variance": {"$round": [{"$pow": ["$ratings_stddev", 2]}, 4]},
            "distinct_genres": {"$reduce": {
                "input": "$genre_lists",
                "initialValue": [],
                "in": {"$setUnion": ["$$value", "$$this"]}
            }}
        }},
        {"$project": {
            "ratings_count": 1,
            "ratings_variance": 1,
            "distinct_genres_count": {"$size": "$distinct_genres"}
        }},

        {"$facet": {
            "most_genre_diverse_users": [
                {"$sort": {"distinct_genres_count": -1, "ratings_count": -1}},
                {"$limit": 10}
            ],
            "highest_variance_users": [
                {"$sort": {"ratings_variance": -1}},
                {"$limit": 10}
            ]
        }}
    ]
    return list(db.ratings.aggregate(pipeline, allowDiskUse=True))

def main():
    db = connect_to_db()
    
    print_query_header(1, "Considering only crew with job = Director, which 10 directors with ≥ 5 movies have the highest median revenue? Also report each director’s movie count and mean vote_average.")
    result = query_1(db)
    pprint.pprint(result)

    print_query_header(2, "List actor pairs have co-starred in ≥ 3 movies together, their number of co-appearances, and their average movie vote_average. Sort by number of co-appearances.")
    #result = query_2(db)
    pprint.pprint(result)

    print_query_header(3, "List the top 10 actors (with ≥ 10 credited movies) that have the widest genre breadth. Report the actor, the number of distinct genres they’ve appeared in, and up to 5 example genres.")
    result = query_3(db)
    pprint.pprint(result)

    print_query_header(4, "For film collections (belongs_to_collection.name not null) with ≥ 3 movies, which 10 collections have the largest total revenue? For each, report movie count, total revenue, median vote_average, and the earliest → latest release date.")
    result = query_4(db)
    pprint.pprint(result)
    
    print_query_header(5, "By decade (e.g., 1970s, 1980s, …) and primary genre (first element in genres), what is the median runtime and movie count? List results sorted by decade then median runtime (desc).")
    result = query_5(db)
    pprint.pprint(result)

    print_query_header(6, "For each movie’s top-billed 5 cast (by order), what is the proportion of female cast? Aggregate by decade and list decades sorted by average female proportion (desc), including movie counts used. Unknown gender may be ignored.")
    result = query_6(db)
    pprint.pprint(result)

    print_query_header(7, "Using a text search over overview and tagline, which 20 movies matching “noir” or “neo-noir” (and vote_count ≥ 50) have the highest vote_average? Return title, year, vote_average, and vote_count.")
    result = query_7(db)
    pprint.pprint(result)
    
    print_query_header(8, "Which 20 director–actor pairs with ≥ 3 collaborations (same movie) have the highest mean vote_average, considering only movies with vote_count ≥ 100? Include the pair’s films count and mean revenue.")
    result = query_8(db)
    pprint.pprint(result)
    
    print_query_header(9, "Among movies where original_language ≠ 'en' but at least one production company or country is United States, which are the top 10 original languages by count? For each language, report the count and one example title.")
    result = query_9(db)
    pprint.pprint(result)
    
    print_query_header(10, "For each user, what is their ratings count, population variance of ratings, and number of distinct genres rated? List the top 10 most genre-diverse users, and separately the top 10 highest-variance users (only users with ≥ 20 ratings).")
    result = query_10(db)
    pprint.pprint(result)

main()