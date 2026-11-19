"""Unit tests for Click and Rich CLI."""

import pytest
from click.testing import CliRunner
from agent_intent_settlement.cli import main


class TestCLI:
    """Test suite for CLI subcommands."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_cli_version(self):
        res = self.runner.invoke(main, ["--version"])
        assert res.exit_code == 0
        assert "0.1.0" in res.output

    def test_cli_solve(self):
        res = self.runner.invoke(
            main,
            ["solve", "--asset", "ETHUSDT", "--price", "3000.0", "--intents", "10"],
        )
        assert res.exit_code == 0
        assert "Autonomous Agent Intent Clearing Engine" in res.output
        assert "Uniform Clearing Price" in res.output
        assert "Batch Auction Clearing Result" in res.output

    def test_cli_simulate(self):
        res = self.runner.invoke(
            main,
            ["simulate", "--asset", "SOLUSDT", "--epochs", "2", "--intents-per-epoch", "10"],
        )
        assert res.exit_code == 0
        assert "Multi-Epoch Discrete Auction Simulation" in res.output
        assert "Simulation Aggregate Economics" in res.output
        assert "Total Intents Generated" in res.output

    def test_cli_directive(self):
        res = self.runner.invoke(
            main,
            [
                "directive",
                "--asset", "ETHUSDT",
                "--action", "SHORT",
                "--price", "3000.0",
                "--atr", "45.0",
                "--size", "5.0 ETH",
                "--leverage", "2.0",
            ],
        )
        assert res.exit_code == 0
        assert "Strict Institutional VAULT Directive" in res.output
        assert "ETHUSDT | SELL" in res.output
        assert "VALID (PASS)" in res.output
