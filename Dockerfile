# AegisCode runtime image.
#
# Credentials are NEVER baked into this image. Inject the LLM API key at
# runtime with `-e` (see the CredentialStore env fallback), e.g.:
#   docker run -e <PROVIDER_KEY>=... -v "$PWD":/workspace -p 8000:8000 aegiscode
# The container runs: aegiscode serve --host 0.0.0.0
# and respects the PORT environment variable (default 8000).
FROM python:3.12-slim

WORKDIR /app

# Copy only what the editable install needs (package metadata + source).
COPY pyproject.toml ./
COPY aegiscode ./aegiscode
# Ship the four SPEC §16.4 mechanism demos so `aegiscode demo` runs in-container.
# The demos import ONLY the aegiscode package + stdlib (never tests/), so they
# work here even though .dockerignore excludes tests/.
COPY demos ./demos
# Include the demo project for public demo mode.
COPY examples ./examples

RUN pip install --no-cache-dir -e .

# Default port; Render injects PORT at runtime.
ENV PORT=8000
EXPOSE 8000

# Bind 0.0.0.0 for container networking; port from $PORT env var.
CMD ["aegiscode", "serve", "--host", "0.0.0.0"]
