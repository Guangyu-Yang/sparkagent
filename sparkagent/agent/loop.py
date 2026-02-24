"""Agent loop - the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any

from sparkagent.agent.codeact import CodeActExecutor, CodeActParser
from sparkagent.agent.context import ContextBuilder
from sparkagent.agent.mode_selector import select_execution_mode
from sparkagent.agent.tools import (
    EditFileTool,
    ListDirectoryTool,
    ReadFileTool,
    ShellTool,
    ToolRegistry,
    WebFetchTool,
    WebSearchTool,
    WriteFileTool,
)
from sparkagent.bus import InboundMessage, MessageBus, OutboundMessage
from sparkagent.config.schema import MemoryConfig
from sparkagent.memory.designer import SkillDesigner
from sparkagent.memory.executor import execute_memory_skills
from sparkagent.memory.models import MemoryOperation, OperationType
from sparkagent.memory.selector import select_skills
from sparkagent.memory.skill_bank import SkillBank
from sparkagent.memory.store import MemoryStore
from sparkagent.providers import LLMProvider
from sparkagent.session import SessionManager


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
        execution_mode: str = "function_calling",
        memory_config: MemoryConfig | None = None,
    ):
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.execution_mode = execution_mode

        # Memory system (opt-in)
        self._memory_config = memory_config
        self._memory_store: MemoryStore | None = None
        self._skill_bank: SkillBank | None = None
        self._skill_designer: SkillDesigner | None = None

        if memory_config and memory_config.enabled:
            self._memory_store = MemoryStore()
            self._skill_bank = SkillBank()
            self._skill_designer = SkillDesigner(
                self._skill_bank,
                hard_case_threshold=memory_config.hard_case_threshold,
            )

        self.context = ContextBuilder(workspace, memory_store=self._memory_store)
        self.sessions = SessionManager()
        self.tools = ToolRegistry()

        self._running = False
        self._codeact_parser = CodeActParser()
        self._codeact_executors: dict[str, CodeActExecutor] = {}
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

    async def _resolve_execution_mode(self, message: str) -> str:
        """Resolve the execution mode, consulting the LLM when set to 'auto'."""
        if self.execution_mode != "auto":
            return self.execution_mode
        return await select_execution_mode(self.provider, self.model, message)

    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """Process a single inbound message, dispatching to the active execution mode."""
        print(f"Processing message from {msg.channel}:{msg.sender_id}")

        session = self.sessions.get_or_create(msg.session_key)

        mode = await self._resolve_execution_mode(msg.content)
        print(f"  Execution mode: {mode}")

        if mode == "code_act":
            final_content = await self._process_message_codeact(msg, session)
        else:
            final_content = await self._process_message_function_calling(msg, session)

        if final_content is None:
            final_content = "I've completed processing but have no response."

        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        # Process memory (non-blocking, errors don't affect the response)
        if self._memory_config and self._memory_config.enabled:
            try:
                await self._process_memory(msg.content, final_content, msg.session_key)
            except Exception as e:
                print(f"  Memory processing error (non-fatal): {e}")

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
        )

    # ------------------------------------------------------------------
    # Function-calling mode (original behaviour)
    # ------------------------------------------------------------------

    async def _process_message_function_calling(
        self, msg: InboundMessage, session: Any
    ) -> str | None:
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
        )

        iteration = 0
        final_content = None

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_schemas(),
                model=self.model,
            )

            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )

                for tool_call in response.tool_calls:
                    print(f"  Executing tool: {tool_call.name}")
                    result = await self.tools.execute(
                        tool_call.name, tool_call.arguments
                    )
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break

        return final_content

    # ------------------------------------------------------------------
    # CodeAct mode
    # ------------------------------------------------------------------

    def _get_codeact_executor(self, session_key: str) -> CodeActExecutor:
        """Return (or create) a per-session CodeActExecutor."""
        if session_key not in self._codeact_executors:
            self._codeact_executors[session_key] = CodeActExecutor(self.tools)
        return self._codeact_executors[session_key]

    async def _process_message_codeact(
        self, msg: InboundMessage, session: Any
    ) -> str | None:
        executor = self._get_codeact_executor(msg.session_key)

        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            execution_mode="code_act",
            tool_schemas=self.tools.get_schemas(),
        )

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # No tool schemas sent — the LLM generates code instead
            response = await self.provider.chat(
                messages=messages,
                tools=None,
                model=self.model,
            )

            text = response.content or ""

            if self._codeact_parser.has_code(text):
                # Add assistant reply to context
                messages.append({"role": "assistant", "content": text})

                code = self._codeact_parser.extract_code(text)
                print(f"  Executing CodeAct block ({len(code)} chars)")
                observation = executor.execute(code)

                # Feed observation back for the next iteration
                messages.append({
                    "role": "user",
                    "content": f"[Observation]\n{observation}\n[/Observation]",
                })
            else:
                # No code — this is the final answer
                return self._codeact_parser.extract_text_response(text) or text

        return None

    # ------------------------------------------------------------------
    # Memory processing
    # ------------------------------------------------------------------

    async def _process_memory(
        self, user_message: str, assistant_response: str, session_key: str
    ) -> None:
        """Run the memory skill pipeline after a conversation turn."""
        if not (self._memory_store and self._skill_bank and self._memory_config):
            return

        turn = f"User: {user_message}\nAssistant: {assistant_response}"
        memories_text = self._memory_store.retrieve_for_context(
            user_message,
            max_entries=self._memory_config.max_memories_in_context,
            max_chars=self._memory_config.max_memory_chars,
        )
        relevant = self._memory_store.retrieve(
            user_message, max_results=self._memory_config.max_memories_in_context
        )

        skill_ids = await select_skills(
            self.provider,
            self.model,
            turn,
            memories_text,
            self._skill_bank.get_descriptions(),
            top_k=self._memory_config.top_k_skills,
        )
        selected = [s for s in (self._skill_bank.get(sid) for sid in skill_ids) if s]
        if not selected:
            return

        operations = await execute_memory_skills(
            self.provider, self.model, turn, relevant, selected
        )
        for op in operations:
            self._apply_operation(op, session_key)
            for skill in selected:
                self._skill_bank.record_usage(skill.id, success=True)

        if (
            self._memory_config.auto_evolve
            and self._skill_designer
            and self._skill_designer.should_evolve()
        ):
            await self._skill_designer.evolve_skills(self.provider, self.model)
            self._skill_designer.check_rollbacks()

    def _apply_operation(self, op: MemoryOperation, session_key: str) -> None:
        """Apply a single memory operation to the store."""
        if not self._memory_store:
            return

        if op.type == OperationType.INSERT and op.content:
            self._memory_store.insert(
                content=op.content,
                tags=op.tags,
                source_session=session_key,
                source_skill=op.skill_id,
            )
        elif op.type == OperationType.UPDATE and op.target_id:
            self._memory_store.update(
                entry_id=op.target_id,
                content=op.content or None,
                tags=op.tags or None,
            )
        elif op.type == OperationType.DELETE and op.target_id:
            self._memory_store.delete(op.target_id)

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
