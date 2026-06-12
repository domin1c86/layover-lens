from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError

from app.config import settings
from app.agents.tools.date_tool import DateInfoTool
from app.agents.tools.place_tool import PlaceSearchTool
from app.agents.tools.types import AgentTool, AgentToolError, AgentToolResult
from app.agents.tools.weather_tool import WeatherForecastTool


_TOOLS: dict[str, AgentTool] = {
    DateInfoTool.name: DateInfoTool(),
    WeatherForecastTool.name: WeatherForecastTool(),
    PlaceSearchTool.name: PlaceSearchTool(),
}


def list_agent_tools() -> list[dict]:
    if not settings.ai_agent_tools_enabled:
        return []
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in _TOOLS.values()
    ]


def execute_agent_tool(name: str, arguments: dict) -> AgentToolResult:
    if not settings.ai_agent_tools_enabled:
        raise AgentToolError("Agent tools are disabled.")
    tool = _TOOLS.get(name)
    if not tool:
        raise AgentToolError(f"Unknown agent tool: {name}")
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(tool.run, arguments)
        try:
            return future.result(timeout=settings.ai_agent_tool_timeout_seconds)
        except TimeoutError as exc:
            raise AgentToolError(f"Agent tool timed out: {name}") from exc
