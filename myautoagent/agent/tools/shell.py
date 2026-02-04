"""Shell execution tool."""

import asyncio
import re
from typing import Any

from myautoagent.agent.tools.base import Tool


class ShellTool(Tool):
    """Execute shell commands."""
    
    # Patterns for potentially dangerous commands
    DANGEROUS_PATTERNS = [
        r"\brm\s+-[rf]{1,2}\b",        # rm -r, rm -rf
        r"\b(format|mkfs|diskpart)\b",  # disk operations
        r"\bdd\s+if=",                  # dd
        r">\s*/dev/sd",                 # write to disk
        r"\b(shutdown|reboot|poweroff)\b",
        r":\(\)\s*\{.*\};\s*:",         # fork bomb
    ]
    
    def __init__(self, working_dir: str | None = None, timeout: int = 60):
        self.working_dir = working_dir
        self.timeout = timeout
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return "Execute a shell command and return its output."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for the command (optional)"
                }
            },
            "required": ["command"]
        }
    
    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir
        
        # Safety check
        if self._is_dangerous(command):
            return "Error: Command blocked by safety guard (potentially dangerous)"
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self.timeout}s"
            
            output_parts = []
            
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace").strip()
                if stderr_text:
                    output_parts.append(f"STDERR:\n{stderr_text}")
            
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")
            
            result = "\n".join(output_parts) if output_parts else "(no output)"
            
            # Truncate long output
            if len(result) > 10000:
                result = result[:10000] + f"\n... (truncated)"
            
            return result
            
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    def _is_dangerous(self, command: str) -> bool:
        """Check if command matches dangerous patterns."""
        lower = command.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, lower):
                return True
        return False
