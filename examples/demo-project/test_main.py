"""Tests for main.py — used by AegisCode's feedback loop."""
from main import greet


def test_greet_returns_name():
    assert greet("Alice") == "Hello, Alice!"
