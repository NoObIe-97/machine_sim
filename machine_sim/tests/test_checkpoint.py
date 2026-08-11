"""Tests for deterministic checkpoint capture, validation, and restore."""

from __future__ import annotations

import json
import random
from collections import deque

import pytest

from machine_sim.agents.base import ActionType, Component, MemoryEntry
from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.sim import checkpoint as ck
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine


def make_config(**overrides) -> SimConfig:
    values = dict(
        grid_width=12,
        grid_height=12,
        resource_density=0.4,
        hazard_density=0.05,
        unit_count=3,
        power_drain_rate=0.5,
        max_ticks=60,
        seed=42,
        signal_enabled=True,
        adaptive_enabled=True,
        neural_controller_enabled=True,
        checkpoint_enabled=True,
        checkpoint_interval=10,
        checkpoint_retention_limit=3,
        control_poll_interval=5,
        run_progress_interval=5,
        run_digest_enabled=True,
    )
    values.update(overrides)
    return SimConfig(**values)


def build_engine(config: SimConfig | None = None, ticks: int = 0) -> SimEngine:
    cfg = config or make_config()
    engine = SimEngine(cfg, seed=cfg.seed)
    for index in range(cfg.unit_count):
        unit = MachineUnitImpl(
            unit_id=f"unit-{index:03d}",
            position=(index + 1, 1),
            signal_enabled=cfg.signal_enabled,
            adaptive_enabled=cfg.adaptive_enabled,
            neural_controller_enabled=cfg.neural_controller_enabled,
            neural_seed=cfg.seed,
        )
        unit.max_power = 5000
        unit.power_reserve = 5000
        engine.register_unit(unit)
    engine.initialize()
    for _ in range(ticks):
        engine.tick()
    return engine


class TestEncoderRoundTrip:
    def test_primitives_pass_through(self):
        for value in (None, True, False, 3, -2.5, "text"):
            assert ck.decode_state(ck.encode_state(value)) == value

    def test_tuple_round_trip_preserves_type(self):
        restored = ck.decode_state(ck.encode_state((1, "a", (2, 3))))
        assert restored == (1, "a", (2, 3))
        assert isinstance(restored, tuple)
        assert isinstance(restored[2], tuple)

    def test_set_round_trip_preserves_type(self):
        restored = ck.decode_state(ck.encode_state({(1, 2), (3, 4)}))
        assert restored == {(1, 2), (3, 4)}
        assert isinstance(restored, set)

    def test_frozenset_round_trip(self):
        restored = ck.decode_state(ck.encode_state(frozenset({1, 2})))
        assert restored == frozenset({1, 2})
        assert isinstance(restored, frozenset)

    def test_deque_round_trip_preserves_maxlen(self):
        source = deque([1, 2, 3], maxlen=5)
        restored = ck.decode_state(ck.encode_state(source))
        assert list(restored) == [1, 2, 3]
        assert restored.maxlen == 5

    def test_enum_round_trip(self):
        restored = ck.decode_state(ck.encode_state(ActionType.HARVEST))
        assert restored is ActionType.HARVEST

    def test_bytes_round_trip(self):
        restored = ck.decode_state(ck.encode_state(b"\x00\x01\xff"))
        assert restored == b"\x00\x01\xff"

    def test_nested_dataclass_round_trip(self):
        entry = MemoryEntry(tick=5, event_type="harvest", position=(2, 3), outcome_delta=1.5)
        restored = ck.decode_state(ck.encode_state(entry))
        assert isinstance(restored, MemoryEntry)
        assert restored.tick == 5
        assert restored.position == (2, 3)
        assert restored.outcome_delta == 1.5

    def test_random_generator_round_trip_continues_identically(self):
        source = random.Random(7)
        source.random()
        restored = ck.decode_state(ck.encode_state(source))
        assert [restored.random() for _ in range(5)] == [source.random() for _ in range(5)]

    def test_non_string_mapping_keys_round_trip(self):
        source = {(0, 0): "a", (1, 2): "b"}
        assert ck.decode_state(ck.encode_state(source)) == source

    def test_mapping_insertion_order_is_preserved(self):
        source = {"z": 1, "a": 2, "m": 3}
        restored = ck.decode_state(ck.encode_state(source))
        assert list(restored.keys()) == ["z", "a", "m"]

    def test_shared_object_stays_shared(self):
        shared = Component(name="sensor")
        payload = ck.encode_state({"first": shared, "second": shared})
        restored = ck.decode_state(payload)
        assert restored["first"] is restored["second"]


class TestEncoderGuards:
    def test_lambda_is_rejected(self):
        with pytest.raises(ck.CheckpointError):
            ck.encode_state(lambda: None)

    def test_out_of_allowlist_type_is_rejected(self):
        import argparse

        with pytest.raises(ck.CheckpointError):
            ck.encode_state(argparse.Namespace(value=1))

    def test_decoder_rejects_type_outside_allowlist(self):
        payload = {"$": "obj", "c": "os:PathLike", "f": [], "i": 0}
        with pytest.raises(ck.CheckpointError):
            ck.decode_state(payload)

    def test_decoder_rejects_unknown_tag(self):
        with pytest.raises(ck.CheckpointError):
            ck.decode_state({"$": "unrecognized", "i": 0})

    def test_decoder_rejects_unresolved_reference(self):
        with pytest.raises(ck.CheckpointError):
            ck.decode_state({"$": "ref", "i": 99})

    def test_cyclic_reference_is_rejected(self):
        left = Component(name="sensor")
        cycle = {"outer": None}
        cycle["outer"] = cycle
        with pytest.raises(ck.CheckpointError):
            ck.encode_state({"left": left, "cycle": cycle})


class TestDeterminism:
    def test_repeated_encoding_is_byte_identical(self):
        engine = build_engine(ticks=12)
        first = ck.canonical_text(ck.encode_state(engine))
        second = ck.canonical_text(ck.encode_state(engine))
        assert first == second

    def test_capture_restore_recapture_is_byte_identical(self):
        engine = build_engine(ticks=12)
        captured = ck.encode_state(engine)
        restored = ck.decode_state(json.loads(ck.canonical_text(captured)))
        assert ck.payload_digest(captured) == ck.payload_digest(ck.encode_state(restored))

    def test_config_digest_is_stable_and_change_sensitive(self):
        first = make_config()
        second = make_config()
        assert ck.config_digest(first) == ck.config_digest(second)
        assert ck.config_digest(make_config(seed=43)) != ck.config_digest(first)


class TestEngineRestore:
    def test_restored_engine_preserves_generator_aliasing(self):
        engine = build_engine(ticks=8)
        restored = ck.restore_engine_state(ck.capture_engine_state(engine))
        assert restored.rng is restored.world.rng

    def test_restored_engine_continues_identically(self):
        engine = build_engine(ticks=15)
        restored = ck.restore_engine_state(ck.capture_engine_state(engine))
        for _ in range(20):
            engine.tick()
            restored.tick()
        assert ck.payload_digest(ck.encode_state(engine)) == ck.payload_digest(
            ck.encode_state(restored)
        )

    def test_restored_engine_keeps_tick_counter(self):
        engine = build_engine(ticks=9)
        restored = ck.restore_engine_state(ck.capture_engine_state(engine))
        assert restored.tick_count == engine.tick_count

    def test_event_counts_are_recorded_even_though_store_is_not_restored(self):
        engine = build_engine(ticks=6)
        payload = ck.capture_engine_state(engine)
        assert payload["recorded_event_count"] > 0
        assert payload["event_type_counts"]
        restored = ck.restore_engine_state(payload)
        assert restored.event_log.all_events() == []

    def test_restore_requires_engine_section(self):
        with pytest.raises(ck.CheckpointError):
            ck.restore_engine_state({})


class TestCheckpointFiles:
    def test_write_load_and_restore_round_trip(self, tmp_path):
        engine = build_engine(ticks=10)
        path = ck.write_checkpoint(engine, tmp_path, engine.tick_count, "run-x", "digest-x")
        assert path.exists()
        restored, document = ck.restore_from_checkpoint(path)
        assert document["run_id"] == "run-x"
        assert document["tick"] == engine.tick_count
        assert restored.tick_count == engine.tick_count

    def test_partial_file_is_not_left_behind(self, tmp_path):
        engine = build_engine(ticks=4)
        ck.write_checkpoint(engine, tmp_path, engine.tick_count, "run-x", "digest-x")
        assert not list((tmp_path / "checkpoints").glob("*.partial"))

    def test_validation_passes_for_a_written_checkpoint(self, tmp_path):
        engine = build_engine(ticks=5)
        path = ck.write_checkpoint(engine, tmp_path, engine.tick_count, "run-x", "digest-x")
        report = ck.validate_checkpoint(path)
        assert report["valid"] is True
        assert report["failed_checks"] == []
        assert set(report["checks"]) >= {
            "file_readable_check",
            "json_parseable_check",
            "schema_version_check",
            "required_fields_check",
            "tick_bounds_check",
            "state_digest_check",
            "payload_decodable_check",
        }

    def test_validation_detects_a_tampered_payload(self, tmp_path):
        engine = build_engine(ticks=5)
        path = ck.write_checkpoint(engine, tmp_path, engine.tick_count, "run-x", "digest-x")
        document = json.loads(path.read_text(encoding="utf-8"))
        document["payload"]["recorded_event_count"] += 1
        path.write_text(json.dumps(document), encoding="utf-8")
        report = ck.validate_checkpoint(path)
        assert report["valid"] is False
        assert report["checks"]["state_digest_check"] == "FAIL"

    def test_validation_reports_missing_file(self, tmp_path):
        report = ck.validate_checkpoint(tmp_path / "absent.json")
        assert report["valid"] is False
        assert report["checks"]["file_readable_check"] == "FAIL"

    def test_validation_reports_unparseable_file(self, tmp_path):
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        report = ck.validate_checkpoint(broken)
        assert report["valid"] is False
        assert report["checks"]["json_parseable_check"] == "FAIL"

    def test_load_rejects_unsupported_schema_version(self, tmp_path):
        target = tmp_path / "old.json"
        target.write_text(json.dumps({"checkpoint_schema_version": "0.0.1"}), encoding="utf-8")
        with pytest.raises(ck.CheckpointError):
            ck.load_checkpoint(target)

    def test_restore_rejects_digest_mismatch(self, tmp_path):
        engine = build_engine(ticks=4)
        path = ck.write_checkpoint(engine, tmp_path, engine.tick_count, "run-x", "digest-x")
        document = json.loads(path.read_text(encoding="utf-8"))
        document["state_digest"] = "0" * 64
        path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ck.CheckpointError):
            ck.restore_from_checkpoint(path)

    def test_load_reports_absent_file(self, tmp_path):
        with pytest.raises(ck.CheckpointError):
            ck.load_checkpoint(tmp_path / "absent.json")


class TestRetention:
    def _write_series(self, tmp_path, count: int):
        engine = build_engine(ticks=2)
        for index in range(1, count + 1):
            ck.write_checkpoint(engine, tmp_path, index, "run-x", "digest-x")

    def test_retention_prunes_oldest_first(self, tmp_path):
        self._write_series(tmp_path, 5)
        pruned = ck.prune_checkpoints(tmp_path, 2)
        remaining = [p.name for p in ck.list_checkpoints(tmp_path)]
        assert len(pruned) == 3
        assert remaining == ["checkpoint_000000004.json", "checkpoint_000000005.json"]

    def test_newest_checkpoint_is_never_pruned(self, tmp_path):
        self._write_series(tmp_path, 3)
        ck.prune_checkpoints(tmp_path, 1)
        remaining = ck.list_checkpoints(tmp_path)
        assert remaining[-1].name == "checkpoint_000000003.json"

    def test_retention_below_limit_prunes_nothing(self, tmp_path):
        self._write_series(tmp_path, 2)
        assert ck.prune_checkpoints(tmp_path, 5) == []

    def test_zero_retention_limit_prunes_nothing(self, tmp_path):
        self._write_series(tmp_path, 2)
        assert ck.prune_checkpoints(tmp_path, 0) == []

    def test_index_lists_retained_checkpoints_only(self, tmp_path):
        self._write_series(tmp_path, 4)
        ck.prune_checkpoints(tmp_path, 2)
        index_path = ck.write_checkpoint_index(tmp_path)
        entries = json.loads(index_path.read_text(encoding="utf-8"))["checkpoints"]
        assert [entry["tick"] for entry in entries] == [3, 4]
        assert all(entry["byte_size"] > 0 for entry in entries)
        assert all(entry["state_digest"] for entry in entries)

    def test_index_is_not_treated_as_a_checkpoint(self, tmp_path):
        self._write_series(tmp_path, 2)
        ck.write_checkpoint_index(tmp_path)
        assert all("index" not in p.name for p in ck.list_checkpoints(tmp_path))

    def test_list_checkpoints_on_missing_directory(self, tmp_path):
        assert ck.list_checkpoints(tmp_path / "absent") == []
