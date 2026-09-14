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

def model():
 global _model
 if _model is None: _model=SentenceTransformer(EMBEDDING_MODEL)
 return _model

def configure_ocr():
 for p in [TESSERACT_PATH,r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',r'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe']:
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
 m=re.search(r'(20\d{2})',name); return int(m.group(1)) if m else None

def segment(text):
 pat=re.compile(r'(?:^|\n)\s*(?:q(?:uestion)?\s*)?(\d{1,2})\s*[\.\):\-]\s*',re.I); ms=list(pat.finditer(text)); out=[]
 if ms:
  for i,m in enumerate(ms):
   q=re.sub(r'\s+',' ',text[m.end():(ms[i+1].start() if i+1<len(ms) else len(text))]).strip()
   if len(q)>=15: out.append(q)
 else:
  out=[re.sub(r'\s+',' ',x).strip() for x in re.split(r'\n\s*\n+',text) if len(x.strip())>=30]
 return out

def assign(questions):
 topics=list(TOPIC_TO_UNIT); emq=model().encode(questions,normalize_embeddings=True,show_progress_bar=False); emt=model().encode(topics,normalize_embeddings=True,show_progress_bar=False); sim=np.matmul(np.asarray(emq),np.asarray(emt).T); out=[]
 for q,row in zip(questions,sim):
  j=int(np.argmax(row)); s=float(row[j]); out.append((q,topics[j] if s>=SEMANTIC_THRESHOLD else 'Unassigned',s))
 return out

def analyze(paths):
 rec=[]; errors=[]
 for p in paths:
  y=year_of(os.path.basename(p))
  if y is None: errors.append({'file':os.path.basename(p),'error':'Year missing from filename'}); continue
  try:
   for q,t,s in assign(segment(extract_text(p))): rec.append({'file':os.path.basename(p),'year':y,'question':q,'topic':t,'similarity':round(s,4),'unit':TOPIC_TO_UNIT.get(t,'Unassigned')})
  except Exception as e: errors.append({'file':os.path.basename(p),'error':str(e)})
 if not rec: raise ValueError('No questions extracted. Check PDF filenames, Tesseract and Poppler.')
 return pd.DataFrame(rec),errors

def matrix(df): return pd.crosstab(df[df.topic!='Unassigned'].topic,df[df.topic!='Unassigned'].year).sort_index(axis=1)

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

def backtest(m,k=TOP_K):
 years=list(m.columns); rows=[]
 for i in range(2,len(years)):
  train=m[years[:i]]; actual=set(m.index[m[years[i]]>0]); proposed=[x['topic'] for x in rank(train,k)]; freq=list(train.sum(1).sort_values(ascending=False).head(k).index); recent=list(train[years[i-1]].sort_values(ascending=False).head(k).index); rows.append({'train_until':years[i-1],'test_year':years[i],'proposed':metrics(proposed,actual,k),'frequency_baseline':metrics(freq,actual,k),'recency_baseline':metrics(recent,actual,k)})
 return rows

def aggregate(rows):
 out={}
 for key in ['proposed','frequency_baseline','recency_baseline']:
  vals=[r[key] for r in rows]; out[key]={z:round(float(np.mean([v[z] for v in vals])),4) if vals else 0 for z in ['precision_at_k','recall_at_k','f1_at_k']}
 return out

def result(df):
 m=matrix(df); f=features(m); bt=backtest(m); return {'summary':{'papers':int(df.file.nunique()),'questions':len(df),'assigned_questions':int((df.topic!='Unassigned').sum()),'unassigned_questions':int((df.topic=='Unassigned').sum()),'years':sorted(map(int,df.year.unique())),'topics':int(df[df.topic!='Unassigned'].topic.nunique())},'topic_frequency':[{'topic':k,'count':int(v)} for k,v in df[df.topic!='Unassigned'].topic.value_counts().head(30).items()],'unit_frequency':[{'unit':k,'count':int(v)} for k,v in df[df.unit!='Unassigned'].unit.value_counts().items()],'topic_year':{str(t):{str(y):int(v) for y,v in row.items()} for t,row in m.iterrows()},'temporal_features':f.to_dict('records'),'forecast':rank(m),'backtest':bt,'backtest_summary':aggregate(bt)}

def report(r,path):
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
 from reportlab.lib.pagesizes import A4
 from reportlab.lib import colors
 from reportlab.lib.styles import getSampleStyleSheet
 s=getSampleStyleSheet(); d=SimpleDocTemplate(path,pagesize=A4); story=[Paragraph('Semantic-Temporal Examination Trend Analysis',s['Title']),Spacer(1,12),Paragraph(f"Papers: {r['summary']['papers']} | Questions: {r['summary']['questions']} | Years: {r['summary']['years']}",s['BodyText']),Spacer(1,12),Paragraph('Top Forecasted Topics',s['Heading2'])]
 data=[['Rank','Topic','Score','Recent','Recurrence','Trend']]+[[x['rank'],x['topic'],x['forecast_score'],x['evidence']['recent_frequency'],x['evidence']['recurrence_rate'],x['evidence']['trend_slope']] for x in r['forecast']]; t=Table(data,repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef7')),('GRID',(0,0),(-1,-1),.5,colors.grey),('PADDING',(0,0),(-1,-1),6)])); story += [t,Spacer(1,14),Paragraph('Back-Testing Summary',s['Heading2'])]; b=r['backtest_summary']; data2=[['Method','Precision@5','Recall@5','F1@5'],['Proposed',b['proposed']['precision_at_k'],b['proposed']['recall_at_k'],b['proposed']['f1_at_k']],['Frequency',b['frequency_baseline']['precision_at_k'],b['frequency_baseline']['recall_at_k'],b['frequency_baseline']['f1_at_k']],['Recency',b['recency_baseline']['precision_at_k'],b['recency_baseline']['recall_at_k'],b['recency_baseline']['f1_at_k']]]; t2=Table(data2,repeatRows=1); t2.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef7')),('GRID',(0,0),(-1,-1),.5,colors.grey),('PADDING',(0,0),(-1,-1),6)])); story += [t2]; d.build(story)
