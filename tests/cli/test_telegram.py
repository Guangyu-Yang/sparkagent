"""Tests for the Telegram plugin CLI commands."""

from unittest.mock import patch

from typer.testing import CliRunner

from sparkagent.cli.main import app

runner = CliRunner()


class TestTelegramSubcommand:
    """Tests for `sparkagent telegram` subcommand group."""

    def test_telegram_help_shows_onboard(self):
        result = runner.invoke(app, ["telegram", "--help"])
        assert result.exit_code == 0
        assert "onboard" in result.output

    def test_telegram_no_args_shows_help(self):
        result = runner.invoke(app, ["telegram"])
        # no_args_is_help causes exit code 0 in some Typer versions, 2 in others
        assert result.exit_code in (0, 2)
        assert "onboard" in result.output


class TestTelegramOnboard:
    """Tests for `sparkagent telegram onboard`."""

    def test_saves_token_and_user_id(self, tmp_path):
        config_path = tmp_path / "config.json"

        with (
            patch("sparkagent.cli.telegram.load_config") as mock_load,
            patch("sparkagent.cli.telegram.save_config") as mock_save,
            patch("sparkagent.cli.telegram.get_config_path", return_value=config_path),
        ):
            from sparkagent.config import Config

            config = Config()
            mock_load.return_value = config

            result = runner.invoke(
                app,
                ["telegram", "onboard"],
                input="fake-bot-token:ABC\n123456789\n",
            )

            assert result.exit_code == 0
            assert "Token saved" in result.output
            assert "123456789" in result.output

            # Verify config was updated
            saved_config = mock_save.call_args[0][0]
            assert saved_config.channels.telegram.enabled is True
            assert saved_config.channels.telegram.token == "fake-bot-token:ABC"
            assert saved_config.channels.telegram.allow_from == ["123456789"]

    def test_blank_user_id_allows_everyone(self, tmp_path):
        config_path = tmp_path / "config.json"

        with (
            patch("sparkagent.cli.telegram.load_config") as mock_load,
            patch("sparkagent.cli.telegram.save_config") as mock_save,
            patch("sparkagent.cli.telegram.get_config_path", return_value=config_path),
        ):
            from sparkagent.config import Config

            config = Config()
            mock_load.return_value = config

            result = runner.invoke(
                app,
                ["telegram", "onboard"],
                input="fake-bot-token:ABC\n\n",
            )

            assert result.exit_code == 0
            assert "allow everyone" in result.output

            saved_config = mock_save.call_args[0][0]
            assert saved_config.channels.telegram.allow_from == []

    def test_preserves_existing_provider_config(self, tmp_path):
        config_path = tmp_path / "config.json"

        with (
            patch("sparkagent.cli.telegram.load_config") as mock_load,
            patch("sparkagent.cli.telegram.save_config") as mock_save,
            patch("sparkagent.cli.telegram.get_config_path", return_value=config_path),
        ):
            from sparkagent.config import Config

            config = Config()
            config.agent.provider = "openai"
            config.agent.model = "gpt-4.1"
            config.providers.openai.api_key = "sk-existing-key"
            mock_load.return_value = config

            # Write a dummy file so config_path.exists() is True
            config_path.write_text("{}")

            result = runner.invoke(
                app,
                ["telegram", "onboard"],
                input="fake-bot-token:ABC\n\n",
            )

            assert result.exit_code == 0

            saved_config = mock_save.call_args[0][0]
            # Provider settings should be untouched
            assert saved_config.agent.provider == "openai"
            assert saved_config.agent.model == "gpt-4.1"
            assert saved_config.providers.openai.api_key == "sk-existing-key"
            # Telegram should be configured
            assert saved_config.channels.telegram.enabled is True

    def test_enables_telegram(self, tmp_path):
        config_path = tmp_path / "config.json"

        with (
            patch("sparkagent.cli.telegram.load_config") as mock_load,
            patch("sparkagent.cli.telegram.save_config") as mock_save,
            patch("sparkagent.cli.telegram.get_config_path", return_value=config_path),
        ):
            from sparkagent.config import Config

            config = Config()
            assert config.channels.telegram.enabled is False
            mock_load.return_value = config

            result = runner.invoke(
                app,
                ["telegram", "onboard"],
                input="fake-bot-token:ABC\n\n",
            )

            assert result.exit_code == 0
            saved_config = mock_save.call_args[0][0]
            assert saved_config.channels.telegram.enabled is True

    def test_shows_gateway_instructions(self, tmp_path):
        config_path = tmp_path / "config.json"

        with (
            patch("sparkagent.cli.telegram.load_config") as mock_load,
            patch("sparkagent.cli.telegram.save_config"),
            patch("sparkagent.cli.telegram.get_config_path", return_value=config_path),
        ):
            from sparkagent.config import Config

            mock_load.return_value = Config()

            result = runner.invoke(
                app,
                ["telegram", "onboard"],
                input="fake-bot-token:ABC\n\n",
            )

            assert result.exit_code == 0
            assert "sparkagent gateway" in result.output

    def test_token_is_stripped(self, tmp_path):
        config_path = tmp_path / "config.json"

        with (
            patch("sparkagent.cli.telegram.load_config") as mock_load,
            patch("sparkagent.cli.telegram.save_config") as mock_save,
            patch("sparkagent.cli.telegram.get_config_path", return_value=config_path),
        ):
            from sparkagent.config import Config

            mock_load.return_value = Config()

            result = runner.invoke(
                app,
                ["telegram", "onboard"],
                input="  fake-bot-token:ABC  \n\n",
            )

            assert result.exit_code == 0
            saved_config = mock_save.call_args[0][0]
            assert saved_config.channels.telegram.token == "fake-bot-token:ABC"

    def test_user_id_is_stripped(self, tmp_path):
        config_path = tmp_path / "config.json"

        with (
            patch("sparkagent.cli.telegram.load_config") as mock_load,
            patch("sparkagent.cli.telegram.save_config") as mock_save,
            patch("sparkagent.cli.telegram.get_config_path", return_value=config_path),
        ):
            from sparkagent.config import Config

            mock_load.return_value = Config()

            result = runner.invoke(
                app,
                ["telegram", "onboard"],
                input="fake-bot-token:ABC\n  123456789  \n",
            )

            assert result.exit_code == 0
            saved_config = mock_save.call_args[0][0]
            assert saved_config.channels.telegram.allow_from == ["123456789"]
