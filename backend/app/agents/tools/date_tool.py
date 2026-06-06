from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.agents.tools.types import AgentToolResult


class DateInfoTool:
    name = "date_info"
    description = "Return current date, weekday, and distance from today for a requested travel date."
    input_schema = {
        "type": "object",
        "properties": {
            "travel_date": {"type": "string", "description": "ISO date such as 2026-06-05"},
            "timezone": {"type": "string", "description": "IANA timezone, default Asia/Shanghai"},
        },
    }

    def run(self, arguments: dict) -> AgentToolResult:
        timezone_name = str(arguments.get("timezone") or "Asia/Shanghai")
        try:
            today = datetime.now(ZoneInfo(timezone_name)).date()
        except Exception:
            timezone_name = "Asia/Shanghai"
            today = datetime.now(ZoneInfo(timezone_name)).date()
        travel_date_text = arguments.get("travel_date")
        target = _parse_date(str(travel_date_text)) if travel_date_text else today
        delta_days = (target - today).days
        weekday = target.strftime("%A")
        if delta_days == 0:
            relation = "today"
        elif delta_days == 1:
            relation = "tomorrow"
        elif delta_days > 1:
            relation = f"in {delta_days} days"
        else:
            relation = f"{abs(delta_days)} days ago"
        return AgentToolResult(
            name=self.name,
            status="success",
            content=f"{target.isoformat()} is {weekday}, {relation}. Current date is {today.isoformat()} ({timezone_name}).",
            data={
                "today": today.isoformat(),
                "travel_date": target.isoformat(),
                "weekday": weekday,
                "delta_days": delta_days,
                "timezone": timezone_name,
            },
        )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return datetime.now(ZoneInfo("Asia/Shanghai")).date()
