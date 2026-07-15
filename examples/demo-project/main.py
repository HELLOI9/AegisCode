"""A tiny sample project for AegisCode public demo.

This module has an intentional bug that the agent can fix,
demonstrating the governance + feedback loop.
"""


def greet(name: str) -> str:
    """Return a greeting. BUG: missing f-string prefix."""
    return "Hello, {name}!"  # Bug: should be f"Hello, {name}!"


if __name__ == "__main__":
    print(greet("World"))
