"""Tests for shell tool."""

import pytest

from sparkagent.agent.tools.shell import ShellTool


class TestShellTool:
    """Tests for ShellTool."""

    def test_properties(self):
        tool = ShellTool()
        assert tool.name == "shell"
        assert "command" in tool.parameters["properties"]

    def test_init_defaults(self):
        tool = ShellTool()
        assert tool.working_dir is None
        assert tool.timeout == 60

    def test_init_custom(self):
        tool = ShellTool(working_dir="/tmp", timeout=30)
        assert tool.working_dir == "/tmp"
        assert tool.timeout == 30

    async def test_execute_simple_command(self):
        tool = ShellTool()
        result = await tool.execute(command="echo 'Hello World'")
        assert "Hello World" in result

    async def test_execute_with_working_dir(self, temp_dir):
        tool = ShellTool()
        result = await tool.execute(command="pwd", working_dir=str(temp_dir))
        assert str(temp_dir) in result

    async def test_execute_default_working_dir(self, temp_dir):
        tool = ShellTool(working_dir=str(temp_dir))
        result = await tool.execute(command="pwd")
        assert str(temp_dir) in result

    async def test_execute_captures_stderr(self):
        tool = ShellTool()
        result = await tool.execute(command="ls /nonexistent_directory_12345")
        assert "STDERR" in result or "Exit code" in result

    async def test_execute_returns_exit_code(self):
        tool = ShellTool()
        result = await tool.execute(command="exit 1")
        assert "Exit code: 1" in result

    async def test_execute_no_output(self):
        tool = ShellTool()
        result = await tool.execute(command="true")
        assert "no output" in result.lower()


class TestShellToolSafetyGuards:
    """Tests for shell tool safety guards."""

    async def test_blocks_rm_rf(self):
        tool = ShellTool()
        result = await tool.execute(command="rm -rf /")
        assert "blocked" in result.lower()
        assert "dangerous" in result.lower()

    async def test_blocks_rm_r(self):
        tool = ShellTool()
        result = await tool.execute(command="rm -r /tmp/test")
        assert "blocked" in result.lower()

    async def test_blocks_format(self):
        tool = ShellTool()
        result = await tool.execute(command="format C:")
        assert "blocked" in result.lower()

    async def test_blocks_mkfs(self):
        tool = ShellTool()
        result = await tool.execute(command="mkfs.ext4 /dev/sda1")
        assert "blocked" in result.lower()

    async def test_blocks_dd(self):
        tool = ShellTool()
        result = await tool.execute(command="dd if=/dev/zero of=/dev/sda")
        assert "blocked" in result.lower()

    async def test_blocks_shutdown(self):
        tool = ShellTool()
        result = await tool.execute(command="shutdown -h now")
        assert "blocked" in result.lower()

    async def test_blocks_reboot(self):
        tool = ShellTool()
        result = await tool.execute(command="reboot")
        assert "blocked" in result.lower()

    async def test_blocks_poweroff(self):
        tool = ShellTool()
        result = await tool.execute(command="poweroff")
        assert "blocked" in result.lower()

    async def test_allows_safe_commands(self):
        tool = ShellTool()

        # These should NOT be blocked
        result = await tool.execute(command="echo hello")
        assert "blocked" not in result.lower()

        result = await tool.execute(command="ls -la")
        assert "blocked" not in result.lower()

        result = await tool.execute(command="cat /etc/hosts")
        assert "blocked" not in result.lower()


class TestShellToolDangerousPatterns:
    """Tests for dangerous pattern detection."""

    def test_is_dangerous_rm_rf(self):
        tool = ShellTool()
        assert tool._is_dangerous("rm -rf /") is True
        assert tool._is_dangerous("rm -rf /tmp") is True
        assert tool._is_dangerous("rm -r /tmp") is True

    def test_is_dangerous_case_insensitive(self):
        tool = ShellTool()
        assert tool._is_dangerous("RM -RF /") is True
        assert tool._is_dangerous("SHUTDOWN") is True
        assert tool._is_dangerous("REBOOT") is True

    def test_is_dangerous_fork_bomb(self):
        tool = ShellTool()
        assert tool._is_dangerous(":(){ :|:& };:") is True

    def test_is_dangerous_safe_commands(self):
        tool = ShellTool()
        assert tool._is_dangerous("echo hello") is False
        assert tool._is_dangerous("ls -la") is False
        assert tool._is_dangerous("cat file.txt") is False
        assert tool._is_dangerous("python script.py") is False


class TestShellToolTimeout:
    """Tests for shell tool timeout handling."""

    async def test_timeout_kills_long_running_command(self):
        tool = ShellTool(timeout=1)
        result = await tool.execute(command="sleep 10")
        assert "timed out" in result.lower()

    async def test_fast_command_does_not_timeout(self):
        tool = ShellTool(timeout=10)
        result = await tool.execute(command="echo 'fast'")
        assert "timed out" not in result.lower()
        assert "fast" in result
