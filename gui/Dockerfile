# For Streamlit dashboard service
FROM python:3.10-bullseye

# Set timezone and locales
ENV TZ=Europe/Istanbul
RUN apt-get update && \
    apt-get install -y --no-install-recommends locales tzdata && \
    echo "tr_TR.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen && \
    ln -fs /usr/share/zoneinfo/Europe/Istanbul /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV LANG=tr_TR.UTF-8 \
    LANGUAGE=tr_TR:tr \
    LC_ALL=tr_TR.UTF-8 \
    PYTHONPATH=/app:/app/utils

WORKDIR /app

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Açılması gereken port
EXPOSE 8501

# Streamlit serverı başlat
CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
