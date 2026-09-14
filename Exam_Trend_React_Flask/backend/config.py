import os
BASE=os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER=os.path.join(BASE,'uploads'); REPORT_FOLDER=os.path.join(BASE,'reports')
TESSERACT_PATH=os.getenv('TESSERACT_PATH',''); POPPLER_PATH=os.getenv('POPPLER_PATH','')
EMBEDDING_MODEL=os.getenv('EMBEDDING_MODEL','sentence-transformers/all-MiniLM-L6-v2')
SEMANTIC_THRESHOLD=float(os.getenv('SEMANTIC_THRESHOLD','0.34')); TOP_K=int(os.getenv('TOP_K','5'))
