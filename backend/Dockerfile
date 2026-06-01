FROM python:3.10.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/planner/build
ENV ROUTE_PLANNER_BACKEND=cpp

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ cmake libmariadb-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY planner/ ./planner/
COPY tests/ ./tests/

RUN cmake -S planner -B planner/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build planner/build --config Release

RUN python -m pytest tests -v

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
