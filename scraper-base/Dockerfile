# Optimized for Chrome-dependent services (elife_scraper, wt_scraper)
FROM python:3.10-slim

# Set timezone and locales
ENV TZ=Europe/Istanbul
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

# Set environment variables
ENV LANG=tr_TR.UTF-8 \
    LANGUAGE=tr_TR:tr \
    LC_ALL=tr_TR.UTF-8 \
    PYTHONPATH=/app:/app/utils

# Install Chrome (v115.0.5790.114 - newer stable version)
ENV CHROME_VERSION="115.0.5790.114-1"
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable=${CHROME_VERSION} && \
    rm -rf /var/lib/apt/lists/*

# Install matching Chromedriver
ENV CHROMEDRIVER_VERSION="115.0.5790.114"
RUN wget -q https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip

# Verify installations
RUN google-chrome --version && chromedriver --version