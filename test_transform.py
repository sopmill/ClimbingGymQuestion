import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from climbing.transform import build_traits_table, collapse_grid, transform
from climbing.validate import validate


def make_raw():
    return pd.DataFrame({
        "Timestamp": ["10/13/2026 15:00:25", "10/13/2026 16:00:00"],
        "Approximately how long does it take you to travel one way to the gym?": ["15-30 minutes", "Less than 15 minutes"],
        "What is your age group? [20s]": ["Age", None],
        "What is your age group? [30s]": [None, "Age"],
        "How long have you been climbing? [1-3 years]": ["Years", None],
        "How long have you been climbing? [3-5 years]": [None, "Years"],
        "How often do you go to the climbing gym per week?": [3.0, 2.0],
        "How many hours per visit are you at the climbing gym?": [2.0, 1.0],
        "How much do you agree with the following statements? [I have formed meaningful friendships through climbing.]": ["Strongly Agree", "Disagree"],
        "How much do you agree with the following statements? [I feel a sense of belonging at my climbing gym. ]": ["Agree", "Neutral"],
        "Which of the following describes your experience at a climbing gym?": [
            "I regularly see familiar faces., I have met new friends there.",
            "I primarily visit to exercise and leave afterward."],
        "Overall, would you consider your local climbing gym your third place?": ["Yes", "No"],
        "Why and how did you get into climbing? Or any other climbing gym related stories. ": ["a story", "  "],
    })


def test_collapse_grid_picks_ticked_option():
    df = make_raw()
    out = collapse_grid(df, "What is your age group?", "age_group", ["20s", "30s"])
    assert out["age_group"].tolist() == ["20s", "30s"]
    assert not any(c.startswith("What is your age group?") for c in out.columns)


def test_collapse_grid_blank_row_is_nan():
    df = make_raw()
    df.loc[1, "What is your age group? [30s]"] = None
    out = collapse_grid(df, "What is your age group?", "age_group", ["20s", "30s"])
    assert pd.isna(out.loc[1, "age_group"])


def test_transform_maps_likert_and_booleans():
    out = transform(make_raw())
    assert out["likert_friendships"].tolist() == [5, 2]
    assert out["is_third_place"].tolist() == [True, False]
    assert out["social_score"].tolist() == [4.5, 2.5]


def test_blank_story_becomes_missing():
    out = transform(make_raw())
    assert out.loc[0, "story"] == "a story"
    assert pd.isna(out.loc[1, "story"])


def test_traits_split_one_row_per_trait():
    traits = build_traits_table(transform(make_raw()))
    assert len(traits) == 3
    assert set(traits["trait"]) == {
        "I regularly see familiar faces",
        "I have met new friends there",
        "I primarily visit to exercise and leave afterward",
    }


def test_validate_catches_out_of_range_values():
    clean = transform(make_raw())
    traits = build_traits_table(clean)
    validate(clean, traits, expected_rows=2)
    clean.loc[0, "visits_per_week"] = 12
    with pytest.raises(AssertionError):
        validate(clean, traits)
