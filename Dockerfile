# AegisCode runtime image.
#
# Credentials are NEVER baked into this image. Inject the LLM API key at
# runtime with `-e` (see the CredentialStore env fallback), e.g.:
#   docker run -e <PROVIDER_KEY>=... -v "$PWD":/workspace -p 8000:8000 aegiscode
# The container runs: aegiscode serve --host 0.0.0.0 --port 8000
# and the host workspace is mounted at /workspace.
FROM python:3.12-slim

WORKDIR /app

# Copy only what the editable install needs (package metadata + source).
COPY pyproject.toml ./
COPY aegiscode ./aegiscode

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["aegiscode", "serve", "--host", "0.0.0.0", "--port", "8000"]
