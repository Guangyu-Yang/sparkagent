"""Agent loop - the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any

from myautoagent.bus import MessageBus, InboundMessage, OutboundMessage
from myautoagent.providers import LLMProvider
from myautoagent.session import SessionManager
from myautoagent.agent.context import ContextBuilder
from myautoagent.agent.tools import (
    ToolRegistry,
    ReadFileTool,
    WriteFileTool,
    ListDirectoryTool,
    EditFileTool,
    ShellTool,
    WebSearchTool,
    WebFetchTool,
)


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history and system prompt
    3. Calls the LLM
    4. Executes tool calls in a loop
    5. Returns the final response
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
    ):
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        
        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager()
        self.tools = ToolRegistry()
        
        self._running = False
        self._register_tools(brave_api_key)
    
    def _register_tools(self, brave_api_key: str | None = None) -> None:
        """Register the default tools."""
        # File tools
        self.tools.register(ReadFileTool())
        self.tools.register(WriteFileTool())
        self.tools.register(ListDirectoryTool())
        self.tools.register(EditFileTool())
        
        # Shell tool
        self.tools.register(ShellTool(working_dir=str(self.workspace)))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=brave_api_key))
        self.tools.register(WebFetchTool())
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        print("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message with timeout
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    print(f"Error processing message: {e}")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        print("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """Process a single inbound message."""
        print(f"Processing message from {msg.channel}:{msg.sender_id}")
        
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Build initial messages
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
        )
        
        # Agent loop - iterate until we get a text response
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_schemas(),
                model=self.model,
            )
            
            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # Execute each tool
                for tool_call in response.tool_calls:
                    print(f"  Executing tool: {tool_call.name}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # No tool calls - we have our final response
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response."
        
        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
        )
    
    async def process_direct(self, content: str, session_key: str = "cli:direct") -> str:
        """
        Process a message directly (for CLI usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="direct",
            content=content,
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""
