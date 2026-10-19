"""Analysis: what goes with a climber calling their gym a 'third place'?

Reads the cleaned SQLite database, runs a few tests, saves charts to
reports/figures/ and a plain-text summary to reports/findings.txt.
"""
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from climbing.config import FIGURES_DIR, PROCESSED_DIR, ROOT, TRAVEL_ORDER

FIGURES_DIR.mkdir(parents=True, exist_ok=True)
lines = []


def say(text=""):
    print(text)
    lines.append(text)


def wilson(k, n, z=1.96):
    """95% Wilson confidence interval for a proportion."""
    p = k / n
    d = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return centre - half, centre + half


def cramers_v(table):
    chi2 = stats.chi2_contingency(table)[0]
    n = table.to_numpy().sum()
    return np.sqrt(chi2 / (n * (min(table.shape) - 1)))


with sqlite3.connect(PROCESSED_DIR / "survey.db") as con:
    df = pd.read_sql("SELECT * FROM respondents", con)
    traits = pd.read_sql("SELECT * FROM respondent_traits", con)

df["is_third_place"] = df["is_third_place"].astype(bool)
y = df["is_third_place"]
df["gym_hours_per_week"] = df["visits_per_week"] * df["hours_per_visit"]
# 60s / Over 60 have 3 people total, too few for a chi-square test
df["age_band"] = df["age_group"].replace({"60s": "50+", "Over 60": "50+", "50s": "50+"})

# ---- 1. Headline ----------------------------------------------------------
k, n = int(y.sum()), len(df)
lo, hi = wilson(k, n)
say(f"1. {k}/{n} respondents ({k/n:.1%}, 95% CI {lo:.1%}-{hi:.1%}) call their gym a third place.")

# ---- 2. Social score by group --------------------------------------------
a, b = df.loc[y, "social_score"].dropna(), df.loc[~y, "social_score"].dropna()
u = stats.mannwhitneyu(a, b)
rbc = 1 - 2 * u.statistic / (len(a) * len(b))   # rank-biserial effect size (sign: yes > no)
say(f"\n2. Social score (mean of the 6 agreement items, 1-5): "
    f"third place = {a.mean():.2f}, not = {b.mean():.2f}; "
    f"Mann-Whitney p = {u.pvalue:.1e}, rank-biserial r = {abs(rbc):.2f}.")
say("   Caution: the agreement items overlap with the idea of a third place, "
    "so this partly measures the same thing twice.")

# ---- 3. Demographics / access vs third place ------------------------------
say("\n3. Chi-square tests of third-place answer vs. each background variable:")
for col in ["age_band", "climbing_experience", "travel_time"]:
    sub = df.dropna(subset=[col])
    table = pd.crosstab(sub[col], sub["is_third_place"])
    chi2, p, _, expected = stats.chi2_contingency(table)
    small = (expected < 5).mean()
    say(f"   {col:20s} p = {p:.3f}, Cramer's V = {cramers_v(table):.2f}"
        f"  ({small:.0%} of cells have expected count < 5)")

# ---- 4. Time spent --------------------------------------------------------
say("\n4. Time at the gym vs. social score (Spearman):")
for col in ["visits_per_week", "hours_per_visit", "gym_hours_per_week"]:
    sub = df[[col, "social_score"]].dropna()
    rho, p = stats.spearmanr(sub[col], sub["social_score"])
    say(f"   {col:20s} rho = {rho:.2f}, p = {p:.1e}")
h = df.dropna(subset=["gym_hours_per_week"])
u = stats.mannwhitneyu(h.loc[h.is_third_place, "gym_hours_per_week"],
                       h.loc[~h.is_third_place, "gym_hours_per_week"])
say(f"   Weekly gym hours, third place vs not: median "
    f"{h.loc[h.is_third_place, 'gym_hours_per_week'].median():.1f} vs "
    f"{h.loc[~h.is_third_place, 'gym_hours_per_week'].median():.1f} (p = {u.pvalue:.1e})")

# ---- 5. Experience traits -------------------------------------------------
m = traits.merge(df[["respondent_id", "is_third_place"]], on="respondent_id")
rows = []
for trait, g in m.groupby("trait"):
    k_, n_ = int(g.is_third_place.sum()), len(g)
    lo_, hi_ = wilson(k_, n_)
    rows.append((trait, n_, k_ / n_, lo_, hi_))
tr = pd.DataFrame(rows, columns=["trait", "n", "pct", "lo", "hi"]).sort_values("pct")
say("\n5. Share calling the gym a third place, among people who ticked each statement:")
for r in tr.sort_values("pct", ascending=False).itertuples():
    say(f"   {r.pct:5.1%} (n={r.n:3d})  {r.trait}")

# ---- Charts ---------------------------------------------------------------
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10})
YES, NO = "#2a7f62", "#c0603a"

# Fig 1: agreement items, third place vs not
likert = [c for c in df.columns if c.startswith("likert_")]
means = df.groupby("is_third_place")[likert].mean().T
labels = [c.replace("likert_", "").replace("_", " ") for c in means.index]
fig, ax = plt.subplots(figsize=(7, 4))
yy = np.arange(len(means))
ax.barh(yy + 0.2, means[True], 0.4, color=YES, label="Third place: yes")
ax.barh(yy - 0.2, means[False], 0.4, color=NO, label="Third place: no")
ax.set_yticks(yy, labels)
ax.set_xlim(1, 5)
ax.set_xlabel("Mean agreement (1 = strongly disagree, 5 = strongly agree)")
ax.legend(frameon=False, loc="lower right")
ax.set_title("Agreement with social statements")
fig.tight_layout()
fig.savefig(FIGURES_DIR / "agreement_by_third_place.png", dpi=160)
plt.close(fig)

# Fig 2: trait -> % third place with CI
fig, ax = plt.subplots(figsize=(8, 4.2))
yy = np.arange(len(tr))
ax.barh(yy, tr.pct * 100, color=YES)
ax.errorbar(tr.pct * 100, yy, xerr=[(tr.pct - tr.lo) * 100, (tr.hi - tr.pct) * 100],
            fmt="none", ecolor="black", capsize=3, lw=1)
ax.set_yticks(yy, [t if len(t) < 48 else t[:45] + "..." for t in tr.trait])
ax.set_xlim(0, 100)
ax.set_xlabel("% who call their gym a third place (95% CI)")
ax.set_title("Third-place rate by experience statement")
fig.tight_layout()
fig.savefig(FIGURES_DIR / "traits_vs_third_place.png", dpi=160)
plt.close(fig)

# Fig 3: weekly hours vs social score
fig, ax = plt.subplots(figsize=(6, 4))
d = df.dropna(subset=["gym_hours_per_week", "social_score"])
jx = d.gym_hours_per_week + np.random.default_rng(0).normal(0, 0.12, len(d))
jy = d.social_score + np.random.default_rng(1).normal(0, 0.05, len(d))
ax.scatter(jx, jy, c=np.where(d.is_third_place, YES, NO), alpha=0.5, s=18)
ax.set_xlabel("Hours at gym per week (visits x hours per visit)")
ax.set_ylabel("Social score (1-5)")
ax.set_title("Time at the gym vs. social score")
fig.tight_layout()
fig.savefig(FIGURES_DIR / "hours_vs_social_score.png", dpi=160)
plt.close(fig)

# Fig 4: third-place rate by travel time
t = df.dropna(subset=["travel_time"]).groupby("travel_time")["is_third_place"].agg(["sum", "count"])
t = t.reindex(TRAVEL_ORDER)
fig, ax = plt.subplots(figsize=(7, 3.8))
pct = t["sum"] / t["count"] * 100
ax.bar(range(len(t)), pct, color=YES)
for i, (p_, c_) in enumerate(zip(pct, t["count"])):
    ax.text(i, p_ + 1.5, f"n={c_}", ha="center", fontsize=9)
ax.set_xticks(range(len(t)), [s.replace(" minutes", " min") for s in t.index])
ax.set_ylim(0, 105)
ax.set_ylabel("% third place")
ax.set_title("Third-place rate by one-way travel time")
fig.tight_layout()
fig.savefig(FIGURES_DIR / "travel_time_vs_third_place.png", dpi=160)
plt.close(fig)

(ROOT / "reports" / "findings.txt").write_text("\n".join(lines) + "\n")
print("\nSaved 4 figures to reports/figures/ and summary to reports/findings.txt")
