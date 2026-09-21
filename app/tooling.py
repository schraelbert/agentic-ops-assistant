from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError


def validate_tool_args(spec: dict[str, Any], args: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Validate and normalize tool arguments with the tool's Pydantic schema.

    Tool schemas are optional so adapters can stay lightweight, but production-facing
    tools should define ``input_model``. Extra fields are rejected by the models used
    in the included domains.
    """
    model: type[BaseModel] | None = spec.get("input_model")
    if model is None:
        return args, None

    try:
        validated = model.model_validate(args)
    except ValidationError as exc:
        messages = []
        for error in exc.errors(include_url=False):
            location = ".".join(str(part) for part in error["loc"]) or "args"
            messages.append(f"{location}: {error['msg']}")
        return None, "Invalid tool arguments: " + "; ".join(messages)

    return validated.model_dump(), None
