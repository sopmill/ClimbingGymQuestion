"""Climbing Gym as Third Place Global Survey Responses"""
"""Extract the data, transform, validate, and load"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw" / "responses.csv"
OUT = BASE / "data" / "processed"


#ordering data properly
LIKERT = {"Strongly Disagree": 1, "Disagree": 2, "Neutral": 3, "Agree": 4, "Strongly Agree": 5}
TRAVEL_ORDER = ["Less than 15 minutes", "15-30 minutes", "30-45 minutes",
                "45-60 minutes", "More than 60 minutes"]
AGE_ORDER = ["Under 20", "20s", "30s", "40s", "50s", "60s", "Over 60"]
EXPERIENCE_ORDER = ["Less than 1 year", "1-3 years", "3-5 years", "5-10 years", "More than 10 years"]


#shortening the names of form questions
RENAME = {
    "Timestamp": "submitted_at",
    "travel one way": "travel_time",
    "How often do you go": "visits_per_week",
    "hours per visit": "hours_per_visit",
    "meaningful friendships": "likert_friendships",
    "sense of belonging": "likert_belonging",
    "even when I am not actively climbing": "likert_enjoy_not_climbing",
    "socialize with other climbers outside": "likert_socialize_outside",
    "important part of my social life": "likert_social_life",
    "without needing to make specific plans": "likert_comfortable_alone",
    "describes your experience": "experience_traits",
    "your third place": "is_third_place",
    "Why and how did you get into": "story",
}

def extract(path: Path = RAW) -> pd.DataFrame:
    return pd.read_csv(path)



#reframing the age question to be more readable
def collapse_grid(df: pd.DataFrame, prefix: str, new_col: str, order: list) -> pd.DataFrame:
    cols = [c for c in df.columns if c.startswith(prefix)]
    labels = {c: re.search(r"\[(.*)\]", c).group(1).strip() for c in cols}
    grid = df[cols].rename(columns=labels).notna()
    df[new_col] = grid.idxmax(axis=1).where(grid.any(axis=1))
    df[new_col] = pd.Categorical(df[new_col], categories=order, ordered=True)
    return df.drop(columns=cols)



def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = collapse_grid(df, "What is your age group?", "age_group", AGE_ORDER)
    df = collapse_grid(df, "How long have you been climbing?", "climbing_experience", EXPERIENCE_ORDER)

    new_names = {}
    for col in df.columns:
        for key, name in RENAME.items():
            if key.lower() in col.lower():
                new_names[col] = name
                break
    df = df.rename(columns=new_names)


    df["submitted_at"] = pd.to_datetime(df["submitted_at"], format="%m/%d/%Y %H:%M:%S")
    df["travel_time"] = pd.Categorical(df["travel_time"], categories=TRAVEL_ORDER, ordered=True)
    df["is_third_place"] = df["is_third_place"].map({"Yes": True, "No": False})
 
    likert_cols = [c for c in df.columns if c.startswith("likert_")]
    for c in likert_cols:
        df[c] = df[c].map(LIKERT).astype("Int64")
    df["social_score"] = df[likert_cols].mean(axis=1).round(2)   # simple composite
 
    df["story"] = df["story"].str.strip().replace("", pd.NA)
    df.insert(0, "respondent_id", range(1, len(df) + 1))
    return df



def build_traits_table(df: pd.DataFrame) -> pd.DataFrame:
    """Checkbox answers -> one row per (respondent, trait)."""
    # Split on '., ' / '.,' so we don't break on commas inside a trait
    traits = df.set_index("respondent_id")["experience_traits"].dropna() \
               .str.split(r"\.,\s*").explode().str.strip().str.rstrip(".")
    return traits.rename("trait").reset_index()
 
 
def validate(df: pd.DataFrame, traits: pd.DataFrame) -> None:
    assert len(df) == 277, f"expected 277 rows, got {len(df)}"
    assert df["respondent_id"].is_unique
    assert df["is_third_place"].notna().all()
    assert df["visits_per_week"].dropna().between(0, 7).all()
    assert df["hours_per_visit"].dropna().between(0, 12).all()
    assert set(traits["respondent_id"]) <= set(df["respondent_id"])
    print("validation passed")
 
 
def load(df: pd.DataFrame, traits: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "responses_clean.csv", index=False)
    traits.to_csv(OUT / "respondent_traits.csv", index=False)
    with sqlite3.connect(OUT / "survey.db") as con:
        df.drop(columns=["experience_traits"]).to_sql("respondents", con, if_exists="replace", index=False)
        traits.to_sql("respondent_traits", con, if_exists="replace", index=False)
    try:
        df.to_parquet(OUT / "responses_clean.parquet", index=False)   # needs pyarrow
    except ImportError:
        print("pyarrow not installed; skipped parquet")
 
 
if __name__ == "__main__":
    raw = extract()
    clean = transform(raw)
    traits = build_traits_table(clean)
    validate(clean, traits)
    load(clean, traits)
    print(clean.drop(columns=["story", "experience_traits"]).head())
    print(clean.isna().sum()[lambda s: s > 0])
    print(traits["trait"].value_counts())
 
