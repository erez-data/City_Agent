FROM cityagent-scraper-base:latest

WORKDIR /app

# First copy requirements for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy utils and application code

COPY . .

CMD ["python", "-u", "elife_main.py"]