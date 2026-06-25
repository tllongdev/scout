FROM python:3.12-slim

# Install uv for fast, reproducible dependency resolution.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy project metadata and source, then install in one step.
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

# Mission output is mounted as a volume so results land on the host.
RUN mkdir -p /app/output

ENTRYPOINT ["scout"]
