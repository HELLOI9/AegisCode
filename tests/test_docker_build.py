"""Config-level tests for the Dockerfile.

These parse the Dockerfile as text and do NOT require the docker daemon.
The key invariant: credentials are NEVER baked into the image; they are
injected at runtime via `-e OPENAI_API_KEY=...` and the workspace is mounted
via `-v host:/workspace`.
"""

import pathlib


def test_dockerfile_has_no_key_and_runtime_cmd():
    df = pathlib.Path("Dockerfile").read_text()
    # runtime entrypoint starts the server
    assert "aegiscode serve" in df
    # key never baked in
    assert "OPENAI_API_KEY" not in df
    # no secret-looking ENV baked in
    assert "ENV" not in df or "API_KEY" not in df


def test_dockerfile_base_image_and_expose():
    df = pathlib.Path("Dockerfile").read_text()
    # slim, pinned base image
    assert "FROM python:3.12-slim" in df
    # port is documented/exposed
    assert "EXPOSE 8000" in df
    # binds to all interfaces so the container is reachable
    assert "0.0.0.0" in df


def test_dockerfile_copies_no_secrets():
    df = pathlib.Path("Dockerfile").read_text()
    # never copy an env/credential file into the image
    assert "COPY .env" not in df
    assert ".env" not in df
    # no generic secret-ish ENV assignments
    lowered = df.lower()
    for token in ("secret", "token", "password", "api_key"):
        assert f"env {token}" not in lowered


def test_dockerignore_excludes_secrets_and_cruft():
    di = pathlib.Path(".dockerignore").read_text()
    for pattern in (".env", ".git", ".venv"):
        assert pattern in di
