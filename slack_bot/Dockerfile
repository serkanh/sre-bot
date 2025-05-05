FROM python:3.11


ENV PYTHONPATH=/app/ \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/usr/local/bin:${PATH}"

WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt

CMD ["uvicorn", "main:fast_api", "--host", "0.0.0.0", "--port", "80"]
