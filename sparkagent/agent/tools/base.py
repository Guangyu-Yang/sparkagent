"""Base class for agent tools."""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Abstract base class for tools.

    Tools are capabilities the agent can use to interact with the environment.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool display name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what the tool does."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Return the JSON Schema for tool parameters."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool.

        Returns:
            String result of the execution.

        """
        pass

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
