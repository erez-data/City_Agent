FROM python:3.10-slim

ENV TZ=Europe/Istanbul
RUN apt-get update && \
    apt-get install -y locales tzdata build-essential && \
    echo "tr_TR.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen && \
    ln -fs /usr/share/zoneinfo/Europe/Istanbul /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean

ENV LANG=tr_TR.UTF-8 \
    LANGUAGE=tr_TR:tr \
    LC_ALL=tr_TR.UTF-8

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH="${PYTHONPATH}:/app"

COPY . .

CMD ["python", "calendar_main.py"]
