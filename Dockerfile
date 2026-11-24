FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY currency currency
COPY templates templates
COPY static static
COPY server.py .
RUN mkdir -p data

ENV HOST=0.0.0.0
EXPOSE 8008
CMD ["python", "server.py"]
