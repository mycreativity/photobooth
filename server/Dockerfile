FROM python:3.12-slim

WORKDIR /app

# Copy everything
COPY pyproject.toml .
COPY src/ src/

# Install in editable mode for dev (volume-mounted source overrides)
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -e .

# Create data directory
RUN mkdir -p /data/photos

EXPOSE 8000

CMD ["python", "-m", "server"]
