from typing import Any, Protocol, List, Dict
from dataclasses import dataclass

@dataclass
class AgentResult:
    """Standard output from an agent execution."""
    output: str
    artifacts: List[str]  # Paths to generated files
    cost: float
    metadata: Dict[str, Any]

class Tool(Protocol):
    """Protocol for tools that agents can use."""
    name: str
    description: str

    def execute(self, **kwargs) -> Any:
        ...

class AgentProtocol(Protocol):
    """Protocol that all external agents must implement to run on Quration."""
    name: str

    def run(self, input_text: str, tools: List[Tool]) -> AgentResult:
        """
        Run the agent with the given input and access to specific tools.

        Args:
            input_text: The user's query or instruction.
            tools: List of Quration-provided tools (e.g., GEOFetcher).

        Returns:
            The result of the agent's execution.
        """
        ...
