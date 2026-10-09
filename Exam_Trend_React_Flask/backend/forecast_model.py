import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


FEATURE_COLUMNS = [
    "total_frequency",
    "recent_frequency",
    "last_year_frequency",
    "active_years",
    "recurrence_rate",
    "recency_gap",
    "trend_slope",
    "mean_similarity",
    "recent_mean_similarity",
    "similarity_trend",
]


class SemanticTemporalForecaster:
    """
    Learned semantic-temporal forecasting model.

    For each topic at each historical cutoff year:
        X = semantic + temporal features
        y = whether the topic appears in the following year

    The model learns P(topic appears in next year).
    """

    def __init__(self, random_state=42):

        self.random_state = random_state

        self.model = Pipeline([
            (
                "scaler",
                StandardScaler()
            ),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=6,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    random_state=random_state,
                    n_jobs=-1
                )
            )
        ])

        self.is_fitted = False
        self.feature_importances_ = None

    # ---------------------------------------------------------
    # Feature extraction
    # ---------------------------------------------------------

    @staticmethod
    def temporal_features(values):

        values = np.asarray(values, dtype=float)

        total = values.sum()

        recent_window = min(3, len(values))
        recent_frequency = values[-recent_window:].sum()

        last_year_frequency = (
            values[-1]
            if len(values) > 0
            else 0
        )

        active_years = int(
            np.sum(values > 0)
        )

        recurrence_rate = (
            active_years / len(values)
            if len(values)
            else 0
        )

        if active_years > 0:

            active_indices = np.where(values > 0)[0]

            last_active = active_indices[-1]

            recency_gap = (
                len(values) - 1 - last_active
            )

        else:

            recency_gap = len(values)

        if len(values) >= 2:

            trend_slope = float(
                np.polyfit(
                    np.arange(len(values)),
                    values,
                    1
                )[0]
            )

        else:

            trend_slope = 0.0

        return {
    "total_frequency": float(total),
    "recent_frequency": float(recent_frequency),
    "last_year_frequency": float(last_year_frequency),
    "active_years": int(active_years),
    "recurrence_rate": float(recurrence_rate),
    "recency_gap": int(recency_gap),
    "trend_slope": float(trend_slope),
}

    # ---------------------------------------------------------
    # Semantic feature extraction
    # ---------------------------------------------------------

    @staticmethod
    def semantic_features(similarities):

        similarities = np.asarray(
            similarities,
            dtype=float
        )

        if len(similarities) == 0:

            return {
                "mean_similarity": 0.0,
                "recent_mean_similarity": 0.0,
                "similarity_trend": 0.0
            }

        mean_similarity = float(
            np.mean(similarities)
        )

        recent_window = min(
            3,
            len(similarities)
        )

        recent_mean_similarity = float(
            np.mean(
                similarities[-recent_window:]
            )
        )

        if len(similarities) >= 2:

            similarity_trend = float(
                np.polyfit(
                    np.arange(len(similarities)),
                    similarities,
                    1
                )[0]
            )

        else:

            similarity_trend = 0.0

        return {
    "mean_similarity": float(mean_similarity),
    "recent_mean_similarity":
        float(recent_mean_similarity),
    "similarity_trend":
        float(similarity_trend)
}

    # ---------------------------------------------------------
    # Build one topic's feature vector
    # ---------------------------------------------------------

    def build_topic_features(
        self,
        topic_df,
        years
    ):

        frequency_values = []

        similarity_values = []

        for year in years:

            year_data = topic_df[
                topic_df["year"] == year
            ]

            frequency_values.append(
                len(year_data)
            )

            if len(year_data) > 0:

                similarity_values.append(
                    year_data["similarity"].mean()
                )

            else:

                similarity_values.append(0.0)

        temporal = self.temporal_features(
            frequency_values
        )

        semantic = self.semantic_features(
            similarity_values
        )

        return {
            **temporal,
            **semantic
        }

    # ---------------------------------------------------------
    # Build training dataset
    # ---------------------------------------------------------

    def build_training_data(self, df):

        assigned = df[
            df["topic"] != "Unassigned"
        ].copy()

        years = sorted(
            assigned["year"].unique()
        )

        X_rows = []
        y_rows = []

        metadata = []

        # Need at least two years:
        # one or more years for history
        # + one year for the target
        for i in range(1, len(years)):

            cutoff_years = years[:i]

            target_year = years[i]

            topics = sorted(
                assigned["topic"].unique()
            )

            for topic in topics:

                topic_df = assigned[
                    assigned["topic"] == topic
                ]

                historical_df = topic_df[
                    topic_df["year"].isin(
                        cutoff_years
                    )
                ]

                features = self.build_topic_features(
                    historical_df,
                    cutoff_years
                )

                # Did the topic appear
                # in the next year?
                future_count = len(
                    topic_df[
                        topic_df["year"] == target_year
                    ]
                )

                label = int(
                    future_count > 0
                )

                X_rows.append(features)
                y_rows.append(label)

                metadata.append({
                    "topic": topic,
                    "cutoff_year": cutoff_years[-1],
                    "target_year": target_year
                })

        X = pd.DataFrame(
            X_rows,
            columns=FEATURE_COLUMNS
        )

        y = np.asarray(y_rows)

        metadata = pd.DataFrame(metadata)

        return X, y, metadata

    # ---------------------------------------------------------
    # Train
    # ---------------------------------------------------------

    def fit(self, df):

        X, y, metadata = (
            self.build_training_data(df)
        )

        if len(X) == 0:

            raise ValueError(
                "Not enough historical years "
                "to train the forecasting model."
            )

        if len(np.unique(y)) < 2:

            raise ValueError(
                "Training data contains only "
                "one target class. More historical "
                "years or topic variation are required."
            )

        self.model.fit(X, y)

        rf = (
            self.model
            .named_steps["classifier"]
        )

        self.feature_importances_ = dict(
            zip(
                FEATURE_COLUMNS,
                rf.feature_importances_
            )
        )

        self.is_fitted = True

        return {
            "samples": len(X),
            "positive_examples": int(y.sum()),
            "negative_examples": int(
                len(y) - y.sum()
            ),
            "feature_importance":
                self.feature_importances_
        }

    # ---------------------------------------------------------
    # Predict future topic probabilities
    # ---------------------------------------------------------

    def predict_topics(
        self,
        df,
        cutoff_year=None,
        top_k=5
    ):

        assigned = df[
            df["topic"] != "Unassigned"
        ].copy()

        if cutoff_year is None:

            cutoff_year = int(
                assigned["year"].max()
            )

        years = sorted(
            assigned[
                assigned["year"] <= cutoff_year
            ]["year"].unique()
        )

        if len(years) == 0:

            return []

        predictions = []

        for topic in sorted(
            assigned["topic"].unique()
        ):

            topic_df = assigned[
                (assigned["topic"] == topic) &
                (assigned["year"] <= cutoff_year)
            ]

            features = (
                self.build_topic_features(
                    topic_df,
                    years
                )
            )

            X = pd.DataFrame(
                [features],
                columns=FEATURE_COLUMNS
            )

            probability = float(
                self.model.predict_proba(X)[0][1]
            )

            predictions.append({
                "topic": topic,
                "forecast_probability":
                    round(probability, 4),
                "features": features
            })

        predictions.sort(
            key=lambda x:
                x["forecast_probability"],
            reverse=True
        )

        for rank, item in enumerate(
            predictions[:top_k],
            start=1
        ):

            item["rank"] = rank

        return predictions[:top_k]