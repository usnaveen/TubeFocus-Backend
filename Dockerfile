# Use a specific Python version for reproducibility
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies first
# This leverages Docker's layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- NEW: Copy the downloaded models into the container ---
# This assumes you have a 'models' directory in your project root.
COPY ./models /app/models

# Copy the rest of your application code
COPY . .

# Command to run the application using gunicorn
# Increased workers and threads for better performance on Cloud Run
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "app:app"]
