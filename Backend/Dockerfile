FROM python:3.13 AS builder
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y portaudio19-dev
RUN pip install -r /app/requirements.txt

FROM python:3.13
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY . .
ENV PIP_ROOT_USER_ACTION=ignore
ENV TF_CPP_MIN_LOG_LEVEL=1
ENV PYTHONUNBUFFERED=1
ENV DONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["python3", "main.py"]