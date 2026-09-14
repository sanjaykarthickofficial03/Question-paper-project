import os,uuid
from pathlib import Path
from flask import Flask,jsonify,request,send_file
from flask_cors import CORS
from analyzer import analyze,result,report
from config import UPLOAD_FOLDER,REPORT_FOLDER
app=Flask(__name__); CORS(app); os.makedirs(UPLOAD_FOLDER,exist_ok=True); os.makedirs(REPORT_FOLDER,exist_ok=True); LAST=None
@app.get('/api/health')
def health(): return jsonify(status='ok')
@app.post('/api/analyze')
def run():
 global LAST
 files=request.files.getlist('files'); paths=[]
 if not files:return jsonify(error='Upload at least one PDF.'),400
 try:
  for f in files:
   if f.filename.lower().endswith('.pdf'):
    p=os.path.join(UPLOAD_FOLDER,f'{uuid.uuid4().hex}_{Path(f.filename).name}'); f.save(p); paths.append(p)
  df,errors=analyze(paths); LAST=result(df); LAST['errors']=errors; return jsonify(LAST)
 except Exception as e:return jsonify(error=str(e)),500
 finally:
  for p in paths:
   try:os.remove(p)
   except OSError:pass
@app.post('/api/report')
def get_report():
 if LAST is None:return jsonify(error='Run analysis first.'),400
 p=os.path.join(REPORT_FOLDER,'exam_trend_research_report.pdf'); report(LAST,p); return send_file(p,as_attachment=True,download_name='exam_trend_research_report.pdf')
if __name__=='__main__':app.run(host='127.0.0.1',port=5000,debug=True)
