"""InputProvider protocol and adapters for collecting credentials from users."""

from __future__ import annotations

import getpass
from typing import Any, Protocol

from pydantic import BaseModel


class InputField(BaseModel):
    """A single field to collect from the user."""

    name: str
    label: str
    secret: bool = True
    default: str | None = None


class InputProvider(Protocol):
    """Collect a set of named values from the user."""

    def collect(self, fields: list[InputField]) -> dict[str, str]: ...


class BridgeInputProvider:
    """Collect inputs via a local browser form (secure_input_bridge)."""

    def __init__(self, title: str, static_fields: list[dict[str, Any]] | None = None) -> None:
        self._title = title
        self._static_fields: list[dict[str, Any]] = static_fields or []

    def collect(self, fields: list[InputField]) -> dict[str, str]:
        from authsome.auth.flows.bridge import secure_input_bridge

        bridge_fields: list[dict[str, Any]] = list(self._static_fields)
        for field in fields:
            bridge_fields.append(
                {
                    "name": field.name,
                    "label": field.label,
                    "type": "password" if field.secret else "text",
                    "required": field.default is None,
                    "value": field.default or "",
                }
            )
        result = secure_input_bridge(self._title, bridge_fields)
        for field in fields:
            if field.name not in result and field.default is not None:
                result[field.name] = field.default
        return result


class InteractiveInputProvider:
    """Collect inputs from the terminal (getpass for secret fields, input() otherwise)."""

    def collect(self, fields: list[InputField]) -> dict[str, str]:
        result: dict[str, str] = {}
        for field in fields:
            prompt = field.label
            if field.default:
                prompt += f" [{field.default}]"
            prompt += ": "
            if field.secret:
                value = getpass.getpass(prompt)
            else:
                value = input(prompt)
            result[field.name] = value.strip() or (field.default or "")
        return result


class MockInputProvider:
    """Return a pre-filled dict — for testing."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def collect(self, fields: list[InputField]) -> dict[str, str]:
        result: dict[str, str] = {}
        for field in fields:
            if field.name in self._values:
                result[field.name] = self._values[field.name]
            elif field.default is not None:
                result[field.name] = field.default
        return result
