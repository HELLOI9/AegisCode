from pydantic import BaseModel


class Action(BaseModel):
    tool: str
    arguments: dict = {}
    thought: str | None = None
    expectation: str | None = None
