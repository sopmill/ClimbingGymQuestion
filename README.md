# Are Climbing Gyms Third Places?

An end-to-end data project built on a Google Forms survey of 277 climbers collected from posting the Form on Facebook climbing groups and Reddit climbing boards.
A *third place* is a social space that is neither home (first place) nor work (second place). This project cleans the raw survey export into a tested pipeline, stores it in a small relational database, and analyzes why a climber may refer to their gym as their third place.

## Pipeline

```
data/raw/responses.csv  ->  extract -> transform -> validate -> load
                                                     |
                data/processed/{responses_clean.csv, .parquet, survey.db}
                                                     |
                                      analysis/analyze.py -> reports/
```

| Step | File | What it does |
|------|------|--------------|
| Extract | `src/climbing/extract.py` | Reads the raw Forms export unchanged |
| Transform | `src/climbing/transform.py` | Short column names, collapses the one-column-per-option grids (age, climbing experience) into single ordered columns, Likert text to 1-5, yes/no to boolean, builds a `social_score` composite |
| Normalize | `build_traits_table()` | Splits the checkbox answers into a `respondent_traits` table (one row per respondent per trait) |
| Validate | `src/climbing/validate.py` | Range, uniqueness, and referential-integrity checks |
| Load | `src/climbing/load.py` | Writes CSV, Parquet, and a SQLite database (`respondents`, `respondent_traits`) |

## Run it

```bash
python -m pip install -r requirements.txt
# put the survey CSV at data/raw/responses.csv
python run_pipeline.py
python analysis/analyze.py
python -m pytest
```

## Data model

- `respondents`: one row per person (`respondent_id`, `age_group`, `climbing_experience`, `travel_time`, `visits_per_week`, `hours_per_visit`, six `likert_*` columns, `social_score`, `is_third_place`, `story`)
- `respondent_traits`: `respondent_id`, `trait` (many per respondent)

Example query:

```sql
SELECT t.trait, COUNT(*) AS n, ROUND(AVG(r.is_third_place) * 100, 1) AS pct_third_place
FROM respondent_traits t JOIN respondents r USING (respondent_id)
GROUP BY t.trait ORDER BY pct_third_place DESC;
```

## Findings (n = 277)

See `reports/findings.txt` and `reports/figures/`. In brief:

- About 84% of respondents call their gym a third place.
- Those who do score much higher on the social items (about 4.1 vs 3.0 out of 5), but those items overlap with the third-place idea, so this is partly circular.
- Age, years climbing, and travel time showed no statistically significant relationship with the third-place answer. Several groups are small, so this is weak evidence of no effect.
- More time at the gym goes with a higher social score (Spearman rho about 0.33 for weekly hours).
- People who say they "primarily visit to exercise and leave afterward" are the least likely to call the gym a third place (about 62% vs 87-95% for the other statements).

## Limitations

- Convenience sample: people who chose to answer a climbing survey are probably more engaged with the community than the average climber.
- Cross-sectional and self-reported, so none of the above shows causation.
- Small subgroups (60+, over an hour of travel) leave the tests with little power.
- Several tests were run without multiple-comparison correction; treat borderline results cautiously.

