import re
import numpy as np
import pandas as pd


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

QUESTION_PATTERNS = {
    "definition": [
        r"\bdefine\b",
        r"\bwhat is\b",
        r"\bwhat are\b",
        r"\bmeaning of\b",
        r"\bdefine and explain\b",
    ],

    "explain": [
        r"\bexplain\b",
        r"\bdescribe\b",
        r"\bdiscuss\b",
        r"\belaborate\b",
    ],

    "compare": [
        r"\bcompare\b",
        r"\bdifferentiate\b",
        r"\bdifference between\b",
        r"\bdistinguish\b",
    ],

    "calculate": [
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bfind\b",
        r"\bsolve\b",
        r"\bderive\b",
    ],

    "apply": [
        r"\bapply\b",
        r"\bimplement\b",
        r"\busing\b",
        r"\bdesign\b",
        r"\bdevelop\b",
    ],

    "analyze": [
        r"\banalyze\b",
        r"\banalyse\b",
        r"\bexamine\b",
        r"\bevaluate\b",
        r"\bjustify\b",
    ],

}


def detect_question_type(question):

    q = question.lower()

    scores = {}

    for qtype, patterns in QUESTION_PATTERNS.items():

        score = 0

        for pattern in patterns:

            if re.search(pattern, q):
                score += 1

        scores[qtype] = score

    best_type = max(
        scores,
        key=scores.get
    )

    if scores[best_type] == 0:
        return "general"

    return best_type


# ============================================================
# BLOOM'S TAXONOMY
# ============================================================

BLOOM_PATTERNS = {

    "Remember": [
        r"\bdefine\b",
        r"\blist\b",
        r"\bidentify\b",
        r"\bstate\b",
        r"\bname\b",
    ],

    "Understand": [
        r"\bexplain\b",
        r"\bdescribe\b",
        r"\bsummarize\b",
        r"\bdiscuss\b",
    ],

    "Apply": [
        r"\bapply\b",
        r"\bimplement\b",
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bsolve\b",
        r"\buse\b",
    ],

    "Analyze": [
        r"\banalyze\b",
        r"\banalyse\b",
        r"\bcompare\b",
        r"\bdifferentiate\b",
        r"\bdistinguish\b",
        r"\bexamine\b",
    ],

    "Evaluate": [
        r"\bevaluate\b",
        r"\bjustify\b",
        r"\bcritique\b",
        r"\bassess\b",
    ],

    "Create": [
        r"\bdesign\b",
        r"\bdevelop\b",
        r"\bconstruct\b",
        r"\bpropose\b",
        r"\bcreate\b",
    ],
}


BLOOM_ORDER = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
]


def detect_bloom(question):

    q = question.lower()

    scores = {}

    for level, patterns in BLOOM_PATTERNS.items():

        score = 0

        for pattern in patterns:

            if re.search(pattern, q):
                score += 1

        scores[level] = score

    best = max(
        scores,
        key=scores.get
    )

    if scores[best] == 0:
        return "Understand"

    return best


# ============================================================
# MARK EXTRACTION
# ============================================================

def extract_marks(question):
    """Fallback mark extraction for papers whose part metadata is missing.

    Only the exam's valid per-question marks are accepted. This prevents
    totals such as 80 from being mistaken for a question's marks.
    """

    valid_marks = {2, 13, 15}

    patterns = [
        r"\((\d+)\s*marks?\)",
        r"\[(\d+)\s*marks?\]",
        r"(\d+)\s*marks?",
        r"(\d+)\s*M\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, str(question or ""), re.IGNORECASE)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if value in valid_marks:
            return value

    return None


# ============================================================
# ENRICH QUESTIONS
# ============================================================

def enrich_questions(df):
    """
    Add question-type and Bloom metadata.

    IMPORTANT:
    Preserve marks already extracted from Part A/B/C.
    Only fall back to text-based mark extraction when a
    marks value is missing.
    """

    df = df.copy()

    df["question_type"] = (
        df["question"]
        .fillna("")
        .apply(detect_question_type)
    )

    df["bloom_level"] = (
        df["question"]
        .fillna("")
        .apply(detect_bloom)
    )

    extracted_marks = (
        df["question"]
        .fillna("")
        .apply(extract_marks)
    )

    if "marks" not in df.columns:
        df["marks"] = extracted_marks
    else:
        # Never replace a valid Part-derived mark with text-derived noise.
        df["marks"] = df["marks"].where(
            df["marks"].isin([2, 13, 15]),
            np.nan
        )
        df["marks"] = df["marks"].fillna(extracted_marks)

    # Part is authoritative for this exam structure.
    if "part" in df.columns:
        part_mark_map = {"A": 2, "B": 13, "C": 15}
        known_part = df["part"].astype(str).str.upper()
        mask = known_part.isin(part_mark_map)
        df.loc[mask, "marks"] = known_part[mask].map(part_mark_map)

    # Final safety check: only valid per-question marks survive.
    df.loc[~df["marks"].isin([2, 13, 15]), "marks"] = np.nan

    return df


# ============================================================
# TOPIC EVOLUTION
# ============================================================

def topic_evolution(df, topic):

    topic_df = df[
        (df["topic"] == topic)
    ].copy()

    if topic_df.empty:
        return {
            "topic": topic,
            "years": [],
            "summary": None
        }

    years = sorted(
        topic_df["year"].unique()
    )

    evolution = []

    for year in years:

        year_df = topic_df[
            topic_df["year"] == year
        ]

        question_types = (
            year_df["question_type"]
            .value_counts()
            .to_dict()
        )

        bloom = (
            year_df["bloom_level"]
            .value_counts()
            .to_dict()
        )

        marks = (
            pd.to_numeric(
                year_df["marks"],
                errors="coerce"
            )
            .dropna()
        )

        evolution.append({

            "year": int(year),

            "question_count":
                int(len(year_df)),

            "average_similarity":
                round(
                    float(
                        year_df["similarity"]
                        .mean()
                    ),
                    3
                ),

            "question_types":
                question_types,

            "bloom_distribution":
                bloom,

            "average_marks":
                round(
                    float(marks.mean()),
                    2
                )
                if len(marks)
                else None,

            "questions":
                year_df[
                    [
                        "question",
                        "question_type",
                        "bloom_level",
                        "marks",
                        "similarity"
                    ]
                ]
                .fillna("")
                .to_dict("records")
        })

    return {
        "topic": topic,
        "years": evolution
    }


# ============================================================
# EMERGING TOPIC DETECTION
# ============================================================

def emerging_topics(df, top_k=10):

    assigned = df[
        df["topic"] != "Unassigned"
    ].copy()

    if assigned.empty:
        return []

    years = sorted(
        assigned["year"].unique()
    )

    if len(years) < 2:
        return []

    latest_year = years[-1]

    # Use up to the last 3 years
    recent_years = years[-3:]

    results = []

    for topic in sorted(
        assigned["topic"].unique()
    ):

        topic_df = assigned[
            assigned["topic"] == topic
        ]

        yearly_counts = []

        for year in years:

            yearly_counts.append(
                len(
                    topic_df[
                        topic_df["year"] == year
                    ]
                )
            )

        values = np.asarray(
            yearly_counts,
            dtype=float
        )

        total = float(values.sum())

        recent_mask = np.isin(
            years,
            recent_years
        )

        recent_count = float(
            values[recent_mask].sum()
        )

        previous_mask = np.isin(
            years,
            years[:-len(recent_years)]
            if len(years) > len(recent_years)
            else []
        )

        previous_count = float(
            values[previous_mask].sum()
        )

        # Normalize by number of years
        recent_avg = (
            recent_count / len(recent_years)
        )

        previous_year_count = (
            len(years) - len(recent_years)
        )

        previous_avg = (
            previous_count /
            previous_year_count
            if previous_year_count > 0
            else 0
        )

        if len(values) >= 2:

            trend = float(
                np.polyfit(
                    np.arange(len(values)),
                    values,
                    1
                )[0]
            )

        else:

            trend = 0.0

        # Consecutive recent appearances
        consecutive = 0

        for value in reversed(values):

            if value > 0:
                consecutive += 1
            else:
                break

        # Recent semantic similarity
        recent_df = topic_df[
            topic_df["year"].isin(
                recent_years
            )
        ]

        recent_similarity = (
            float(
                recent_df["similarity"].mean()
            )
            if not recent_df.empty
            else 0.0
        )

        # Growth ratio
        if previous_avg > 0:

            growth = (
                recent_avg /
                previous_avg
            )

        elif recent_avg > 0:

            growth = 2.0

        else:

            growth = 0.0

        # Emerging score
        score = (
            0.35 * min(
                max(growth - 1, 0),
                1
            )
            +
            0.30 * min(
                max(trend, 0) /
                max(
                    np.max(values),
                    1
                ),
                1
            )
            +
            0.20 * min(
                consecutive / 3,
                1
            )
            +
            0.15 * recent_similarity
        )

        results.append({

            "topic": topic,

            "emerging_score":
                round(
                    float(score),
                    4
                ),

            "recent_frequency":
                int(recent_count),

            "previous_average":
                round(
                    float(previous_avg),
                    2
                ),

            "growth_ratio":
                round(
                    float(growth),
                    3
                ),

            "trend":
                round(
                    float(trend),
                    4
                ),

            "consecutive_recent_years":
                int(consecutive),

            "recent_similarity":
                round(
                    float(recent_similarity),
                    3
                ),

            "yearly_counts": {
                str(y): int(v)
                for y, v
                in zip(years, values)
            }
        })

    results.sort(
        key=lambda x:
            x["emerging_score"],
        reverse=True
    )

    for rank, item in enumerate(
        results[:top_k],
        start=1
    ):
        item["rank"] = rank

    return results[:top_k]


# ============================================================
# FUTURE QUESTION BLUEPRINT
# ============================================================

def question_blueprint(df, topic):

    topic_df = df[
        df["topic"] == topic
    ].copy()

    if topic_df.empty:
        return {
            "topic": topic,
            "status": "No historical evidence",
            "common_part": None,
            "recent_part": None,
            "common_marks": None,
            "average_marks": None,
            "part_distribution": {},
            "marks_distribution": {}
        }

    # --------------------------------------------------------
    # Part distribution
    # --------------------------------------------------------

    part_counts = (
        topic_df["part"]
        .dropna()
        .astype(str)
        .str.upper()
        .value_counts()
    )

    common_part = (
        part_counts.index[0]
        if len(part_counts)
        else None
    )

    # --------------------------------------------------------
    # Recent topic behaviour
    # --------------------------------------------------------

    latest_year = int(
        topic_df["year"].max()
    )

    recent_topic_df = topic_df[
        topic_df["year"] >=
        latest_year - 2
    ]

    if recent_topic_df.empty:
        recent_topic_df = topic_df

    recent_parts = (
        recent_topic_df["part"]
        .dropna()
        .astype(str)
        .str.upper()
        .value_counts()
    )

    recent_part = (
        recent_parts.index[0]
        if len(recent_parts)
        else common_part
    )

    # --------------------------------------------------------
    # Marks
    # --------------------------------------------------------

    marks = pd.to_numeric(
        topic_df["marks"],
        errors="coerce"
    ).dropna()

    if len(marks):

        average_marks = round(
            float(marks.mean()),
            2
        )

        common_marks = int(
            marks.mode().iloc[0]
        )

        marks_distribution = {
            str(int(k)): int(v)
            for k, v in marks.value_counts().items()
        }

    else:

        average_marks = None
        common_marks = None
        marks_distribution = {}

    # --------------------------------------------------------
    # Question type
    # --------------------------------------------------------

    type_counts = (
        topic_df["question_type"]
        .value_counts()
    )

    dominant_type = (
        type_counts.index[0]
        if len(type_counts)
        else "general"
    )

    type_distribution = {
        str(k): int(v)
        for k, v in type_counts.items()
    }

    # --------------------------------------------------------
    # Bloom
    # --------------------------------------------------------

    bloom_counts = (
        topic_df["bloom_level"]
        .value_counts()
    )

    dominant_bloom = (
        bloom_counts.index[0]
        if len(bloom_counts)
        else "Understand"
    )

    bloom_distribution = {
        str(k): int(v)
        for k, v in bloom_counts.items()
    }

    # --------------------------------------------------------
    # Recent question pattern
    # --------------------------------------------------------

    recent_type = (
        recent_topic_df["question_type"]
        .value_counts()
    )

    recent_bloom = (
        recent_topic_df["bloom_level"]
        .value_counts()
    )

    recent_question_type = (
        recent_type.index[0]
        if len(recent_type)
        else dominant_type
    )

    recent_bloom_level = (
        recent_bloom.index[0]
        if len(recent_bloom)
        else dominant_bloom
    )

    # --------------------------------------------------------
    # Difficulty signal
    # --------------------------------------------------------

    difficulty_map = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    bloom_scores = (
        topic_df["bloom_level"]
        .map(difficulty_map)
        .dropna()
    )

    avg_bloom_score = (
        float(bloom_scores.mean())
        if len(bloom_scores)
        else 2.0
    )

    if avg_bloom_score >= 4.5:
        difficulty = "High"
    elif avg_bloom_score >= 3.0:
        difficulty = "Medium-High"
    elif avg_bloom_score >= 2.0:
        difficulty = "Medium"
    else:
        difficulty = "Low"

    # --------------------------------------------------------
    # Historical evidence
    # --------------------------------------------------------

    evidence = []

    for _, row in (
        topic_df
        .sort_values("year")
        .tail(5)
        .iterrows()
    ):

        evidence.append({

            "year": int(row["year"]),

            "part":
                str(row["part"])
                if pd.notna(row["part"])
                else None,

            "question":
                str(row["question"]),

            "question_type":
                str(row["question_type"]),

            "bloom_level":
                str(row["bloom_level"]),

            "marks":
                (
                    int(row["marks"])
                    if pd.notna(row["marks"])
                    else None
                )
        })

    return {

        "topic": topic,

        "status": "Available",

        "historical_question_count":
            int(len(topic_df)),

        "latest_year":
            latest_year,

        "common_part":
            common_part,

        "recent_part":
            recent_part,

        "part_distribution": {
            str(k): int(v)
            for k, v in part_counts.items()
        },

        "dominant_question_type":
            dominant_type,

        "recent_question_type":
            recent_question_type,

        "question_type_distribution":
            type_distribution,

        "dominant_bloom_level":
            dominant_bloom,

        "recent_bloom_level":
            recent_bloom_level,

        "bloom_distribution":
            bloom_distribution,

        "average_marks":
            average_marks,

        "common_marks":
            common_marks,

        "marks_distribution":
            marks_distribution,

        "estimated_difficulty":
            difficulty,

        "historical_evidence":
            evidence
    }


# ============================================================
# FULL PATTERN ANALYSIS
# ============================================================

def pattern_analysis(df):

    df = enrich_questions(df)

    topics = sorted(
        df[
            df["topic"] != "Unassigned"
        ]["topic"].unique()
    )

    evolution = {}

    blueprints = {}

    for topic in topics:

        evolution[topic] = (
            topic_evolution(
                df,
                topic
            )
        )

        blueprints[topic] = (
            question_blueprint(
                df,
                topic
            )
        )

    return {

        "question_type_distribution":
            {
                str(k): int(v)
                for k, v
                in df["question_type"]
                .value_counts()
                .items()
            },

        "bloom_distribution":
            {
                str(k): int(v)
                for k, v
                in df["bloom_level"]
                .value_counts()
                .items()
            },

        "emerging_topics":
            emerging_topics(df),

        "topic_evolution":
            evolution,

        "question_blueprints":
            blueprints,

        "enriched_questions":
            df,
        "part_analysis":
            part_analysis(df)
    }

def part_analysis(df):

    if df.empty:
        return []

    grouped = (
        df.groupby(
            ["part", "marks"]
        )
        .size()
        .reset_index(
            name="question_count"
        )
    )

    result = []

    for _, row in grouped.iterrows():

        result.append({

            "part":
                str(row["part"]),

            "marks":
                (
                    int(row["marks"])
                    if pd.notna(
                        row["marks"]
                    )
                    else None
                ),

            "question_count":
                int(
                    row["question_count"]
                ),

            "total_marks":
                (
                    int(
                        row["question_count"] *
                        row["marks"]
                    )
                    if pd.notna(
                        row["marks"]
                    )
                    else None
                )
        })

    return result