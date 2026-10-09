import React, { useMemo, useState } from 'react'
import {createRoot} from 'react-dom/client'
import {
  BarChart3,
  BrainCircuit,
  FileText,
  FlaskConical,
  UploadCloud,
  TrendingUp,
  Download,
  AlertCircle,
  Database,
  Sparkles,
  Flame,
  GitBranch,
  Lightbulb,
  Target,
  Clock3,
  ChevronRight
} from 'lucide-react';

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LineChart,
  Line
} from 'recharts';

import './styles.css';


/* =========================================================
   Small reusable components
   ========================================================= */

function Stat({ icon: Icon, label, value, note }) {
  return (
    <div className="stat">
      <div className="ico">
        <Icon size={18} />
      </div>

      <div>
        <small>{label}</small>
        <strong>{value}</strong>
        {note && <em>{note}</em>}
      </div>
    </div>
  );
}


function SectionHeader({ icon: Icon, title, subtitle }) {
  return (
    <div className="section-header">
      <div className="section-title-row">
        {Icon && <Icon size={20} />}
        <h2>{title}</h2>
      </div>

      {subtitle && <span>{subtitle}</span>}
    </div>
  );
}


function EmptyState({ icon: Icon = Database, title, text }) {
  return (
    <div className="empty">
      <Icon size={38} />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}


/* =========================================================
   Main application
   ========================================================= */

function App() {
  const [files, setFiles] = useState([]);
  const [r, setR] = useState(null);
  const [tab, setTab] = useState('overview');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const [selectedTopic, setSelectedTopic] = useState(null);

  const [practiceQuestion, setPracticeQuestion] = useState('');
  const [generatingPractice, setGeneratingPractice] = useState(false);

  /*
   * Existing year-wise chart.
   */
  const evolution = useMemo(() => {
    if (!r) return [];

    return r.summary.years.map((y) => {
      const x = { year: y };

      Object.entries(r.topic_year || {})
        .slice(0, 5)
        .forEach(([t, v]) => {
          x[t] = v[String(y)] || 0;
        });

      return x;
    });
  }, [r]);


  /*
   * Use the learned forecast if the new backend is available.
   * Otherwise fall back to the original transparent forecast.
   */
  const forecastData = useMemo(() => {
    if (!r) return [];

    if (
      Array.isArray(r.learned_forecast) &&
      r.learned_forecast.length
    ) {
      return r.learned_forecast.map((x, index) => ({
        ...x,
        rank: x.rank || index + 1,
        forecast_score:
          x.forecast_probability ??
          x.forecast_score ??
          0,
        isLearned: true
      }));
    }

    return (r.forecast || []).map((x, index) => ({
      ...x,
      rank: x.rank || index + 1,
      forecast_score: x.forecast_score || 0,
      isLearned: false
    }));
  }, [r]);


  /*
   * Selected topic blueprint.
   *
   * This comes directly from the new backend response.
   */
  const selectedBlueprint =
    selectedTopic &&
    r?.question_blueprints?.[selectedTopic]
      ? r.question_blueprints[selectedTopic]
      : null;


  const selectedEvolution =
    selectedTopic &&
    r?.topic_evolution?.[selectedTopic]
      ? r.topic_evolution[selectedTopic]
      : null;


  /*
   * Question-level records added in Phase 2.
   * These include year, Part A/B/C, question number,
   * marks, topic and semantic similarity.
   */
  const questionRecords = useMemo(() => {
    if (!r) return [];

    return [...(r.question_records || [])].sort(
      (a, b) =>
        Number(a.year || 0) - Number(b.year || 0) ||
        String(a.part || '').localeCompare(
          String(b.part || '')
        ) ||
        Number(a.question_number || 0) -
          Number(b.question_number || 0)
    );
  }, [r]);


  const partSummary = useMemo(() => {
    const defaults = {
      A: 2,
      B: 13,
      C: 15
    };

    return ['A', 'B', 'C'].map((part) => {
      const questions = questionRecords.filter(
        (q) => q.part === part
      );

      const marks =
        questions.find(
          (q) => q.marks !== null && q.marks !== undefined
        )?.marks ?? defaults[part];

      return {
        part,
        marks,
        count: questions.length,
        assigned: questions.filter(
          (q) => q.topic !== 'Unassigned'
        ).length
      };
    });
  }, [questionRecords]);


  /* =======================================================
     API calls
     ======================================================= */

  async function analyze() {
    if (!files.length) {
      setErr('Select PDF question papers first.');
      return;
    }

    setBusy(true);
    setErr('');
    setSelectedTopic(null);
    setPracticeQuestion('');

    const f = new FormData();

    files.forEach((x) => {
      f.append('files', x);
    });

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        body: f
      });

      const d = await res.json();

      if (!res.ok) {
        throw new Error(d.error || 'Analysis failed.');
      }

      setR(d);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }


  async function download() {
    try {
      const res = await fetch('/api/report', {
        method: 'POST'
      });

      if (!res.ok) {
        const data = await res.json();
        setErr(data.error || 'Unable to generate report.');
        return;
      }

      const b = await res.blob();
      const u = URL.createObjectURL(b);
      const a = document.createElement('a');

      a.href = u;
      a.download = 'exam_trend_research_report.pdf';

      document.body.appendChild(a);
      a.click();
      a.remove();

      URL.revokeObjectURL(u);
    } catch (e) {
      setErr(e.message);
    }
  }


  async function generatePracticeQuestion(topic) {
    setGeneratingPractice(true);
    setPracticeQuestion('');
    setErr('');

    try {
      const res = await fetch(
        '/api/generate-practice-question',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ topic })
        }
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data.error ||
          'Unable to generate practice question.'
        );
      }

      setPracticeQuestion(
        data.question || ''
      );
    } catch (e) {
      setErr(
        `Practice question generation failed: ${e.message}`
      );
    } finally {
      setGeneratingPractice(false);
    }
  }


  function openTopic(topic) {
    setSelectedTopic(topic);
    setPracticeQuestion('');
    setTab('patterns');
  }


  /* =======================================================
     Navigation
     ======================================================= */

  const nav = [
    ['overview', 'Overview', BarChart3],
    ['questions', 'Question Papers', FileText],
    ['semantic', 'Semantic Analysis', BrainCircuit],
    ['temporal', 'Temporal Trends', TrendingUp],
    ['forecast', 'Forecast', Sparkles],
    ['patterns', 'Emerging & Patterns', GitBranch],
    ['evaluation', 'Evaluation', FlaskConical]
  ];


  /* =======================================================
     Render
     ======================================================= */

  return (
    <div className="shell">

      {/* ===================================================
          SIDEBAR
          =================================================== */}

      <aside>

        <div className="brand">

          <div className="logo">
            <BrainCircuit size={21} />
          </div>

          <div>
            <b>ExamTrend</b>
            <small>Research Prototype</small>
          </div>

        </div>


        <label>ANALYSIS</label>

        {nav.map(([k, n, I]) => (
          <button
            className={tab === k ? 'sel' : ''}
            onClick={() => setTab(k)}
            key={k}
          >
            <I size={17} />
            {n}
          </button>
        ))}


        <footer>
          Semantic + Temporal
          <br />

          <span>
            Topic-level forecasting, not
            exact-question prediction.
          </span>
        </footer>

      </aside>


      {/* ===================================================
          MAIN
          =================================================== */}

      <main>

        <header>

          <div>

            <small>RESEARCH ANALYTICS</small>

            <h1>
              Intelligent Examination Trend Analysis
            </h1>

            <p>
              Semantic topic discovery, temporal evolution,
              learned forecasting and explainable examination
              pattern analysis.
            </p>

          </div>


          <button
            className="export"
            disabled={!r}
            onClick={download}
          >
            <Download size={16} />
            Export Report
          </button>

        </header>


        {/* =================================================
            UPLOAD
            ================================================= */}

        <section className="upload">

          <div className="uploadcopy">

            <UploadCloud size={22} />

            <div>

              <b>
                Analyze historical papers
              </b>

              <p>
                Use filenames containing the year,
                e.g. <strong>Physics_2024.pdf</strong>.
              </p>

            </div>

          </div>


          <label className="drop">

            <input
              type="file"
              accept=".pdf"
              multiple
              onChange={(e) =>
                setFiles([
                  ...e.target.files
                ])
              }
            />

            <FileText size={19} />

            {
              files.length
                ? `${files.length} PDF(s) selected`
                : 'Choose PDF question papers'
            }

          </label>


          <button
            className="run"
            onClick={analyze}
            disabled={busy}
          >
            {
              busy
                ? 'Analyzing...'
                : 'Run Research Analysis'
            }
          </button>

        </section>


        {/* =================================================
            ERROR
            ================================================= */}

        {err && (
          <div className="alert">
            <AlertCircle size={17} />
            {err}
          </div>
        )}


        {/* =================================================
            EMPTY STATE
            ================================================= */}

        {!r ? (

          <EmptyState
            icon={Database}
            title="Ready for your question-paper corpus"
            text="Upload multiple years to activate semantic mapping, temporal analysis, learned forecasting, emerging-topic detection and question-pattern analysis."
          />

        ) : (

          <>

            {/* =============================================
                OVERVIEW
                ============================================= */}

            {tab === 'overview' && (

              <>

                <div className="stats">

                  <Stat
                    icon={FileText}
                    label="Papers"
                    value={r.summary.papers}
                  />

                  <Stat
                    icon={Database}
                    label="Questions"
                    value={r.summary.questions}
                  />

                  <Stat
                    icon={BrainCircuit}
                    label="Topics"
                    value={r.summary.topics}
                  />

                  <Stat
                    icon={TrendingUp}
                    label="Years"
                    value={r.summary.years.length}
                    note={
                      `${r.summary.years[0]}–${r.summary.years.at(-1)}`
                    }
                  />

                </div>


                <div className="coverage-strip overview-coverage">

                  <div>
                    <span>Extracted Questions</span>
                    <strong>
                      {questionRecords.length}
                    </strong>
                  </div>

                  <div>
                    <span>Topic Assigned</span>
                    <strong>
                      {
                        questionRecords.filter(
                          (q) =>
                            q.topic !== 'Unassigned'
                        ).length
                      }
                    </strong>
                  </div>

                  <div>
                    <span>Unassigned</span>
                    <strong>
                      {
                        questionRecords.filter(
                          (q) =>
                            q.topic === 'Unassigned'
                        ).length
                      }
                    </strong>
                  </div>

                  <div>
                    <span>Parts Detected</span>
                    <strong>
                      {
                        new Set(
                          questionRecords
                            .map((q) => q.part)
                            .filter(Boolean)
                        ).size
                      }
                    </strong>
                  </div>

                </div>


                <div className="two">

                  <section className="panel">

                    <SectionHeader
                      icon={Target}
                      title="Topic Frequency"
                      subtitle="Semantic topic assignments"
                    />

                    <ResponsiveContainer
                      width="100%"
                      height={330}
                    >

                      <BarChart
                        data={
                          r.topic_frequency?.slice(
                            0,
                            12
                          ) || []
                        }
                        layout="vertical"
                      >

                        <CartesianGrid
                          strokeDasharray="3 3"
                        />

                        <XAxis type="number" />

                        <YAxis
                          type="category"
                          dataKey="topic"
                          width={140}
                          tick={{
                            fontSize: 11
                          }}
                        />

                        <Tooltip />

                        <Bar
                          dataKey="count"
                          fill="#5267d8"
                          radius={[
                            0,
                            5,
                            5,
                            0
                          ]}
                        />

                      </BarChart>

                    </ResponsiveContainer>

                  </section>


                  <section className="panel">

                    <SectionHeader
                      icon={Database}
                      title="Unit Distribution"
                      subtitle="Question coverage by unit"
                    />

                    <ResponsiveContainer
                      width="100%"
                      height={330}
                    >

                      <BarChart
                        data={
                          r.unit_frequency || []
                        }
                      >

                        <CartesianGrid
                          strokeDasharray="3 3"
                        />

                        <XAxis
                          dataKey="unit"
                          tick={{
                            fontSize: 9
                          }}
                          angle={-18}
                          textAnchor="end"
                          height={75}
                        />

                        <YAxis />

                        <Tooltip />

                        <Bar
                          dataKey="count"
                          fill="#7a87dd"
                        />

                      </BarChart>

                    </ResponsiveContainer>

                  </section>

                </div>


                {/* Quick emerging-topic preview */}

                {r.emerging_topics?.length > 0 && (

                  <section className="panel">

                    <SectionHeader
                      icon={Flame}
                      title="Emerging Topics"
                      subtitle="Topics showing increasing recent examination activity"
                    />

                    <div className="emerging-grid">

                      {r.emerging_topics
                        .slice(0, 5)
                        .map((item) => (

                          <button
                            className="emerging-card"
                            key={item.topic}
                            onClick={() =>
                              openTopic(
                                item.topic
                              )
                            }
                          >

                            <div className="emerging-rank">
                              #{item.rank}
                            </div>

                            <h3>
                              {item.topic}
                            </h3>

                            <div className="emerging-score">
                              {
                                (
                                  item.emerging_score *
                                  100
                                ).toFixed(0)
                              }%
                            </div>

                            <div className="emerging-details">

                              <span>
                                Recent:
                                {' '}
                                {item.recent_frequency}
                              </span>

                              <span>
                                Growth:
                                {' '}
                                {item.growth_ratio}×
                              </span>

                            </div>

                          </button>

                        ))}

                    </div>

                  </section>

                )}

              </>

            )}


            {/* =============================================
                QUESTION PAPERS
                ============================================= */}

            {tab === 'questions' && (

              <>

                <section className="panel">

                  <SectionHeader
                    icon={FileText}
                    title="Question Paper Structure"
                    subtitle="Question-level view with examination part, marks and semantic topic assignment."
                  />

                  <div className="part-summary">

                    {partSummary.map((item) => (

                      <div
                        className="part-summary-card"
                        key={item.part}
                      >

                        <span>
                          PART {item.part}
                        </span>

                        <strong>
                          {item.marks} marks
                        </strong>

                        <small>
                          {item.count} question(s)
                          {' · '}
                          {item.assigned} assigned
                        </small>

                      </div>

                    ))}

                  </div>


                  <div className="coverage-strip">

                    <div>
                      <span>Total extracted</span>
                      <strong>
                        {questionRecords.length}
                      </strong>
                    </div>

                    <div>
                      <span>Assigned to topic</span>
                      <strong>
                        {
                          questionRecords.filter(
                            (q) =>
                              q.topic !== 'Unassigned'
                          ).length
                        }
                      </strong>
                    </div>

                    <div>
                      <span>Unassigned</span>
                      <strong>
                        {
                          questionRecords.filter(
                            (q) =>
                              q.topic === 'Unassigned'
                          ).length
                        }
                      </strong>
                    </div>

                  </div>


                  {!questionRecords.length ? (

                    <div className="empty-table">
                      No question-level records are available.
                      Make sure the backend returns
                      <b> question_records</b>.
                    </div>

                  ) : (

                    <div className="question-table-wrap">

                      <table className="question-table">

                        <thead>
                          <tr>
                            <th>Year</th>
                            <th>Part</th>
                            <th>Q.No.</th>
                            <th>Marks</th>
                            <th>Topic</th>
                            <th>Similarity</th>
                            <th>Question</th>
                          </tr>
                        </thead>

                        <tbody>

                          {questionRecords.map(
                            (q, index) => (

                              <tr key={index}>

                                <td>
                                  {q.year}
                                </td>

                                <td>

                                  <span
                                    className={`part-badge part-${String(
                                      q.part || 'Unknown'
                                    ).toUpperCase()}`}
                                  >
                                    Part {q.part || '—'}
                                  </span>

                                </td>

                                <td>
                                  {q.question_number ??
                                    '—'}
                                </td>

                                <td>
                                  <strong>
                                    {q.marks ??
                                      'N/A'}
                                  </strong>
                                </td>

                                <td>
                                  <span
                                    className={
                                      q.topic === 'Unassigned'
                                        ? 'unassigned-topic'
                                        : 'assigned-topic'
                                    }
                                  >
                                    {q.topic || 'Unassigned'}
                                  </span>
                                </td>

                                <td>
                                  {q.similarity !== null &&
                                  q.similarity !== undefined
                                    ? Number(
                                        q.similarity
                                      ).toFixed(2)
                                    : 'N/A'}
                                </td>

                                <td className="question-text">
                                  {q.question}
                                </td>

                              </tr>

                            )
                          )}

                        </tbody>

                      </table>

                    </div>

                  )}

                </section>

              </>

            )}


            {/* =============================================
                SEMANTIC
                ============================================= */}

            {tab === 'semantic' && (

              <section className="panel">

                <SectionHeader
                  icon={BrainCircuit}
                  title="Semantic Topic Analysis"
                  subtitle="Questions are mapped to syllabus concepts using sentence embeddings."
                />

                <div className="methods">

                  <div>
                    <BrainCircuit />
                    <b>Sentence-BERT</b>
                    <small>
                      Meaning-aware question
                      embeddings.
                    </small>
                  </div>

                  <div>
                    <Database />
                    <b>Semantic Matching</b>
                    <small>
                      Nearest reference topic
                      assignment.
                    </small>
                  </div>

                  <div>
                    <AlertCircle />
                    <b>Thresholding</b>
                    <small>
                      Low-confidence matches
                      can remain unassigned.
                    </small>
                  </div>

                </div>


                <Table
                  rows={
                    r.temporal_features || []
                  }
                />

              </section>

            )}


            {/* =============================================
                TEMPORAL
                ============================================= */}

            {tab === 'temporal' && (

              <section className="panel">

                <SectionHeader
                  icon={TrendingUp}
                  title="Topic Evolution Over Time"
                  subtitle="Year-wise frequency of the leading semantic topics."
                />

                <ResponsiveContainer
                  width="100%"
                  height={450}
                >

                  <LineChart
                    data={evolution}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                    />

                    <XAxis
                      dataKey="year"
                    />

                    <YAxis
                      allowDecimals={false}
                    />

                    <Tooltip />

                    <Legend />

                    {
                      Object.keys(
                        r.topic_year || {}
                      )
                      .slice(0, 5)
                      .map((t, i) => (

                        <Line
                          key={t}
                          type="monotone"
                          dataKey={t}
                          stroke={
                            [
                              '#5267d8',
                              '#38a169',
                              '#d97706',
                              '#a855f7',
                              '#0891b2'
                            ][i]
                          }
                          strokeWidth={2.5}
                        />

                      ))
                    }

                  </LineChart>

                </ResponsiveContainer>

              </section>

            )}


            {/* =============================================
                FORECAST
                ============================================= */}

            {tab === 'forecast' && (

              <>

                <section className="panel">

                  <SectionHeader
                    icon={Sparkles}
                    title="Top-K Topic Forecast"
                    subtitle={
                      forecastData.some(
                        x => x.isLearned
                      )
                        ? 'Learned semantic-temporal forecasting using historical topic behavior.'
                        : 'Transparent score using recent frequency, recurrence, trend and recency.'
                    }
                  />


                  {forecastData.some(
                    x => x.isLearned
                  ) && (

                    <div className="research-note">
                      <BrainCircuit size={17} />

                      <span>
                        <b>Learned model active.</b>
                        {' '}
                        Click a topic to inspect its
                        historical evolution and future
                        question blueprint.
                      </span>

                    </div>

                  )}


                  <div className="forecasts">

                    {forecastData.map((x) => (

                      <button
                        className="forecast"
                        key={x.topic}
                        onClick={() =>
                          openTopic(
                            x.topic
                          )
                        }
                      >

                        <div className="rank">
                          {x.rank}
                        </div>

                        <div className="fmain">

                          <b>
                            {x.topic}
                          </b>

                          <small>
                            {x.unit || ''}
                          </small>

                          <div className="score">

                            <div>
                              <i
                                style={{
                                  width:
                                    `${x.forecast_score * 100}%`
                                }}
                              />
                            </div>

                            {
                              Number(
                                x.forecast_score
                              ).toFixed(2)
                            }

                          </div>

                        </div>


                        <div className="evidence">

                          {
                            x.evidence ? (
                              <>
                                <span>
                                  Recent
                                  {' '}
                                  <b>
                                    {
                                      x.evidence
                                        .recent_frequency ??
                                      0
                                    }
                                  </b>
                                </span>

                                <span>
                                  Years
                                  {' '}
                                  <b>
                                    {
                                      x.evidence
                                        .active_years ??
                                      0
                                    }
                                  </b>
                                </span>

                                <span>
                                  Trend
                                  {' '}
                                  <b>
                                    {
                                      Number(
                                        x.evidence
                                          .trend_slope ??
                                        0
                                      ).toFixed(2)
                                    }
                                  </b>
                                </span>
                              </>
                            ) : (
                              <span>
                                Probability
                                {' '}
                                <b>
                                  {
                                    (
                                      x.forecast_score *
                                      100
                                    ).toFixed(1)
                                  }%
                                </b>
                              </span>
                            )
                          }

                        </div>

                        <ChevronRight
                          size={18}
                        />

                      </button>

                    ))}

                  </div>

                </section>


                {/* Forecast explanation */}

                <section className="panel">

                  <SectionHeader
                    icon={Lightbulb}
                    title="How to read the forecast"
                    subtitle="The system forecasts topic recurrence, not exact future questions."
                  />

                  <div className="explanation-grid">

                    <div>
                      <Clock3 />
                      <b>Temporal evidence</b>
                      <p>
                        Recent frequency, recurrence,
                        recency gaps and historical trend.
                      </p>
                    </div>

                    <div>
                      <BrainCircuit />
                      <b>Semantic evidence</b>
                      <p>
                        Sentence-level semantic similarity
                        helps group differently worded
                        questions under related concepts.
                      </p>
                    </div>

                    <div>
                      <Target />
                      <b>Top-K prediction</b>
                      <p>
                        Topics are ranked by their estimated
                        likelihood of recurring in the next
                        examination period.
                      </p>
                    </div>

                  </div>

                </section>

              </>

            )}


            {/* =============================================
                EMERGING + PATTERNS
                ============================================= */}

            {tab === 'patterns' && (

              <>

                <section className="panel">

                  <SectionHeader
                    icon={Flame}
                    title="Emerging Topics"
                    subtitle="Topics showing increasing recent examination activity."
                  />


                  {!r.emerging_topics?.length ? (

                    <EmptyState
                      icon={Flame}
                      title="No emerging-topic data"
                      text="Run the enhanced backend analysis with multiple historical years."
                    />

                  ) : (

                    <div className="emerging-grid">

                      {r.emerging_topics.map(
                        (item) => (

                          <button
                            className={
                              selectedTopic ===
                              item.topic
                                ? 'emerging-card active'
                                : 'emerging-card'
                            }
                            key={item.topic}
                            onClick={() =>
                              openTopic(
                                item.topic
                              )
                            }
                          >

                            <div className="emerging-rank">
                              #{item.rank}
                            </div>

                            <h3>
                              {item.topic}
                            </h3>

                            <div className="emerging-score">
                              {
                                (
                                  item.emerging_score *
                                  100
                                ).toFixed(0)
                              }%
                            </div>

                            <div className="emerging-details">

                              <span>
                                Recent:
                                {' '}
                                {item.recent_frequency}
                              </span>

                              <span>
                                Growth:
                                {' '}
                                {item.growth_ratio}×
                              </span>

                              <span>
                                Consecutive years:
                                {' '}
                                {item.consecutive_recent_years}
                              </span>

                              <span>
                                Semantic similarity:
                                {' '}
                                {item.recent_similarity}
                              </span>

                            </div>

                          </button>

                        )
                      )}

                    </div>

                  )}

                </section>


                {/* =========================================
                    SELECTED TOPIC
                    ========================================= */}

                {selectedTopic && (

                  <>

                    <section className="panel">

                      <SectionHeader
                        icon={GitBranch}
                        title={`${selectedTopic} · Question Pattern Evolution`}
                        subtitle="How the examination treatment of this topic has changed over time."
                      />


                      {!selectedEvolution ? (

                        <p>
                          No historical evolution data
                          is available for this topic.
                        </p>

                      ) : (

                        <div className="evolution-timeline">

                          {selectedEvolution.years.map(
                            (yearData) => (

                              <div
                                className="timeline-item"
                                key={yearData.year}
                              >

                                <div className="timeline-year">
                                  {yearData.year}
                                </div>

                                <div className="timeline-content">

                                  <strong>
                                    {
                                      yearData.question_count
                                    }
                                    {' '}
                                    question(s)
                                  </strong>

                                  <p>
                                    Avg. semantic similarity:
                                    {' '}
                                    {
                                      yearData.average_similarity
                                    }
                                  </p>

                                  <p>
                                    Bloom:
                                    {' '}
                                    {
                                      Object.entries(
                                        yearData
                                          .bloom_distribution ||
                                        {}
                                      )
                                      .map(
                                        ([level, count]) =>
                                          `${level} (${count})`
                                      )
                                      .join(', ')
                                    }
                                  </p>

                                  <p>
                                    Type:
                                    {' '}
                                    {
                                      Object.entries(
                                        yearData
                                          .question_types ||
                                        {}
                                      )
                                      .map(
                                        ([type, count]) =>
                                          `${type} (${count})`
                                      )
                                      .join(', ')
                                    }
                                  </p>

                                  {
                                    yearData
                                      .average_marks !==
                                      null &&
                                    yearData
                                      .average_marks !==
                                      undefined && (

                                      <p>
                                        Average marks:
                                        {' '}
                                        {
                                          yearData
                                            .average_marks
                                        }
                                      </p>

                                    )
                                  }


                                  {
                                    yearData.questions?.length >
                                      0 && (

                                      <details>
                                        <summary>
                                          View historical questions
                                        </summary>

                                        <div className="historical-questions">

                                          {
                                            yearData
                                              .questions
                                              .map(
                                                (q, i) => (

                                                  <div
                                                    key={i}
                                                  >

                                                    <p>
                                                      {q.question}
                                                    </p>

                                                    <small>
                                                      {
                                                        q.question_type
                                                      }
                                                      {' · '}
                                                      {
                                                        q.bloom_level
                                                      }
                                                      {
                                                        q.marks
                                                          ? ` · ${q.marks} marks`
                                                          : ''
                                                      }
                                                    </small>

                                                  </div>

                                                )
                                              )
                                          }

                                        </div>

                                      </details>

                                    )
                                  }

                                </div>

                              </div>

                            )
                          )}

                        </div>

                      )}

                    </section>


                    {/* =====================================
                        FUTURE QUESTION BLUEPRINT
                        ===================================== */}

                    <section className="panel">

                      <SectionHeader
                        icon={Sparkles}
                        title="Future Question Blueprint"
                        subtitle="A historical pattern-based blueprint, not an exact-question prediction."
                      />


                      {!selectedBlueprint ? (

                        <p>
                          No blueprint is available for
                          this topic.
                        </p>

                      ) : (

                        <>

                          <div className="blueprint-grid">

                            <div>
                              <span>Topic</span>
                              <strong>
                                {
                                  selectedBlueprint.topic
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Likely Question Type
                              </span>
                              <strong>
                                {
                                  selectedBlueprint
                                    .recent_question_type
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Likely Bloom Level
                              </span>
                              <strong>
                                {
                                  selectedBlueprint
                                    .recent_bloom_level
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Estimated Difficulty
                              </span>
                              <strong>
                                {
                                  selectedBlueprint
                                    .estimated_difficulty
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Historical Avg. Marks
                              </span>
                              <strong>
                                {
                                  selectedBlueprint
                                    .average_marks ??
                                  'N/A'
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Common Marks
                              </span>
                              <strong>
                                {
                                  selectedBlueprint
                                    .common_marks ??
                                  'N/A'
                                }
                              </strong>
                            </div>

                          </div>


                          <div className="blueprint-explanation">

                            <h3>
                              Historical Evidence
                            </h3>

                            {
                              (
                                selectedBlueprint
                                  .historical_evidence ||
                                []
                              ).map(
                                (item, index) => (

                                  <div
                                    className="evidence-item"
                                    key={index}
                                  >

                                    <strong>
                                      {item.year}
                                    </strong>

                                    <p>
                                      {item.question}
                                    </p>

                                    <small>
                                      {
                                        item.question_type
                                      }
                                      {' · '}
                                      {
                                        item.bloom_level
                                      }
                                      {
                                        item.marks
                                          ? ` · ${item.marks} marks`
                                          : ''
                                      }
                                    </small>

                                  </div>

                                )
                              )
                            }

                          </div>


                          {/* =================================
                              PRACTICE QUESTION
                              ================================= */}

                          <div className="practice-box">

                            <div>

                              <h3>
                                ✨ Practice Question
                              </h3>

                              <p>
                                Generate an original
                                practice question based
                                on the historical pattern.
                              </p>

                            </div>

                            <div className="practice-meta">

                              <span>
                                <b>Topic</b>
                                {selectedBlueprint.topic}
                              </span>

                              <span>
                                <b>Part</b>
                                {
                                  selectedBlueprint
                                    .common_part ||
                                  selectedBlueprint
                                    .recent_part ||
                                  '—'
                                }
                              </span>

                              <span>
                                <b>Marks</b>
                                {
                                  selectedBlueprint
                                    .common_marks ??
                                  'N/A'
                                }
                              </span>

                            </div>


                            <button
                              className="primary-button"
                              onClick={() =>
                                generatePracticeQuestion(
                                  selectedBlueprint.topic
                                )
                              }
                              disabled={
                                generatingPractice
                              }
                            >
                              <Sparkles size={16} />

                              {
                                generatingPractice
                                  ? 'Generating...'
                                  : 'Generate Practice Question'
                              }

                            </button>


                            {
                              practiceQuestion && (

                                <div className="practice-question">

                                  <p>
                                    {practiceQuestion}
                                  </p>

                                  <small>
                                    Generated from historical
                                    question patterns. This is
                                    a practice question, not a
                                    prediction of the exact
                                    future examination question.
                                  </small>

                                </div>

                              )
                            }

                          </div>

                        </>

                      )}

                    </section>

                  </>

                )}

              </>

            )}


            {/* =============================================
                EVALUATION
                ============================================= */}

            {tab === 'evaluation' && (

              <>

                <section className="panel">

                  <SectionHeader
                    icon={FlaskConical}
                    title="Historical Back-Testing"
                    subtitle="Chronological evaluation uses earlier years to predict a later year."
                  />


                  {
                    r.backtest_summary && (

                      <div className="metrics">

                        {
                          [
                            [
                              'Proposed Semantic-Temporal',
                              r.backtest_summary.proposed
                            ],
                            [
                              'Frequency Baseline',
                              r.backtest_summary.frequency_baseline
                            ],
                            [
                              'Recency Baseline',
                              r.backtest_summary.recency_baseline
                            ]
                          ].map(
                            ([n, m]) => (

                              <div key={n}>

                                <b>{n}</b>

                                <p>
                                  Precision@5
                                  {' '}
                                  <strong>
                                    {
                                      m?.precision_at_k != null
                                        ? Number(
                                            m.precision_at_k
                                          ).toFixed(2)
                                        : 'N/A'
                                    }
                                  </strong>
                                </p>

                                <p>
                                  Recall@5
                                  {' '}
                                  <strong>
                                    {
                                      m?.recall_at_k != null
                                        ? Number(
                                            m.recall_at_k
                                          ).toFixed(2)
                                        : 'N/A'
                                    }
                                  </strong>
                                </p>

                                <p>
                                  F1@5
                                  {' '}
                                  <strong>
                                    {
                                      m?.f1_at_k != null
                                        ? Number(
                                            m.f1_at_k
                                          ).toFixed(2)
                                        : 'N/A'
                                    }
                                  </strong>
                                </p>

                              </div>

                            )
                          )
                        }

                      </div>

                    )
                  }

                </section>


                <section className="panel">

                  <SectionHeader
                    icon={Clock3}
                    title="Back-Test Runs"
                    subtitle="Each run trains only on earlier examination years."
                  />

                  <Table
                    rows={r.backtest || []}
                  />

                </section>


                {/* Learned model feature importance */}

                {
                  r.learned_model_info
                    ?.feature_importance && (

                    <section className="panel">

                      <SectionHeader
                        icon={BrainCircuit}
                        title="Learned Model Feature Importance"
                        subtitle="Which semantic-temporal signals influenced the learned forecasting model."
                      />

                      <div className="importance-list">

                        {
                          Object.entries(
                            r.learned_model_info
                              .feature_importance
                          )
                          .sort(
                            ([, a], [, b]) =>
                              b - a
                          )
                          .map(
                            ([feature, importance]) => (

                              <div
                                className="importance-row"
                                key={feature}
                              >

                                <span>
                                  {
                                    feature.replaceAll(
                                      '_',
                                      ' '
                                    )
                                  }
                                </span>

                                <div className="importance-bar">
                                  <i
                                    style={{
                                      width:
                                        `${Number(
                                          importance
                                        ) * 100}%`
                                    }}
                                  />
                                </div>

                                <b>
                                  {
                                    (
                                      Number(
                                        importance
                                      ) * 100
                                    ).toFixed(1)
                                  }%
                                </b>

                              </div>

                            )
                          )
                        }

                      </div>

                    </section>

                  )
                }

              </>

            )}

          </>

        )}

      </main>

    </div>
  );
}


/* =========================================================
   Generic table
   ========================================================= */

function Table({ rows }) {

  if (!rows || !rows.length) {
    return (
      <div className="empty-table">
        No data available.
      </div>
    );
  }

  return (
    <div className="table">

      <table>

        <tbody>

          {rows.map((x, i) => (

            <tr key={i}>

              {Object.entries(x)
                .slice(0, 6)
                .map(([k, v]) => (

                  <td key={k}>

                    <small>
                      {k.replaceAll(
                        '_',
                        ' '
                      )}
                    </small>

                    <br />

                    {
                      typeof v === 'object'
                        ? JSON.stringify(v)
                        : String(v)
                    }

                  </td>

                ))}

            </tr>

          ))}

        </tbody>

      </table>

    </div>
  );
}


createRoot(
  document.getElementById('root')
).render(
  <App />
);
