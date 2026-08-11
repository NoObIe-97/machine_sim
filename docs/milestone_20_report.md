# Milestone 20 Report: User-Owned Unattended Run Control and Local Run Status Surface

## Date

2026-08-12

## Summary

Made a simulation run an inspectable, interruptible, resumable object without changing any simulation dynamics. A run now carries a schema-versioned lifecycle manifest, writes deterministic checkpoints on a configured interval, honors user-written pause and stop requests through a file-based control channel, and can be resumed from a validated checkpoint in a fresh process. A per-tick digest chain derived from live state establishes that a paused-and-resumed run continues exactly as an uninterrupted run of the same configuration and seed.

The controlling property is continuation equivalence, and it holds on the primary run: a run paused at tick 8100, terminated, and resumed in a separate process reached tick 20000 with a run digest identical to the uninterrupted reference run, with zero mismatches across 40 sampled tick digests (24 of them after the resume point).

## Design Summary

- `sim/run_control.py` — run lifecycle manifest, restricted state machine, file-based control channel, per-tick digest chain, and the `RunController` that drives a `SimEngine` under checkpoint and control policy
- `sim/checkpoint.py` — dependency-free deterministic encoder/decoder for the live engine object graph, integrity digests, an explicit validator, and bounded retention with pruning
- `analysis/run_status.py` — strictly read-only status surface producing text, a JSON snapshot, and a self-contained local page
- `verification/milestone_20_judge.py` — 24 exact-PASS-only checks
- CLI: `run --run-control`, `run --resume-from`, `run-control`, `run-status`, `checkpoint-validate`, `unattended-demo`

## Run Lifecycle Manifest

`run_manifest.json`, schema version `1.0.0`, written atomically through a temporary file and `os.replace`, so a partially written manifest is never observable.

Fields: `manifest_schema_version`, `run_id`, `run_state`, `config_digest`, `seed`, `requested_ticks`, `completed_ticks`, `progress_ratio`, `run_digest`, `checkpoint_records`, `control_records`, `artifact_index`, `created_at_unix`, `updated_at_unix`.

`run_id` is derived deterministically from the configuration digest, the seed, and the requested tick count, so an uninterrupted reference run and a controlled run of the same configuration share an identifier and a digest chain origin.

Permitted transitions:

```text
initialized → running
running     → paused | stopped | completed | failed
paused      → running | stopped
stopped, completed, failed are terminal
```

Any other transition raises `RunControlViolation`. Progress is not permitted to decrease.

## Checkpoint Format

`checkpoints/checkpoint_<tick:09d>.json`, schema version `1.0.0`, with `run_id`, `tick`, `created_at_unix`, `config_digest`, `state_digest`, and `payload`.

The encoder emits primitives directly and tags every other node with a `$` type tag: `list`, `tuple`, `set`, `frozenset`, `deque` (with `maxlen`), `smap` and `map` for mappings, `enum`, `bytes`, `rng` for `random.Random` state, `fn` for module-level callables, `obj` for in-project objects, and `ref` for a shared object already emitted.

Properties the format guarantees:

- **Dependency-free** — standard library only, JSON rather than a binary pickle stream, so a checkpoint is inspectable.
- **Deterministic** — identical state produces byte-identical output. Mapping and attribute insertion order is preserved rather than sorted, because the tick loop observes mapping order: `degrade()` draws one random value per component in `components` order, so re-ordering that mapping on restore would change the draw sequence. Set members, whose iteration order is a function of insertion history rather than of the simulation, are emitted in a canonical order.
- **Aliasing-preserving** — `engine.rng is engine.world.rng` survives a restore, because shared objects are emitted once and referenced afterwards.
- **Restricted on load** — object reconstruction is limited to the `machine_sim.` module prefix. A checkpoint cannot cause an arbitrary class to be imported or constructed. Cycles and non-addressable callables are rejected at encode time with an explicit error.

The append-only event store is deliberately excluded: the tick loop reads only the per-tick buffer, which is captured, while `_events` is an output artifact. Each checkpoint records `recorded_event_count` and per-label `event_type_counts` in its place.

## Checkpoint Validation

`validate_checkpoint(path)` returns a structured report and never runs the simulation or modifies the file. Checks: `file_readable_check`, `json_parseable_check`, `schema_version_check`, `required_fields_check`, `tick_bounds_check`, `config_digest_present_check`, `state_digest_check` (recomputed against recorded), `payload_decodable_check` (under the restricted allowlist).

## Control Channel Protocol

The control channel is `<output_dir>/control/`, so a run directory is self-describing.

- `control_request.json` — the pending request, written by the user
- `control_history.jsonl` — append-only bounded record of applied requests

A request carries `request_id`, `requested_state` (`pause` or `stop`), and `requested_at_unix`. The engine reads the channel once every `control_poll_interval` ticks. Applying a request writes a checkpoint at the current tick, appends a control record, transitions the run state, clears the pending request, and returns control to the caller without raising. A `request_id` already present in the history is ignored and not re-applied.

Resume is a user action rather than a runtime request: the user invokes the resume path with a checkpoint, which restores engine state, transitions `paused → running`, and continues to the requested tick count.

## Per-Tick Digest Chain

```text
digest_0 = sha256(run_id)
digest_t = sha256(digest_{t-1} + canonical_tick_observation_t)
```

The tick observation is derived from live state — tick index, active unit count, and per-unit identifier, position, power reserve, mean component health, and active flag — with fixed six-decimal quantization so the chain is stable across processes. The chain value is checkpointed and restored, so a resumed run continues the same chain.

## Read-Only Status Surface

`run-status` reads the manifest, checkpoint index, control history, and progress trace, and renders run identifier, run state, progress, run digest, checkpoint count and bytes, control records, and artifact locations. It writes only to caller-supplied paths. Read-only behaviour is demonstrated numerically: the demo digests the manifest, progress trace, control channel, and checkpoint set before and after rendering and records that the digests match. The rendered page is self-contained with no remote stylesheet, script, font, image, or network call.

## Primary Run Evidence

Configuration: `configs/milestone_20_unattended_run_control.toml` — 120x120 grid, 8 initial units, 20000 ticks, seed 42, checkpoint interval 2000, retention limit 6, control poll interval 100, progress interval 500.

| Metric | Value |
|--------|-------|
| run_id | `run-b397a39b4a8ee4e0` |
| run_ticks | 20000 |
| final_run_state | completed |
| reference_final_run_state | completed |
| checkpoints written | 11 |
| checkpoints retained | 6 (ticks 10000–20000) |
| checkpoints pruned | 5 |
| max checkpoint bytes | 28790329 |
| applied control records | 1 |
| pause applied | yes, at tick 8100 |
| stop applied | yes (separate short run, stopped at tick 100) |
| resume applied | yes, separate process |
| resumed tick span | 11900 |
| checkpoint validation | 6 pass, 0 fail |
| status surface read-only | yes |
| status page self-contained | yes |
| demo elapsed | 1893.72 s |

Continuation equivalence:

```text
reference_run_digest          c836def339a2c1aebf9d4ba741d175828e2799b8345a032cbf68ab801986b4b5
resumed_run_digest            c836def339a2c1aebf9d4ba741d175828e2799b8345a032cbf68ab801986b4b5
digests_equal                 true
pause_tick                    8100
final_tick                    20000
resumed_tick_span             11900
compared_tick_count           40
post_resume_compared_tick_count 24
sampled_digest_mismatch_count 0
process_isolated              true
```

The reference run and the controlled run executed in separate processes, so no in-process state could mask a serialization defect.

## M20 Judge Result

M20_JUDGE_STATUS: PASS (24/24 checks passed, 0 SKIP, strict exact-PASS-only)

## M14–M19 Regression Judge Results

| Milestone | Status |
|-----------|--------|
| M14 | PASS |
| M15 | PASS |
| M16 | PASS |
| M17 | PASS (12/12) |
| M18 | PASS (14/14) |
| M19 | PASS (21/21) |

Regression was captured by the demo itself and re-confirmed after the final code state.

## Full M1-M20 Regression Summary

| Milestone | Key Metrics |
|-----------|-------------|
| M1 | 0/5 active at 500 ticks |
| M2 | 3/6 active at 100 ticks |
| M3 | 1/4 active, 30 emissions, 235 observations |
| M4 | 1/5 active, 39 emissions, 295 observations |
| M5 compare | adaptive +77 events, +10 emissions |
| M6 | 985 attempts, 9 successes, 9 lineage records |
| M7 compare | warm_start_power_delta +1.8906 |
| M8 | 50 frames, 182 reconciliation, 5 drift entries |
| M9 | 5 pressure cells, avg_depletion=0.366 |
| M10 | 3 patterns, 30 signals, 4 clusters |
| M11 | raw=100, compressed=20, ratio=0.200 |
| M12 | generations=100, capsule_compat=0.985 |
| M13 | consistency=0.961, combined_stability=0.925 |
| M14A | 20000 ticks, 120x120, 12/12 judge PASS |
| M15 | 30000 ticks, 120x120, 6 transfers, gen span 4, 12/12 judge PASS |
| M16 | 6 source records, 3 compressed segments, ratio 0.695, 12/12 judge PASS |
| M17 | 20000 ticks, 7 active, 5 transfers, 29036 plasticity events, 12/12 judge PASS |
| M18 | 6 variants, nontrivial sensitivity detected, 14/14 judge PASS |
| M19 | architecture variation, dimension-changing transfer, 21/21 judge PASS |
| M20 | 20000 ticks, pause at 8100, resumed span 11900, digests equal, 24/24 judge PASS |

## Tests and Coverage

```text
521 passed in 45.43s
Required test coverage of 77.0% reached. Total coverage: 77.94%
```

104 tests were added in this stage: 42 in `machine_sim/tests/test_checkpoint.py` and 62 in `machine_sim/tests/test_run_control.py`, covering encoder round-trips and guards, encoder determinism, decoder allowlist rejection, checkpoint create/validate/restore, tamper detection, retention pruning, every legal and illegal run-state transition, control request handling and duplicate suppression, in-process pause/restore/continue equivalence, digest chain determinism and restoration, status-surface read-only behaviour, page self-containment, and the four new CLI commands.

## Guardrail Result

```text
All guardrail checks passed.
```

## Commands Run

```bash
pip install -e ".[dev]"
python -m pytest machine_sim/tests -q
python -m pytest machine_sim/tests -q --cov=machine_sim --cov-report=term
python -m machine_sim.cli.main check
python -m machine_sim.cli.main unattended-demo -c configs/milestone_20_unattended_run_control.toml -o output/demo_m20
python -m machine_sim.cli.main run-status output/demo_m20
python -m machine_sim.cli.main checkpoint-validate output/demo_m20 --all
python -m machine_sim.verification.milestone_20_judge output/demo_m20
python -m machine_sim.verification.milestone_19_judge output/demo_m19
python -m machine_sim.verification.milestone_18_judge output/demo_m18
python -m machine_sim.verification.milestone_17_judge output/demo_m17
python -m machine_sim.verification.milestone_16_judge output/demo_m16
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_14_judge output/demo_m14
```

## Artifact Paths

- `output/demo_m20/run_manifest.json`
- `output/demo_m20/run_progress_trace.jsonl`
- `output/demo_m20/checkpoints/checkpoint_index.json`
- `output/demo_m20/checkpoints/checkpoint_<tick>.json`
- `output/demo_m20/control/control_history.jsonl`
- `output/demo_m20/checkpoint_validation_report.json`
- `output/demo_m20/resume_equivalence_report.json`
- `output/demo_m20/unattended_run_summary.json`
- `output/demo_m20/run_status_snapshot.json`
- `output/demo_m20/run_dashboard.html`
- `output/demo_m20/artifact_index.json`
- `output/demo_m20/milestone_20_judge_result.json`
- `output/demo_m20/reference_run/run_manifest.json`
- `output/demo_m20/stop_run/run_manifest.json`

## Known Limitations

- **Checkpoint size grows with accumulated in-engine trace buffers.** A checkpoint at tick 2000 was about 6.6 MB and one at tick 20000 was about 28.8 MB, because bounded-per-event traces such as the plasticity trace accumulate inside the engine over a run. Retention bounds the total on disk, but per-checkpoint size still grows roughly with run length. This is the primary input to M21: a multi-hour run needs either trace externalization or a checkpoint payload that excludes accumulated output traces.
- The append-only event store is not restored. Per-label counts are recorded instead. Post-run summaries computed after a resume therefore reflect only the resumed segment's events, while live simulation state and the digest chain are exact.
- Checkpoint capture is synchronous and pauses the tick loop for roughly 0.5–2 s at 120x120 scale.
- The status surface is a rendering of files on disk, not a live view; it reflects the last manifest write, which occurs on checkpoints and control transitions.
- Continuation equivalence is verified by digest sampling at the progress interval plus the final chain value, not at every tick.

## Next Recommended Milestone

```text
Milestone 21 — Unattended Multi-Hour Architecture Run and Post-Run Trajectory Analysis
```
