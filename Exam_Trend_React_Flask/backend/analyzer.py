import os,re
import numpy as np
import pandas as pd
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from config import *
from syllabus import TOPIC_TO_UNIT
_model=None
from forecast_model import (
    SemanticTemporalForecaster
)
from pattern_analysis import pattern_analysis

def model():
 global _model
 if _model is None: _model=SentenceTransformer(EMBEDDING_MODEL)
 return _model

def configure_ocr():
 for p in [TESSERACT_PATH,r'C:\\Users\\T9973\\AppData\Local\\Tesseract-OCR\\tesseract.exe',r'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe']:
  if p and os.path.exists(p): pytesseract.pytesseract.tesseract_cmd=p; return p
 return 'PATH'

def extract_text(path):
 try:
  text='\n'.join(x.extract_text() or '' for x in PdfReader(path).pages)
 except Exception: text=''
 if len(re.sub(r'\s+','',text))>=100: return text
 configure_ocr(); kw={}
 if POPPLER_PATH and os.path.isdir(POPPLER_PATH): kw['poppler_path']=POPPLER_PATH
 return '\n'.join(pytesseract.image_to_string(p) for p in convert_from_path(path,**kw))

def year_of(name):
    """
    Extract examination year from the original filename.

    Prioritize the STUCOR-style AM/ND year pattern
    so UUIDs prepended by the application do not
    accidentally become the detected year.
    """

    # Examples:
    # AM2022
    # ND2021
    # ND2023
    match = re.search(
        r'(?:AM|ND)(20\d{2})',
        name,
        re.IGNORECASE
    )

    if match:
        return int(match.group(1))

    # Generic fallback for filenames such as:
    # Physics_2024.pdf
    years = re.findall(
        r'(?<!\d)(20\d{2})(?!\d)',
        name
    )

    if years:
        return int(years[-1])

    return None

# ============================================================
# EXAMINATION PART + QUESTION PARSER
# ============================================================

PART_MARKS = {
    "A": 2,
    "B": 13,
    "C": 15
}

# Accept common OCR variants: PART / PAPT / SECTION,
# PART-A, PART A, PART A:, PART A (2 MARKS), etc.
PART_PATTERN = re.compile(
    r"""
    \b(?:PART|PAPT|SECTION)
    \s*[-_:.\s]*
    ([ABC])
    \b
    (?P<details>[^\n]*)
    """,
    re.IGNORECASE | re.VERBOSE
)

# Top-level questions:
#   1.
#   1)
#   Q1.
#   11(a)
#   11 (a)
#   11-b
QUESTION_PATTERN = re.compile(
    r"""
    (?<!\d)
    (?:Q(?:UESTION)?\s*)?
    (\d{1,3})
    \s*
    (?:
        \(\s*([a-z])\s*\)
        |
        [.)\-:]
    )
    (?=\s|$)
    """,
    re.IGNORECASE | re.VERBOSE
)


def _normalise_question_text(text):
    """Clean OCR whitespace without destroying question structure."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_part_marks(details, part):
    """
    Prefer an explicit mark value in the part heading.
    Otherwise use the known examination structure.
    """
    match = re.search(
        r"(\d{1,3})\s*(?:marks?|m)\b",
        details or "",
        re.IGNORECASE
    )

    if match:
        return int(match.group(1))

    return PART_MARKS.get(part)


def _build_question_record(part, marks, qmatch, question):
    """Create one uniform record for both normal and OR questions."""
    q_number = int(qmatch.group(1))

    option = qmatch.group(2)

    if option:
        option = option.upper()

    question_id = (
        f"{q_number}({option.lower()})"
        if option
        else str(q_number)
    )

    return {
        "part": part,
        "question_number": q_number,
        "option": option,
        "question_id": question_id,
        "question_group": q_number,
        "is_alternative": option is not None,
        "marks": (
            int(marks)
            if marks is not None
            else None
        ),
        "question": question
    }


def _parse_question_section(
    section_text,
    part,
    marks
):
    """
    Parse one PART section.

    First tries line-start question markers, then falls
    back to an inline scan for OCR that collapsed line breaks.
    """

    # 1) Prefer question starts at the beginning of a line.
    line_pattern = re.compile(
        r"""
        (?im)
        ^[ \t]*
        (?:Q(?:UESTION)?\s*)?
        (\d{1,3})
        \s*
        (?:
            \(\s*([a-z])\s*\)
            |
            [.)\-:]
        )
        (?=\s|$)
        """,
        re.VERBOSE
    )

    matches = list(
        line_pattern.finditer(section_text)
    )

    # 2) OCR fallback: question markers may be embedded
    #    in a single long line.
    if len(matches) < 2:
        matches = list(
            QUESTION_PATTERN.finditer(
                section_text
            )
        )

    records = []

    for i, qmatch in enumerate(matches):

        start = qmatch.end()

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(section_text)
        )

        question = _normalise_question_text(
            section_text[start:end]
        )

        # Remove leading/trailing OR artifacts.
        question = re.sub(
            r"^(?:OR|EITHER)\s+",
            "",
            question,
            flags=re.IGNORECASE
        )

        question = re.sub(
            r"\s+(?:OR|EITHER)$",
            "",
            question,
            flags=re.IGNORECASE
        )

        # Ignore headers / OCR fragments.
        if len(question) < 15:
            continue

        records.append(
            _build_question_record(
                part,
                marks,
                qmatch,
                question
            )
        )

    return records


def segment(text):
    """
    Robust parser for the actual examination structure:

        PART A -> 2 marks
        PART B -> 13 marks
        PART C -> 15 marks

    11(a) and 11(b) are kept as TWO separate question
    records, linked by question_group=11 and marked
    is_alternative=True.
    """

    if not text or not text.strip():
        return []

    text = text.replace(
        "\r\n", "\n"
    ).replace(
        "\r", "\n"
    )

    # Keep newlines because headings and question starts
    # depend on document structure.
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # ---------------------------------------------------------
    # Detect Part A/B/C headings.
    # ---------------------------------------------------------

    part_matches = []

    for match in PART_PATTERN.finditer(text):

        part = match.group(1).upper()

        details = (
            match.group("details") or ""
        )

        marks = _extract_part_marks(
            details,
            part
        )

        part_matches.append({
            "part": part,
            "marks": marks,
            "start": match.start(),
            "end": match.end()
        })

    # Remove duplicate/overlapping part detections.
    unique_parts = []

    for item in part_matches:

        if (
            unique_parts
            and abs(
                item["start"] -
                unique_parts[-1]["start"]
            ) < 3
            and item["part"] ==
            unique_parts[-1]["part"]
        ):
            continue

        unique_parts.append(item)

    part_matches = unique_parts

    # ---------------------------------------------------------
    # If no part headings exist, fall back to a generic
    # question parser. These records intentionally have
    # unknown part/marks rather than inventing them.
    # ---------------------------------------------------------

    if not part_matches:
        return _segment_generic(text)

    records = []

    # ---------------------------------------------------------
    # Parse each detected part independently.
    # ---------------------------------------------------------

    for part_index, part_info in enumerate(
        part_matches
    ):

        section_start = part_info["end"]

        section_end = (
            part_matches[part_index + 1]["start"]
            if part_index + 1 < len(part_matches)
            else len(text)
        )

        section_text = text[
            section_start:section_end
        ]

        section_records = _parse_question_section(
            section_text,
            part_info["part"],
            part_info["marks"]
        )

        records.extend(
            section_records
        )

    return records


def _segment_generic(text):
    """
    Fallback when Part A/B/C headings cannot be detected.

    The record schema stays identical so analyze() never
    crashes because a fallback record lacks 'option'.
    """

    matches = list(
        QUESTION_PATTERN.finditer(text)
    )

    records = []

    for i, qmatch in enumerate(matches):

        start = qmatch.end()

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(text)
        )

        question = _normalise_question_text(
            text[start:end]
        )

        question = re.sub(
            r"^(?:OR|EITHER)\s+",
            "",
            question,
            flags=re.IGNORECASE
        )

        question = re.sub(
            r"\s+(?:OR|EITHER)$",
            "",
            question,
            flags=re.IGNORECASE
        )

        if len(question) < 15:
            continue

        records.append(
            _build_question_record(
                "Unknown",
                None,
                qmatch,
                question
            )
        )

    return records


def assign(questions):

    if not questions:
        return []

    topics = list(TOPIC_TO_UNIT)

    if not topics:
        return [
            (
                q,
                "Unassigned",
                0.0
            )
            for q in questions
        ]

    emq = model().encode(
        questions,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    emt = model().encode(
        topics,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    emq = np.asarray(emq)

    emt = np.asarray(emt)

    # Safety guard
    if emq.size == 0:
        return []

    sim = np.matmul(
        emq,
        emt.T
    )

    out = []

    for q, row in zip(
        questions,
        sim
    ):

        j = int(
            np.argmax(row)
        )

        score = float(
            row[j]
        )

        topic = (
            topics[j]
            if score >= SEMANTIC_THRESHOLD
            else "Unassigned"
        )

        out.append(
            (
                q,
                topic,
                score
            )
        )

    return out

def analyze(paths):

    rec = []
    errors = []

    for p in paths:

        filename = os.path.basename(p)

        y = year_of(filename)

        if y is None:
            errors.append({
                "file": filename,
                "error":
                    "Year missing from filename"
            })
            continue

        try:

            text = extract_text(p)

            questions = segment(text)

            print(
                f"\nFILE: {filename}"
            )

            print(
                f"DETECTED YEAR: {y}"
            )

            print(
                f"QUESTIONS EXTRACTED: "
                f"{len(questions)}"
            )

            # Useful parser diagnostics
            part_counts = {}

            for item in questions:

                part = item.get(
                    "part",
                    "Unknown"
                )

                part_counts[part] = (
                    part_counts.get(
                        part,
                        0
                    ) + 1
                )

            print(
                f"PART COUNTS: {part_counts}"
            )

            if not questions:

                errors.append({
                    "file": filename,
                    "error":
                        "No questions could be segmented"
                })

                continue

            question_texts = [
                item["question"]
                for item in questions
            ]

            assignments = assign(
                question_texts
            )

            assigned_count = 0
            unassigned_count = 0

            for meta, assignment in zip(
                questions,
                assignments
            ):

                # IMPORTANT:
                # qmatch is ONLY used inside segment().
                # analyze() works with the structured
                # metadata returned by segment().
                q, topic, similarity = assignment

                if topic == "Unassigned":
                    unassigned_count += 1
                else:
                    assigned_count += 1

                rec.append({

                    "file":
                        filename,

                    "year":
                        int(y),

                    "part":
                        meta.get(
                            "part",
                            "Unknown"
                        ),

                    "question_number":
                        int(
                            meta.get(
                                "question_number",
                                0
                            )
                        ),

                    "option":
                        meta.get(
                            "option"
                        ),

                    "question_id":
                        meta.get(
                            "question_id"
                        ),

                    "question_group":
                        int(
                            meta.get(
                                "question_group",
                                meta.get(
                                    "question_number",
                                    0
                                )
                            )
                        ),

                    "is_alternative":
                        bool(
                            meta.get(
                                "is_alternative",
                                False
                            )
                        ),

                    "marks":
                        (
                            int(meta["marks"])
                            if meta.get("marks")
                            is not None
                            else None
                        ),

                    "question":
                        q,

                    "topic":
                        topic,

                    "similarity":
                        float(
                            round(
                                similarity,
                                4
                            )
                        ),

                    "unit":
                        TOPIC_TO_UNIT.get(
                            topic,
                            "Unassigned"
                        )
                })

            print(
                f"ASSIGNED: "
                f"{assigned_count}"
            )

            print(
                f"UNASSIGNED: "
                f"{unassigned_count}"
            )

        except Exception as e:

            print(
                f"ERROR: {e}"
            )

            errors.append({
                "file": filename,
                "error":
                    str(e)
            })

    if not rec:

        raise ValueError(
            "No questions were extracted "
            "from the uploaded papers."
        )

    return (
        pd.DataFrame(rec),
        errors
    )


def matrix(df):
    assigned = df[df.topic != 'Unassigned']

    if assigned.empty:
        return pd.DataFrame()

    all_years = sorted(df['year'].unique())

    m = pd.crosstab(
        assigned['topic'],
        assigned['year']
    )

    m = m.reindex(columns=all_years, fill_value=0)

    return m.sort_index(axis=1)

def features(m):
 if m.empty:return pd.DataFrame()
 years=list(m.columns); rows=[]
 for topic,r in m.iterrows():
  v=np.array([r.get(y,0) for y in years],float); total=v.sum(); recent=v[-3:].sum(); active=int((v>0).sum()); last=max((y for y,x in zip(years,v) if x>0),default=None); gap=0 if last is None else max(years)-last; slope=float(np.polyfit(np.arange(len(v)),v,1)[0]) if len(v)>1 else 0
  rows.append({'topic':topic,'total_frequency':int(total),'recent_frequency':int(recent),'active_years':active,'recurrence_rate':active/len(years),'recency_gap':int(gap),'trend_slope':slope})
 return pd.DataFrame(rows)

def rank(m,k=TOP_K):
 f=features(m)
 if f.empty:return []
 def mm(s):
  a,b=s.min(),s.max(); return (s-a)/(b-a) if b!=a else s*0
 f['freq']=mm(f.total_frequency); f['recent']=mm(f.recent_frequency); f['trend']=mm(f.trend_slope.clip(lower=0)); f['recency']=1-mm(f.recency_gap); f['score']=(.25*f.recent+.25*f.recurrence_rate+.20*f.trend+.20*f.recency+.10*f.freq).clip(0,1)
 f=f.sort_values('score',ascending=False); out=[]
 for i,(_,r) in enumerate(f.head(k).iterrows(),1): out.append({'rank':i,'topic':r.topic,'unit':TOPIC_TO_UNIT[r.topic],'forecast_score':round(float(r.score),3),'evidence':{'total_frequency':int(r.total_frequency),'recent_frequency':int(r.recent_frequency),'active_years':int(r.active_years),'recurrence_rate':round(float(r.recurrence_rate),3),'recency_gap':int(r.recency_gap),'trend_slope':round(float(r.trend_slope),3)}})
 return out

def metrics(pred,actual,k=TOP_K):
 pred=list(pred)[:k]; actual=set(actual); hit=len(set(pred)&actual); p=hit/len(pred) if pred else 0; r=hit/len(actual) if actual else 0; f=2*p*r/(p+r) if p+r else 0; return {'precision_at_k':round(p,4),'recall_at_k':round(r,4),'f1_at_k':round(f,4)}

def learned_backtest(df, k=TOP_K):

    assigned = df[
        df["topic"] != "Unassigned"
    ].copy()

    years = sorted(
        assigned["year"].unique()
    )

    rows = []

    # Need at least:
    # historical years + future test year
    if len(years) < 3:

        return rows

    for i in range(2, len(years)):

        train_until = years[i - 1]
        test_year = years[i]

        train_df = assigned[
            assigned["year"] <= train_until
        ].copy()

        actual = set(
            assigned[
                assigned["year"] == test_year
            ]["topic"]
        )

        # -------------------------------------------------
        # Train model using ONLY historical information
        # -------------------------------------------------

        forecaster = (
            SemanticTemporalForecaster()
        )

        try:

            training_info = (
                forecaster.fit(train_df)
            )

        except ValueError as e:

            rows.append({
                "train_until": int(train_until),
                "test_year": int(test_year),
                "error": str(e)
            })

            continue

        # -------------------------------------------------
        # Predict test-year topic recurrence
        # -------------------------------------------------

        predictions = (
            forecaster.predict_topics(
                train_df,
                cutoff_year=train_until,
                top_k=k
            )
        )

        proposed = [
            x["topic"]
            for x in predictions
        ]

        # -------------------------------------------------
        # Frequency baseline
        # -------------------------------------------------

        frequency = (
            train_df
            .groupby("topic")
            .size()
            .sort_values(
                ascending=False
            )
            .head(k)
            .index
            .tolist()
        )

        # -------------------------------------------------
        # Recency baseline
        # -------------------------------------------------

        recent = (
            train_df[
                train_df["year"] == train_until
            ]
            .groupby("topic")
            .size()
            .sort_values(
                ascending=False
            )
            .head(k)
            .index
            .tolist()
        )

        rows.append({
            "train_until": int(train_until),
            "test_year": int(test_year),

            "proposed": metrics(
                proposed,
                actual,
                k
            ),

            "frequency_baseline": metrics(
                frequency,
                actual,
                k
            ),

            "recency_baseline": metrics(
                recent,
                actual,
                k
            ),

            "predictions": predictions,

            "feature_importance":
                training_info[
                    "feature_importance"
                ]
        })

    return rows

def aggregate(rows):
 out={}
 for key in ['proposed','frequency_baseline','recency_baseline']:
  vals=[r[key] for r in rows]; out[key]={z:round(float(np.mean([v[z] for v in vals])),4) if vals else 0 for z in ['precision_at_k','recall_at_k','f1_at_k']}
 return out

def result(df):
    m = matrix(df)

    f = features(m)

    old_forecast = rank(m)

    # Learned semantic-temporal forecast
    learned_forecast = []

    try:
        forecaster = SemanticTemporalForecaster()

        training_info = forecaster.fit(df)

        learned_forecast = forecaster.predict_topics(
            df,
            top_k=TOP_K
        )

    except ValueError as e:

        training_info = {
            "error": str(e)
        }

    bt = learned_backtest(df)

    patterns = pattern_analysis(df)


    patterns.pop(
        "enriched_questions",
        None
    )

    # ---------------------------------------------------------
    # Result
    # ---------------------------------------------------------

    result_data= {

        "summary": {

            "papers":
                int(df.file.nunique()),

            "questions":
                int(len(df)),

            "assigned_questions":
                int(
                    (df.topic != "Unassigned")
                    .sum()
                ),

            "unassigned_questions":
                int(
                    (df.topic == "Unassigned")
                    .sum()
                ),

            "years":
                sorted(
                    map(
                        int,
                        df.year.unique()
                    )
                ),

            "topics":
                int(
                    df[
                        df.topic != "Unassigned"
                    ]
                    .topic
                    .nunique()
                )
        },

        "topic_frequency": [

            {
                "topic": topic,
                "count": int(count)
            }

            for topic, count

            in df[
                df.topic != "Unassigned"
            ]
            .topic
            .value_counts()
            .head(30)
            .items()
        ],

        "unit_frequency": [

            {
                "unit": unit,
                "count": int(count)
            }

            for unit, count

            in df[
                df.unit != "Unassigned"
            ]
            .unit
            .value_counts()
            .items()
        ],

        "topic_year": {

            str(topic): {

                str(year):
                    int(value)

                for year, value
                in row.items()
            }

            for topic, row
            in m.iterrows()
        },

        "temporal_features":
            f.to_dict("records"),

        # Existing transparent forecast
        "forecast":
            rank(m),

        # Existing evaluation
        "backtest":
            bt,

        "backtest_summary":
            aggregate(bt),

        # =====================================================
        # NEW
        # =====================================================

        "emerging_topics":
            patterns[
                "emerging_topics"
            ],

        "topic_evolution":
            patterns[
                "topic_evolution"
            ],

        "question_blueprints":
            patterns[
                "question_blueprints"
            ],

        "question_type_distribution":
            patterns[
                "question_type_distribution"
            ],

        "bloom_distribution":
            patterns[
                "bloom_distribution"
            ],

        "part_analysis":
            patterns.get(
                "part_analysis",
                []
            ),

        "question_records": [
            {
        "year": int(row["year"]),
        "part": str(row["part"]),
        "question_number":
            int(row["question_number"]),
        "marks":
            (
                int(row["marks"])
                if pd.notna(row["marks"])
                else None
            ),
        "question":
            str(row["question"]),
        "topic":
            str(row["topic"]),
        "similarity":
            float(row["similarity"]),
        "unit":
            str(row["unit"])
    }
    for _, row in df.iterrows()
],
    }
    return make_json_safe(result_data)


def make_json_safe(obj):
    if isinstance(obj, dict):
        return {
            str(k): make_json_safe(v)
            for k, v in obj.items()
        }

    if isinstance(obj, list):
        return [
            make_json_safe(v)
            for v in obj
        ]

    if isinstance(obj, tuple):
        return [
            make_json_safe(v)
            for v in obj
        ]

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    return obj

def report(r,path):
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
 from reportlab.lib.pagesizes import A4
 from reportlab.lib import colors
 from reportlab.lib.styles import getSampleStyleSheet
 s=getSampleStyleSheet(); d=SimpleDocTemplate(path,pagesize=A4); story=[Paragraph('Semantic-Temporal Examination Trend Analysis',s['Title']),Spacer(1,12),Paragraph(f"Papers: {r['summary']['papers']} | Questions: {r['summary']['questions']} | Years: {r['summary']['years']}",s['BodyText']),Spacer(1,12),Paragraph('Top Forecasted Topics',s['Heading2'])]
 data=[['Rank','Topic','Score','Recent','Recurrence','Trend']]+[[x['rank'],x['topic'],x['forecast_score'],x['evidence']['recent_frequency'],x['evidence']['recurrence_rate'],x['evidence']['trend_slope']] for x in r['forecast']]; t=Table(data,repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef7')),('GRID',(0,0),(-1,-1),.5,colors.grey),('PADDING',(0,0),(-1,-1),6)])); story += [t,Spacer(1,14),Paragraph('Back-Testing Summary',s['Heading2'])]; b=r['backtest_summary']; data2=[['Method','Precision@5','Recall@5','F1@5'],['Proposed',b['proposed']['precision_at_k'],b['proposed']['recall_at_k'],b['proposed']['f1_at_k']],['Frequency',b['frequency_baseline']['precision_at_k'],b['frequency_baseline']['recall_at_k'],b['frequency_baseline']['f1_at_k']],['Recency',b['recency_baseline']['precision_at_k'],b['recency_baseline']['recall_at_k'],b['recency_baseline']['f1_at_k']]]; t2=Table(data2,repeatRows=1); t2.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef7')),('GRID',(0,0),(-1,-1),.5,colors.grey),('PADDING',(0,0),(-1,-1),6)])); story += [t2]; d.build(story)
