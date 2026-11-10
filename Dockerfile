FROM python:3.14-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir .

FROM python:3.14-slim
# git is needed for `review` and `review --base`. The mounted repo belongs to the host
# user, so git must be told to trust it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*' \
    && useradd --create-home observer
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONWARNINGS=ignore::DeprecationWarning
USER observer
WORKDIR /repo
ENTRYPOINT ["pr-observer"]
CMD ["review"]
