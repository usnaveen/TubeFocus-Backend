# 1) Use a slim Python base
FROM python:3.10-slim

# 2) Create & switch to the app directory
WORKDIR /app

# 3) Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copy all your source code
COPY . .

# 5) Expose port 8080 (Cloud Run & local)
EXPOSE 8080

# 6) Run via Gunicorn, with:
#    --preload   : Load the Flask app (and models) in master before forking workers
#    --timeout 120 : Give workers up to 120s to finish imports/startup
CMD ["gunicorn", "app:app", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "1", \
     "--preload", \
     "--timeout", "120" ]
