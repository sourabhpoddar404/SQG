FROM python:3.8.8

WORKDIR /usr/src/app

COPY requirements.txt ./

# config
RUN mkdir -p /var/www \
    && apt-get update \
    && apt-get install -y \
        build-essential \
        python-dev \
        git \
        python3-pip \
    && pip3 install -U pip

RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python3", "./sqg_webserver.py" ]