"""Tests for the run lifecycle manifest, control channel, and status surface."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from machine_sim.analysis import run_status
from machine_sim.cli.main import cli
from machine_sim.sim import checkpoint as ck
from machine_sim.sim import run_control as rc
from machine_sim.tests.test_checkpoint import build_engine, make_config


def build_controller(tmp_path, ticks: int = 0, **config_overrides) -> rc.RunController:
    config = make_config(**config_overrides)
    engine = build_engine(config, ticks=0)
    controller = rc.RunController(engine, tmp_path)
    controller.start()
    if ticks:
        controller.advance(ticks)
    return controller


class TestRunManifest:
    def test_create_writes_an_initialized_manifest(self, tmp_path):
        manifest = rc.RunManifest.create(tmp_path, make_config())
        assert manifest.path.exists()
        assert manifest.run_state == rc.RUN_STATE_INITIALIZED
        assert manifest.data["manifest_schema_version"] == rc.MANIFEST_SCHEMA_VERSION
        assert manifest.data["progress_ratio"] == 0.0

    def test_run_id_is_deterministic_for_equal_configurations(self, tmp_path):
        first = rc.RunManifest.create(tmp_path / "a", make_config())
        second = rc.RunManifest.create(tmp_path / "b", make_config())
        assert first.run_id == second.run_id

    def test_run_id_changes_with_the_seed(self, tmp_path):
        first = rc.RunManifest.create(tmp_path / "a", make_config())
        second = rc.RunManifest.create(tmp_path / "b", make_config(seed=99))
        assert first.run_id != second.run_id

    def test_reload_round_trip(self, tmp_path):
        manifest = rc.RunManifest.create(tmp_path, make_config())
        manifest.transition(rc.RUN_STATE_RUNNING)
        manifest.set_progress(17, "abc")
        manifest.save()
        reloaded = rc.RunManifest.load(tmp_path)
        assert reloaded.run_state == rc.RUN_STATE_RUNNING
        assert reloaded.data["completed_ticks"] == 17
        assert reloaded.data["run_digest"] == "abc"

    def test_write_is_atomic_and_leaves_no_partial_file(self, tmp_path):
        manifest = rc.RunManifest.create(tmp_path, make_config())
        manifest.save()
        assert not list(tmp_path.glob("*.partial"))

    def test_load_requires_a_manifest(self, tmp_path):
        with pytest.raises(rc.RunControlViolation):
            rc.RunManifest.load(tmp_path)

    def test_load_rejects_unsupported_schema_version(self, tmp_path):
        (tmp_path / rc.MANIFEST_NAME).write_text(
            json.dumps({"manifest_schema_version": "0.0.1"}), encoding="utf-8"
        )
        with pytest.raises(rc.RunControlViolation):
            rc.RunManifest.load(tmp_path)

    @pytest.mark.parametrize(
        "sequence",
        [
            (rc.RUN_STATE_RUNNING,),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_PAUSED),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_PAUSED, rc.RUN_STATE_RUNNING),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_PAUSED, rc.RUN_STATE_STOPPED),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_COMPLETED),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_STOPPED),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_FAILED),
        ],
    )
    def test_legal_transitions_are_accepted(self, tmp_path, sequence):
        manifest = rc.RunManifest.create(tmp_path, make_config())
        for state in sequence:
            manifest.transition(state)
        assert manifest.run_state == sequence[-1]

    @pytest.mark.parametrize(
        "sequence",
        [
            (rc.RUN_STATE_PAUSED,),
            (rc.RUN_STATE_COMPLETED,),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_COMPLETED, rc.RUN_STATE_RUNNING),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_STOPPED, rc.RUN_STATE_RUNNING),
            (rc.RUN_STATE_RUNNING, rc.RUN_STATE_PAUSED, rc.RUN_STATE_COMPLETED),
        ],
    )
    def test_illegal_transitions_are_rejected(self, tmp_path, sequence):
        manifest = rc.RunManifest.create(tmp_path, make_config())
        with pytest.raises(rc.RunControlViolation):
            for state in sequence:
                manifest.transition(state)

    def test_unrecognized_state_is_rejected(self, tmp_path):
        manifest = rc.RunManifest.create(tmp_path, make_config())
        with pytest.raises(rc.RunControlViolation):
            manifest.transition("halted")

    def test_progress_must_not_decrease(self, tmp_path):
        manifest = rc.RunManifest.create(tmp_path, make_config())
        manifest.set_progress(10)
        with pytest.raises(rc.RunControlViolation):
            manifest.set_progress(9)

    def test_progress_ratio_is_bounded(self, tmp_path):
        manifest = rc.RunManifest.create(tmp_path, make_config(max_ticks=10))
        manifest.set_progress(50)
        assert manifest.data["progress_ratio"] == 1.0


class TestControlChannel:
    def test_write_and_read_round_trip(self, tmp_path):
        channel = rc.ControlChannel(tmp_path)
        written = channel.write_request("pause", "req-1")
        read_back = channel.read_request()
        assert read_back["request_id"] == written["request_id"]
        assert read_back["requested_state"] == "pause"

    def test_unrecognized_request_is_rejected(self, tmp_path):
        with pytest.raises(rc.RunControlViolation):
            rc.ControlChannel(tmp_path).write_request("restart")

    def test_absent_request_reads_as_none(self, tmp_path):
        assert rc.ControlChannel(tmp_path).read_request() is None

    def test_unparseable_request_reads_as_none(self, tmp_path):
        channel = rc.ControlChannel(tmp_path)
        channel.directory.mkdir(parents=True, exist_ok=True)
        channel.request_path.write_text("{broken", encoding="utf-8")
        assert channel.read_request() is None

    def test_request_with_unrecognized_state_reads_as_none(self, tmp_path):
        channel = rc.ControlChannel(tmp_path)
        channel.directory.mkdir(parents=True, exist_ok=True)
        channel.request_path.write_text(
            json.dumps({"request_id": "x", "requested_state": "halt"}), encoding="utf-8"
        )
        assert channel.read_request() is None

    def test_clear_request_removes_the_file(self, tmp_path):
        channel = rc.ControlChannel(tmp_path)
        channel.write_request("stop", "req-2")
        channel.clear_request()
        assert not channel.request_path.exists()
        channel.clear_request()

    def test_history_is_append_only(self, tmp_path):
        channel = rc.ControlChannel(tmp_path)
        channel.append_history({"request_id": "a", "requested_state": "pause"})
        channel.append_history({"request_id": "b", "requested_state": "stop"})
        assert channel.applied_request_ids() == ["a", "b"]


class TestDigestChain:
    def test_initial_digest_depends_on_the_run_id(self):
        assert rc.initial_run_digest("run-a") != rc.initial_run_digest("run-b")

    def test_chain_advances_deterministically(self):
        first = rc.advance_run_digest("seed", "observation")
        second = rc.advance_run_digest("seed", "observation")
        assert first == second
        assert rc.advance_run_digest("seed", "other") != first

    def test_tick_observation_reflects_live_state(self):
        engine = build_engine(ticks=3)
        before = rc.tick_observation(engine)
        engine.units[0].power_reserve -= 5.0
        assert rc.tick_observation(engine) != before

    def test_controller_advances_the_chain(self, tmp_path):
        controller = build_controller(tmp_path, ticks=10)
        assert controller.run_digest
        assert controller.run_digest != rc.initial_run_digest(controller.manifest.run_id)

    def test_chain_survives_a_checkpoint_restore(self, tmp_path):
        controller = build_controller(tmp_path, ticks=10)
        path = controller.create_checkpoint()
        restored, _ = ck.restore_from_checkpoint(path)
        assert restored.run_digest_value == controller.run_digest


class TestRunController:
    def test_start_marks_the_run_running(self, tmp_path):
        controller = build_controller(tmp_path)
        assert controller.manifest.run_state == rc.RUN_STATE_RUNNING

    def test_advance_to_target_completes_the_run(self, tmp_path):
        controller = build_controller(tmp_path)
        assert controller.advance(20) == rc.RUN_STATE_COMPLETED
        assert controller.engine.tick_count == 20
        assert controller.manifest.run_state == rc.RUN_STATE_COMPLETED

    def test_advance_requires_a_running_state(self, tmp_path):
        controller = build_controller(tmp_path)
        controller.advance(10)
        with pytest.raises(rc.RunControlViolation):
            controller.advance(20)

    def test_checkpoints_are_written_on_the_configured_interval(self, tmp_path):
        controller = build_controller(tmp_path, ticks=30)
        assert len(ck.list_checkpoints(tmp_path)) == 3

    def test_retention_limit_is_honored_during_a_run(self, tmp_path):
        controller = build_controller(tmp_path, ticks=50, checkpoint_retention_limit=2)
        assert len(ck.list_checkpoints(tmp_path)) == 2
        assert controller.pruned_checkpoints

    def test_progress_trace_is_written(self, tmp_path):
        controller = build_controller(tmp_path, ticks=20)
        records = [
            json.loads(line)
            for line in controller.progress_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert records
        assert all(record["run_digest"] for record in records)
        assert [r["tick"] for r in records] == sorted(r["tick"] for r in records)

    def test_pause_request_is_applied_at_a_poll_boundary(self, tmp_path):
        controller = build_controller(tmp_path)
        controller.channel.write_request("pause", "req-pause")
        assert controller.advance(40) == rc.RUN_STATE_PAUSED
        assert controller.manifest.run_state == rc.RUN_STATE_PAUSED
        assert controller.engine.tick_count == controller.control_poll_interval
        assert ck.list_checkpoints(tmp_path)

    def test_stop_request_is_applied(self, tmp_path):
        controller = build_controller(tmp_path)
        controller.channel.write_request("stop", "req-stop")
        assert controller.advance(40) == rc.RUN_STATE_STOPPED
        assert controller.manifest.run_state == rc.RUN_STATE_STOPPED

    def test_applied_request_is_recorded_once(self, tmp_path):
        controller = build_controller(tmp_path)
        controller.channel.write_request("pause", "req-pause")
        controller.advance(40)
        assert controller.channel.applied_request_ids() == ["req-pause"]
        assert len(controller.manifest.data["control_records"]) == 1

    def test_duplicate_request_is_not_reapplied(self, tmp_path):
        controller = build_controller(tmp_path)
        controller.channel.write_request("pause", "req-pause")
        controller.advance(40)
        controller.manifest.transition(rc.RUN_STATE_RUNNING)
        controller.channel.write_request("pause", "req-pause")
        assert controller.advance(40) == rc.RUN_STATE_COMPLETED
        assert controller.channel.applied_request_ids() == ["req-pause"]

    def test_artifact_index_records_produced_artifacts(self, tmp_path):
        controller = build_controller(tmp_path, ticks=20)
        index = controller.finalize_artifact_index({"extra_label": "extra.json"})
        assert index["run_manifest"] == rc.MANIFEST_NAME
        assert index["checkpoint_index"].endswith("checkpoint_index.json")
        assert index["extra_label"] == "extra.json"
        assert controller.manifest.data["artifact_index"] == index


class TestResumeEquivalence:
    def test_resume_continues_the_uninterrupted_trajectory(self, tmp_path):
        reference = build_controller(tmp_path / "reference")
        reference.advance(40)

        controlled = build_controller(tmp_path / "controlled")
        controlled.channel.write_request("pause", "req-pause")
        assert controlled.advance(40) == rc.RUN_STATE_PAUSED
        pause_tick = controlled.engine.tick_count

        resumed = rc.resume_controller(tmp_path / "controlled", target_ticks=40)
        assert resumed.engine.tick_count == pause_tick
        assert resumed.advance(40) == rc.RUN_STATE_COMPLETED
        assert resumed.run_digest == reference.run_digest

    def test_resume_rejects_a_mismatched_run_id(self, tmp_path):
        controller = build_controller(tmp_path)
        path = controller.create_checkpoint()
        document = json.loads(path.read_text(encoding="utf-8"))
        document["run_id"] = "run-other"
        document["state_digest"] = ck.payload_digest(document["payload"])
        path.write_text(json.dumps(document), encoding="utf-8")
        controller.manifest.transition(rc.RUN_STATE_PAUSED)
        controller.manifest.save()
        with pytest.raises(rc.RunControlViolation):
            rc.resume_controller(tmp_path, path)

    def test_resume_requires_a_checkpoint(self, tmp_path):
        rc.RunManifest.create(tmp_path, make_config())
        with pytest.raises(rc.RunControlViolation):
            rc.resume_controller(tmp_path)

    def test_latest_checkpoint_helper(self, tmp_path):
        controller = build_controller(tmp_path, ticks=30)
        assert rc.latest_checkpoint_file(tmp_path).name.endswith("000000030.json")
        assert rc.latest_checkpoint_file(tmp_path / "absent") is None

    def test_checkpoint_file_for_tick_helper(self, tmp_path):
        assert rc.checkpoint_file_for_tick(tmp_path, 42).name == "checkpoint_000000042.json"


class TestStatusSurface:
    def test_collect_status_reports_the_run_record(self, tmp_path):
        controller = build_controller(tmp_path, ticks=20)
        controller.finalize_artifact_index()
        status = run_status.collect_status(tmp_path)
        assert status["run_id"] == controller.manifest.run_id
        assert status["run_state"] == rc.RUN_STATE_COMPLETED
        assert status["completed_ticks"] == 20
        assert status["checkpoint_count"] >= 1
        assert status["artifact_index"]

    def test_status_surface_does_not_mutate_its_inputs(self, tmp_path):
        controller = build_controller(tmp_path, ticks=20)
        controller.finalize_artifact_index()
        before = run_status.input_digest(tmp_path)
        run_status.write_status_surface(
            tmp_path, tmp_path / "snapshot.json", tmp_path / "page.html"
        )
        assert run_status.input_digest(tmp_path) == before

    def test_rendered_text_names_the_run_state(self, tmp_path):
        controller = build_controller(tmp_path, ticks=10)
        controller.finalize_artifact_index()
        text = run_status.render_text(run_status.collect_status(tmp_path))
        assert "run state" in text
        assert rc.RUN_STATE_COMPLETED in text

    def test_rendered_page_is_self_contained(self, tmp_path):
        controller = build_controller(tmp_path, ticks=10)
        controller.finalize_artifact_index()
        page = run_status.render_page(run_status.collect_status(tmp_path))
        assert run_status.page_is_self_contained(page) is True
        assert "<table>" in page

    def test_external_reference_is_detected(self):
        assert run_status.page_is_self_contained(
            "<link href=\"https://example.invalid/style.css\">"
        ) is False

    def test_status_of_an_empty_directory_is_safe(self, tmp_path):
        status = run_status.collect_status(tmp_path)
        assert status["run_state"] == "unknown"
        assert status["checkpoint_count"] == 0
        assert run_status.render_text(status)


class TestRunControlCli:
    def test_run_control_writes_a_request(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["run-control", str(tmp_path), "--request", "pause"])
        assert result.exit_code == 0
        assert (tmp_path / "control" / "control_request.json").exists()

    def test_run_status_prints_and_writes(self, tmp_path):
        controller = build_controller(tmp_path, ticks=20)
        controller.finalize_artifact_index()
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "run-status", str(tmp_path),
                "--snapshot", str(tmp_path / "snap.json"),
                "--page", str(tmp_path / "page.html"),
            ],
        )
        assert result.exit_code == 0
        assert "Run status surface" in result.output
        assert (tmp_path / "snap.json").exists()
        assert (tmp_path / "page.html").exists()

    def test_checkpoint_validate_accepts_a_valid_checkpoint(self, tmp_path):
        controller = build_controller(tmp_path, ticks=10)
        path = controller.create_checkpoint()
        runner = CliRunner()
        result = runner.invoke(cli, ["checkpoint-validate", str(path)])
        assert result.exit_code == 0
        assert "1 pass, 0 fail" in result.output

    def test_checkpoint_validate_reports_a_tampered_checkpoint(self, tmp_path):
        controller = build_controller(tmp_path, ticks=10)
        path = controller.create_checkpoint()
        document = json.loads(path.read_text(encoding="utf-8"))
        document["state_digest"] = "0" * 64
        path.write_text(json.dumps(document), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["checkpoint-validate", str(path)])
        assert result.exit_code == 1
        assert "state_digest_check" in result.output

    def test_checkpoint_validate_all_writes_a_report(self, tmp_path):
        build_controller(tmp_path, ticks=30)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["checkpoint-validate", str(tmp_path), "--all",
             "--report", str(tmp_path / "validation.json")],
        )
        assert result.exit_code == 0
        report = json.loads((tmp_path / "validation.json").read_text(encoding="utf-8"))
        assert report["validated_count"] >= 1
        assert report["fail_count"] == 0

    def test_run_control_requires_an_output_directory(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["run", "-c", "configs/milestone_1.toml", "-t", "2", "--run-control"]
        )
        assert result.exit_code != 0
