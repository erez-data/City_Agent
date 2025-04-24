FROM scraper-base:latest

WORKDIR /app

# First copy requirements for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy utils and application code
COPY utils/ /app/utils/
COPY . .

CMD ["python", "elife_scraper.py"]