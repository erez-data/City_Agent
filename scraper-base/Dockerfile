# Base image
FROM python:3.10-slim

# Set environment variables
ENV TZ=Europe/Istanbul
ENV LANG=tr_TR.UTF-8
ENV LANGUAGE=tr_TR:tr
ENV LC_ALL=tr_TR.UTF-8
ENV PYTHONPATH=/app:/app/utils

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget curl unzip gnupg2 \
    locales tzdata \
    fonts-liberation libappindicator3-1 libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
    libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 \
    libxcomposite1 libxdamage1 libxrandr2 xdg-utils && \
    echo "tr_TR.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen && \
    ln -fs /usr/share/zoneinfo/Europe/Istanbul /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Download and install Google Chrome 114.0.5735.90 from University of Chicago mirror
WORKDIR /tmp
RUN wget https://mirror.cs.uchicago.edu/google-chrome/pool/main/g/google-chrome-stable/google-chrome-stable_114.0.5735.90-1_amd64.deb && \
    apt-get install -y ./google-chrome-stable_114.0.5735.90-1_amd64.deb && \
    rm google-chrome-stable_114.0.5735.90-1_amd64.deb

# Install matching ChromeDriver 114.0.5735.90
RUN wget https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip

# Verify installations
RUN google-chrome --version && chromedriver --version

# Set working dir for your app
WORKDIR /app
