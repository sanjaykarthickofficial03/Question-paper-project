# Exam Trend Research: React + Flask

Research-oriented full-stack prototype for **Semantic-Temporal Modeling of Examination Question Trends for Explainable Topic Forecasting**.

## Stack
- React + Vite + Recharts + Lucide React
- Flask REST API + Flask-CORS
- Pandas / NumPy / scikit-learn
- Sentence-BERT (`all-MiniLM-L6-v2`)
- pypdf + pdf2image + Tesseract OCR
- ReportLab

## Run backend
```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```
Backend: http://127.0.0.1:5000

## Run frontend
Requires Node.js.
```powershell
cd frontend
npm install
npm run dev
```
Frontend: http://localhost:5173

## OCR
Install Tesseract separately. If it is not on PATH:
```powershell
$env:TESSERACT_PATH="C:\Program Files\Tesseract-OCR\tesseract.exe"
```
For scanned PDFs, install Poppler and optionally set:
```powershell
$env:POPPLER_PATH="C:\path\to\poppler\Library\bin"
```

## Filename rule
Every PDF must contain a four-digit year, e.g. `Physics_2024.pdf`. This is needed for temporal analysis and chronological back-testing.

## Research pipeline
PDFs -> extraction/OCR -> question segmentation -> Sentence-BERT semantic assignment -> topic-year matrix -> temporal features -> Top-K forecast -> frequency/recency baselines -> chronological back-testing -> report.

Forecasting is topic-level and is not a guarantee of exact future questions.
