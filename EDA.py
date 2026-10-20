import pandas as pd
import numpy as np
import json
import ast

# calculate the average and biggest entry of the credit list
CREDIT_LIST_PATH = "csvs/credits.csv"

def analyze_credit_list():
    # Load the credit list CSV file into a pandas DataFrame
    print(f"Loading credit list from: {CREDIT_LIST_PATH}")
    df = pd.read_csv(CREDIT_LIST_PATH)
    highest_total = 0
    mean_total = 0
    lowest_total = float('inf')
    total_entries = len(df)
    empty_cast = 0
    empty_crew = 0
    print("load completed, total entries:", total_entries)

    # for each entry
    for _, row in df.iterrows():
        # Some CSV values use Python-style lists with single quotes instead
        # of strict JSON, so parse either representation safely.
        def parse_entries(value):
            if pd.isna(value) or not str(value).strip():
                return []
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return ast.literal_eval(str(value))
        total_cast = len(parse_entries(row["cast"]))
        if total_cast == 0:
            empty_cast += 1
        total_crew = len(parse_entries(row["crew"]))
        if total_crew == 0:
            empty_crew += 1
        total = total_cast + total_crew
        if total > highest_total:
            highest_total = total
        if total < lowest_total and total > 0:
            lowest_total = total
        mean_total += total

    # Calculate the average
    if total_entries > 0:
        mean_total /= total_entries - empty_cast - empty_crew

    print(f"Number of entries with empty cast: {empty_cast}")
    print(f"Number of entries with empty crew: {empty_crew}")
    print(f"Average number of entries in the credit list: {mean_total}")
    print(f"Highest number of entries in the credit list: {highest_total}")
    print(f"Lowest number of entries in the credit list: {lowest_total}")

analyze_credit_list()