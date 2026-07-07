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


def test_cli_long_run_adaptation(runner):
    """Long-run adaptation mode writes required artifacts without events.json."""
    with runner.isolated_filesystem():
        Path("configs").mkdir(exist_ok=True)
        Path("configs/m14_test.toml").write_text(
            "[simulation]\ngrid_width = 15\ngrid_height = 15\n"
            "unit_count = 3\nmax_ticks = 20\nseed = 42\n"
            "resource_density = 0.3\nhazard_density = 0.05\n"
            "power_drain_rate = 0.5\nsignal_enabled = true\n"
            "signal_pattern_count = 4\nsignal_energy_cost = 1.0\n"
            "signal_default_radius = 10\nsignal_default_decay = 0.01\n"
            "signal_default_duration = 40\nsignal_observation_window = 20\n"
            "adaptive_enabled = true\nfabrication_enabled = true\n"
            "capsule_enabled = false\nfabrication_interval = 5\n"
            "fabrication_power_cost = 5.0\nfabrication_material_cost = 1.0\n"
            "fabrication_variation = 0.08\nunit_capacity = 10\n"
            "telemetry_enabled = true\nreconciliation_enabled = false\n"
            "lineage_drift_enabled = false\npressure_analysis_enabled = false\n"
            "signal_dynamics_enabled = false\ntrace_compression_enabled = false\n"
            "trace_drift_enabled = false\nsummary_consistency_enabled = false\n"
            "long_run_adaptation_enabled = true\n"
        )
        result = runner.invoke(cli, [
            "run", "-c", "configs/m14_test.toml", "-o", "output/test_lr"
        ])
        assert result.exit_code == 0
        outpath = Path("output/test_lr")
        assert (outpath / "long_run_adaptation_summary.json").exists()
        assert (outpath / "action_distribution_trace.jsonl").exists()
        assert not (outpath / "events.json").exists()
        assert not (outpath / "state.json").exists()


def test_cli_inspect_long_run(runner):
    """Inspect works on long-run output (no events.json)."""
    with runner.isolated_filesystem():
        Path("output/test_lr").mkdir(parents=True, exist_ok=True)
        Path("output/test_lr/long_run_adaptation_summary.json").write_text("{}")
        result = runner.invoke(cli, ["inspect", "output/test_lr"])
        assert result.exit_code == 0
        assert "long-run mode" in result.output or "events.json not present" in result.output
