FROM apache/airflow:3.3.0

WORKDIR /opt/oee

COPY --chown=airflow:root pyproject.toml uv.lock ./
COPY --chown=airflow:root \
    oee-ingestion/pyproject.toml \
    oee-ingestion/pyproject.toml

ENV VIRTUAL_ENV="/opt/oee/.venv"

RUN uv sync \
    --frozen \
    --extra orchestration \
    --no-dev \
    --no-install-project \
    --no-install-workspace

ENV PATH="/opt/oee/.venv/bin:${PATH}"
ENV PYTHONPATH="/opt/oee/oee-ingestion:/opt/oee/oee-ingestion/src:/opt/oee/oee-orchestration/src"
