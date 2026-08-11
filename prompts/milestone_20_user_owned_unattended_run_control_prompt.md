# After Silicon — Milestone 20 Goal Spec: User-Owned Unattended Run Control and Local Run Status Surface

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 19 remote head:

```text
d9bd3bf
```

Milestone 19 is accepted. Milestone 20 must build on the accepted M14 long-run adaptive control, M15 multi-generation trace evolution, M16 trajectory compression, M17/M17A/M17B internal neural processing unit, M18/M18A controller-variant sensitivity, and M19 successor-transferred architecture variation.

Do not regress the accepted M14, M15, M16, M17, M18, or M19 judges.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Strategic direction

M14 through M19 produced increasingly long deterministic runs whose only execution mode is "start a process and wait for it to finish." A 40000-tick M19 primary run already takes roughly 13 minutes of wall clock. The next scientific step — multi-hour unattended architecture runs — is not reachable while a run is an opaque, uninterruptible, unresumable process.

M20 must therefore make a run an inspectable, interruptible, resumable object without changing any simulation dynamics.

The required system boundary is:

```text
run lifecycle manifest
→ periodic deterministic checkpoint
→ user-issued control request (pause / resume / stop)
→ resume from checkpoint in a new process
→ verified continuation equivalence against an uninterrupted reference run
→ read-only local status surface over manifest, checkpoints and artifact locations
```

The controlling requirement is **continuation equivalence**: a run that is paused at tick `k`, terminated, and resumed from its tick-`k` checkpoint in a fresh process must produce exactly the same per-tick digest chain from tick `k+1` onward as an uninterrupted run of the same configuration and seed. If that property does not hold, checkpointing is not a scientific instrument and M20 fails.

Control must be user-owned. The simulator must not start background daemons, schedule itself, supervise its own processes, or reach the network. The user starts a process, the user writes a control request, the user resumes a run.

---

## Scope boundary

M20 is a run-control and run-observability milestone.

M20 must implement:

- a schema-versioned run lifecycle manifest,
- deterministic full-state checkpoint capture and restore,
- checkpoint integrity digests and an explicit checkpoint validator,
- a file-based user-owned control channel supporting pause, resume, and stop,
- resume-from-checkpoint execution in a fresh process,
- a per-tick run digest chain and a continuation-equivalence report,
- a read-only local run status surface (text and a self-contained local page),
- an artifact location index,
- an exact-PASS-only M20 judge.

M20 must **not** implement:

- any change to unit decision logic, environment dynamics, fabrication, neural controller behaviour, or architecture variation,
- a network service, remote endpoint, or hosted page,
- a background daemon, scheduler, watchdog, or self-restarting supervisor,
- multi-hour unattended runs as an acceptance requirement,
- distributed or multi-process concurrent simulation,
- external optimization or run selection.

The multi-hour unattended architecture run is reserved for M21 and must be able to consume M20's substrate unchanged.

---

## Conceptual and wording boundary

Use machine-native terminology in committed runtime code, config keys, artifact schemas, and reports.

Runtime modules under `machine_sim/sim/`, `machine_sim/agents/`, `machine_sim/environment/`, and `machine_sim/analysis/` are lexically scanned. Avoid the established forbidden terms, and in particular avoid these terms which are easy to introduce in control-plane code:

```text
goal
aim
purpose
reason
why
meaning
intend
want
wish
trust
group
identity
character
experience
aware
law
leadership
social
community
```

Prefer:

```text
run lifecycle
run state
control request
control channel
checkpoint
checkpoint digest
continuation equivalence
progress record
artifact index
status surface
retention limit
poll interval
```

Artifact field names, config keys, and report wording must satisfy the same boundary.

---

## Milestone 20 goal statement

Produce a deterministic, user-controllable run lifecycle in which a long run can be paused on user request, terminated, resumed in a fresh process from a validated checkpoint, and inspected through a read-only local status surface — while producing byte-identical continuation relative to an uninterrupted reference run.

---

## Core implementation requirements

### 1. Run lifecycle manifest

Add `machine_sim/sim/run_control.py`.

The manifest file is `run_manifest.json` in the run output directory.

Required fields:

```text
manifest_schema_version      string, semantic version
run_id                       string, deterministic from config digest + seed + requested ticks
run_state                    one of: initialized, running, paused, stopped, completed, failed
config_digest                sha256 of the canonical config mapping
seed                         integer
requested_ticks              integer
completed_ticks              integer
progress_ratio               float in [0.0, 1.0]
run_digest                   hex digest of the per-tick digest chain at last write
checkpoint_records           list of checkpoint index entries
control_records              list of applied control records
artifact_index               mapping of artifact label to relative path
created_at_unix              float
updated_at_unix              float
```

Run state transitions must be restricted to:

```text
initialized → running
running     → paused | stopped | completed | failed
paused      → running | stopped
```

Any other transition must raise `RunControlViolation`.

Manifest writes must be atomic: write to a temporary file in the same directory, then replace. A partially written manifest must never be observable.

### 2. Deterministic checkpoint capture

Add `machine_sim/sim/checkpoint.py`.

Checkpoint capture must serialize the complete mutable engine state required to continue the run, including at minimum:

```text
engine tick counter
engine random generator state
world grid cell resource quantities, hazard intensities, occupancy, terrain
world signal list and next signal identifier
world active cell set
every registered unit, active or inactive, including
    position, power reserve, capacity, component health values,
    bounded sensor reading buffer, bounded local record buffer,
    adaptive state vector and policy state,
    neural controller weights, hidden state, plasticity counters,
    recurrent connection mask,
    architecture descriptor,
    generation index, lifetime ticks, per-action counters
fabrication engine counters and lineage records
capsule manager contents
correlator, telemetry, and enabled analyzer state
all bounded trace buffers held by the engine
accumulated processing and fabrication cost totals
per-tick digest chain value
```

Serialization must be:

- **dependency-free** — standard library only,
- **deterministic** — the same state must produce byte-identical output, with sorted mapping keys and a fixed float representation,
- **inspectable** — JSON, not a binary pickle stream,
- **type-preserving** — tuples, sets, deques with `maxlen`, enum members, and `random.Random` state must round-trip exactly,
- **restricted on load** — object reconstruction must be limited to an explicit module prefix allowlist (`machine_sim.`) plus a small set of standard-library container types. Loading a checkpoint must never import or construct an arbitrary attacker-chosen class.

Checkpoint files are written to `checkpoints/checkpoint_<tick:09d>.json` with:

```text
checkpoint_schema_version
run_id
tick
created_at_unix
config_digest
state_digest        sha256 over the canonical serialized state payload
payload             the encoded state
```

`checkpoint_index.json` must list every retained checkpoint with tick, path, state digest, and byte size.

A `checkpoint_retention_limit` must bound the number of retained checkpoint files; pruning removes the oldest first and must never prune the most recent checkpoint.

### 3. Checkpoint validation

`validate_checkpoint(path)` must return a structured report containing per-check results and an overall boolean, checking at minimum:

```text
file readable and JSON-parseable
checkpoint schema version supported
required top-level fields present
recomputed state digest equals recorded state digest
tick is a non-negative integer
payload decodes under the restricted allowlist
config digest present
```

Validation must never execute the run and must never modify the checkpoint.

### 4. User-owned control channel

Control requests are files, not signals or sockets.

The control channel lives in `<output_dir>/control/`:

```text
control_request.json     current pending request written by the user
control_history.jsonl    append-only bounded record of applied requests
```

A request has:

```text
request_id          string
requested_state     one of: pause, stop
requested_at_unix   float
```

The engine polls the control channel every `control_poll_interval` ticks. Polling must be bounded work and must not read the file more than once per poll.

On an applied `pause` request the run must: write a checkpoint at the current tick, append a control record, set `run_state` to `paused`, clear the pending request, and return control to the caller without raising.

On an applied `stop` request the run must do the same with `run_state` set to `stopped`.

A request whose `request_id` already appears in the control history must be ignored exactly once and not re-applied.

Resume is a user action, not a runtime request: the user invokes the resume path with a checkpoint, which restores engine state, sets `run_state` to `running`, and continues the tick loop to the requested tick count.

### 5. Per-tick digest chain

The engine must be able to maintain a bounded-cost per-tick digest chain when `run_digest_enabled` is set:

```text
digest_0     = sha256(run_id)
digest_t     = sha256(digest_{t-1} + canonical_tick_observation_t)
```

The tick observation must be derived from live simulation state — at minimum tick index, active unit count, and per-unit position, power reserve, and component health — with a fixed float quantization so the chain is stable across processes and platforms.

The digest chain value must be checkpointed and restored. A resumed run must continue the same chain.

### 6. Continuation equivalence verification

Add a verification path that produces `resume_equivalence_report.json` containing:

```text
reference_run_digest             digest chain value of the uninterrupted run at final tick
resumed_run_digest               digest chain value of the resumed run at final tick
digests_equal                    bool
pause_tick                       int
final_tick                       int
resumed_tick_span                int, final_tick - pause_tick
reference_tick_digests           bounded sample of (tick, digest) pairs
resumed_tick_digests             bounded sample at the same ticks
sampled_digest_mismatch_count    int
process_isolated                 bool, true when the resumed run executed in a separate process
```

The resumed run must execute in a **separate process** from the reference run so that latent in-process state cannot mask a serialization defect.

### 7. Read-only local status surface

Add `machine_sim/analysis/run_status.py`.

The status surface must be strictly read-only: it must not write into the manifest, checkpoints, or control channel, and must not advance the run.

It must render, from the manifest and checkpoint index alone:

```text
run identifier, run state, progress ratio, completed and requested ticks
last checkpoint tick, checkpoint count, total checkpoint bytes
applied control record count and last control record
artifact index as label → absolute path
```

Outputs:

- a text rendering, printed by the CLI,
- `run_status_snapshot.json`, written only to a caller-supplied status output path,
- `run_dashboard.html`, a self-contained local page with no external references — no remote stylesheet, script, font, or image, and no network access of any kind.

### 8. CLI surface

Extend `machine_sim/cli/main.py` with:

```text
run                   gains --run-control, --checkpoint-interval, --resume-from
run-control           writes a pause or stop request into a run output directory
run-status            prints the read-only status surface and optionally writes snapshot + page
checkpoint-validate   validates one checkpoint, or every checkpoint under a run directory
unattended-demo       executes the full M20 evidence scenario and writes all M20 artifacts
```

The control channel always lives at `<output_dir>/control/`, so a run directory
is self-describing and no separate control path option is required.

Default behaviour of the existing `run` command must be unchanged when the new options are absent.

---

## Configuration requirements

Add:

```text
configs/milestone_20_unattended_run_control.toml
```

Add guardrail-approved config keys:

```text
run_control_enabled
checkpoint_enabled
checkpoint_interval
checkpoint_retention_limit
control_poll_interval
run_progress_interval
run_digest_enabled
run_status_surface_enabled
```

Recommended primary-run parameters:

```text
grid_width >= 120
grid_height >= 120
unit_count between 6 and 12
max_ticks >= 20000
seed = 42
adaptive_enabled = true
neural_controller_enabled = true
neural_plasticity_enabled = true
neural_architecture_variation_enabled = true
fabrication_enabled = true
signal_enabled = true
long_run_adaptation_enabled = true
run_control_enabled = true
checkpoint_enabled = true
checkpoint_interval between 1000 and 5000
checkpoint_retention_limit >= 4
control_poll_interval between 50 and 500
run_digest_enabled = true
```

Preferred evidence targets:

```text
run_ticks >= 20000
retained checkpoints >= 4
at least 1 applied pause request
at least 1 applied stop request
at least 1 resume from checkpoint in a separate process
resumed tick span >= 5000
continuation digests equal
all retained checkpoints validate
```

---

## Required artifacts

Written under `output/demo_m20/`:

```text
run_manifest.json
run_progress_trace.jsonl
checkpoints/checkpoint_<tick>.json
checkpoints/checkpoint_index.json
control/control_history.jsonl
checkpoint_validation_report.json
resume_equivalence_report.json
unattended_run_summary.json
run_status_snapshot.json
run_dashboard.html
artifact_index.json
milestone_20_judge_result.json
```

`unattended_run_summary.json` must include at minimum:

```text
run_id
run_ticks
requested_ticks
final_run_state
checkpoint_count
retained_checkpoint_count
pruned_checkpoint_count
applied_control_count
pause_applied
stop_applied
resume_applied
resumed_tick_span
continuation_equivalence
checkpoint_validation_pass_count
checkpoint_validation_fail_count
max_checkpoint_bytes
status_surface_read_only
strict_regression_summary
```

All JSONL artifacts must remain bounded — under 100000 lines each.

---

## Independent M20 judge

Add `machine_sim/verification/milestone_20_judge.py`, invoked as:

```bash
python -m machine_sim.verification.milestone_20_judge output/demo_m20
```

It must write `milestone_20_judge_result.json` and print `M20_JUDGE_STATUS`. Overall status is `PASS` only when **every** check is exactly `PASS`. No SKIP, no partial credit, no defaulting a missing artifact to PASS.

Required checks:

```text
1.  manifest_present_check
2.  manifest_schema_version_check
3.  manifest_terminal_run_state_check
4.  progress_monotonic_check
5.  checkpoint_count_check
6.  checkpoint_index_consistency_check
7.  checkpoint_digest_integrity_check
8.  checkpoint_validation_report_check
9.  checkpoint_retention_bound_check
10. pause_request_applied_check
11. stop_request_applied_check
12. control_history_consistency_check
13. resume_from_checkpoint_check
14. process_isolated_resume_check
15. continuation_equivalence_check
16. resumed_tick_span_check
17. sampled_digest_mismatch_check
18. long_run_ticks_check
19. artifact_index_completeness_check
20. status_surface_read_only_check
21. self_contained_status_page_check
22. bounded_artifact_size_check
23. m14_m15_m16_m17_m18_m19_regression_check
24. machine_native_wording_check
```

The regression check must require recorded `PASS` status for M14, M15, M16, M17, M18, and M19 judges; a missing regression record is `FAIL`, not `PASS`.

The wording check must scan every JSON and JSONL artifact in the output directory for the forbidden term list and fail on any match.

---

## Tests required

Add `machine_sim/tests/test_run_control.py` and `machine_sim/tests/test_checkpoint.py`.

Required coverage:

```text
manifest creation, atomic write, and reload round-trip
every legal run-state transition
every illegal run-state transition raising RunControlViolation
config digest stability across equal configs and change under any config edit
encoder round-trip for tuple, set, deque with maxlen, enum, nested dataclass, random.Random
encoder determinism: same state encodes byte-identically twice
decoder rejection of a class outside the module allowlist
checkpoint create → validate → restore round-trip
checkpoint digest mismatch detected on tampered payload
checkpoint validation report structure and failure paths
retention limit pruning, newest checkpoint never pruned
control request write, poll, apply, and duplicate-request suppression
pause applied at a poll boundary sets paused state and writes a checkpoint
stop applied sets stopped state
in-process pause → restore → continue equals uninterrupted run digest
per-tick digest chain determinism and restoration
status surface renders without mutating manifest, checkpoints, or control channel
status page contains no external reference
CLI: run-control, run-status, checkpoint-validate
```

The full suite must pass, and project coverage must not fall below the configured `fail_under` threshold.

---

## Scientific guardrails

- No simulation dynamics may change. M14–M19 judges must still pass on freshly produced or previously accepted artifacts, and the M20 continuation-equivalence property is itself evidence that dynamics are untouched.
- Checkpoint restore must not re-seed, re-randomize, or re-place units.
- The status surface must be read-only, and this must be demonstrated by digesting the run directory before and after rendering.
- No network access, no background process, no self-scheduling.
- Determinism claims must be produced by cross-process execution, not by in-process object reuse alone.

---

## Documentation requirements

- `docs/milestone_20_report.md` with design summary, manifest and checkpoint schemas, control-channel protocol, continuation-equivalence evidence, exact commands run, current test count and coverage, artifact paths, known limitations, and the next recommended milestone.
- `docs/review_package.md` retitled to Milestone 20 and fully synchronized.
- `docs/roadmap.md` updated through M20 with duplicate entries removed.
- `docs/architecture.md` updated with the run-control layer.

---

## Verification commands

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

---

## Acceptance criteria

M20 is accepted only when all of the following hold:

1. `M20_JUDGE_STATUS: PASS` with every check exactly `PASS` and zero SKIP.
2. M14, M15, M16, M17, M18, and M19 judges all report `PASS`.
3. Full test suite passes with no failures and no skips introduced by this stage.
4. Coverage meets or exceeds the configured threshold.
5. `All guardrail checks passed.`
6. Continuation equivalence holds across a real cross-process pause/resume cycle over at least 5000 resumed ticks.
7. Documentation is synchronized per `prompts/skills/stage_closing_chores.md`.
8. Working tree is clean and the branch is pushed.

---

## Next recommended milestone

```text
Milestone 21 — Unattended Multi-Hour Architecture Run and Post-Run Trajectory Analysis
```
