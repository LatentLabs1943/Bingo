FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bingo ./bingo
COPY web ./web
RUN useradd --create-home bingo && mkdir -p /app/data && chown bingo:bingo /app/data
USER bingo
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "bingo.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
