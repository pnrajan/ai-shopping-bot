FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHOPPER_HOST=0.0.0.0 \
    SHOPPER_PORT=8000

WORKDIR /app

RUN adduser --disabled-password --gecos "" shopper

COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY shopper ./shopper
COPY main.py ./

RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir --no-deps .

USER shopper
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c \
  "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["python", "main.py"]
