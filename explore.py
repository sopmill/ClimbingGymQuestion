import sqlite3
import pandas as pd
from pathlib import Path

db = Path(__file__).resolve().parent / "data" / "processed" / "survey.db"
con = sqlite3.connect(db)

#third place yes/no vs. average social score
print(pd.read_sql("""
    SELECT is_third_place, COUNT(*) AS n, ROUND(AVG(social_score), 2) AS avg_social
    FROM respondents GROUP BY is_third_place
""", con))

#which experiences go with calling the gym a third place?
print(pd.read_sql("""
    SELECT t.trait, COUNT(*) AS n,
           ROUND(AVG(r.is_third_place) * 100, 1) AS pct_third_place
    FROM respondent_traits t JOIN respondents r USING (respondent_id)
    GROUP BY t.trait ORDER BY pct_third_place DESC
""", con))

#third place rate by how long they've been climbing
print(pd.read_sql("""
    SELECT climbing_experience, COUNT(*) AS n,
           ROUND(AVG(is_third_place) * 100, 1) AS pct_third_place
    FROM respondents GROUP BY climbing_experience
""", con))