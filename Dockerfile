FROM python:3.12.3-alpine
RUN apk add --no-cache mariadb-dev gcc musl-dev tzdata
WORKDIR /wordle
ENV APP_TIMEZONE=UTC
COPY ./requirements.txt /wordle/requirements.txt
RUN pip3 install --no-cache-dir --upgrade -r requirements.txt
COPY ./app.py /wordle/app.py
COPY ./bin/ /wordle/bin
CMD ["fastapi", "run", "app.py", "--proxy-headers", "--port", "80"]
