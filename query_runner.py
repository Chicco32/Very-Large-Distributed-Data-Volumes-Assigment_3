import pprint
from DbConnector import DbConnector

QUERY_FILE = "queries.js"

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


def main():
    db = connect_to_db()
    
    print_query_header(1, "Considering only crew with job = Director, which 10 directors with ≥ 5 movies have the highest median revenue? Also report each director’s movie count and mean vote_average.")
    result = query_1(db)
    pprint.pprint(result)

    print_query_header(2, "List actor pairs have co-starred in ≥ 3 movies together, their number of co-appearances, and their average movie vote_average. Sort by number of co-appearances.")
    result = query_2(db)
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

main()