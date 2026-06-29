"""Tests for CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from machine_sim.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "After Silicon" in result.output


def test_cli_run(runner):
    with runner.isolated_filesystem():
        Path("configs").mkdir(exist_ok=True)
        Path("configs/milestone_1.toml").write_text(
            "[simulation]\ngrid_width = 5\ngrid_height = 5\n"
            "unit_count = 2\nmax_ticks = 10\nseed = 42\n"
            "resource_density = 0.3\nhazard_density = 0.05\n"
            "power_drain_rate = 1.0\n"
        )
        result = runner.invoke(cli, ["run", "-c", "configs/milestone_1.toml"])
        assert result.exit_code == 0
        assert "Simulation complete" in result.output


def test_cli_check(runner):
    result = runner.invoke(cli, ["check"])
    assert result.exit_code == 0
    assert "All guardrail checks passed" in result.output
