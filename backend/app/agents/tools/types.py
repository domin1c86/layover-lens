from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class AgentToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentToolResult:
    name: str
    status: str
    content: str
    data: dict = field(default_factory=dict)


class AgentTool(Protocol):
    name: str
    description: str
    input_schema: dict

    def run(self, arguments: dict) -> AgentToolResult:
        ...
