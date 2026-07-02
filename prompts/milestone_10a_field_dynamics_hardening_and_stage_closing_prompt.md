# After Silicon — MiMo Milestone 10A Field Dynamics Hardening and Stage Closing Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 10 implementation head:

```text
a3010e1
```

Milestone 10 core implementation is present, but final acceptance is on hold pending field-dynamics hardening and stage-closing completion.

Do not start Milestone 11.

Before final handoff, invoke and satisfy the shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
MILESTONE_10_CORE_IMPLEMENTATION: PASS
FIELD_DYNAMICS_MODULE: PASS_WITH_NOTES
ENGINE_AND_CLI_INTEGRATION: PASS
M10_TEST_ASSERTION_STRENGTH: PARTIAL
M10_SIGNAL_GRADIENT_SUMMARY_OUTPUT: FAIL
FULL_M1_M10_REGRESSION_REPORTING: FAIL
REVIEW_PACKAGE_SYNC: FAIL
NEXT_MILESTONE_WORDING: FAIL
MILESTONE_10_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_11: NO
```

---

## What already passed

Keep these pieces unless a minimal correction is needed:

- `machine_sim/analysis/field_dynamics.py` exists.
- Signal pattern frequency is implemented.
- Temporal signal-density clustering is implemented.
- Pattern-observation correlation is implemented.
- Bounded signal and observation histories are implemented.
- Engine integration exists as a post-pressure field-dynamics phase.
- CLI prints a basic signal-dynamics summary.
- `signal_field_dynamics.json` artifact is written.
- 193 tests reportedly pass with coverage above 80%.

---

## Blocking issue 1 — signal-gradient mapping is computed but not exposed

`SignalFieldDynamics.compute_signal_gradient(world)` exists, but the M10 summary, CLI output, and artifact do not include signal-gradient metrics.

Fix this by making signal-gradient metrics part of the M10 summary and artifact.

Required output fields:

```text
signal_gradient_cells
avg_signal_gradient
max_signal_gradient
```

Implementation options:

1. Store the latest gradient summary during the engine run, or
2. Add a `get_summary(world=None)` / `get_field_dynamics_summary()` path that computes gradient with access to world state.

Prefer a simple, clean design that avoids repeated expensive recomputation.

The CLI M10 output should include a line like:

```text
Signal gradient: cells=..., avg_gradient=..., max_gradient=...
```

The artifact `signal_field_dynamics.json` must include the gradient fields.

---

## Blocking issue 2 — tests need stronger numeric assertions

Strengthen `machine_sim/tests/test_field_dynamics.py` so it proves real behavior rather than only existence/non-negative values.

Required tests:

1. **Pattern frequency nonzero from deterministic run**
   - Run a real signal-enabled engine setup or use real recorded signal calls.
   - Assert:

```python
assert summary["total_signals"] > 0
assert summary["pattern_count"] > 0
```

2. **Density clusters nonzero in deterministic demo**
   - Assert:

```python
assert summary["cluster_count"] > 0
assert summary["peak_cluster_density"] > 0
```

3. **Signal-gradient fields are present and nonzero or meaningfully numeric**
   - Assert fields exist:

```python
assert "signal_gradient_cells" in summary
assert "avg_signal_gradient" in summary
assert "max_signal_gradient" in summary
```

   - Prefer nonzero for deterministic signal-enabled demo:

```python
assert summary["signal_gradient_cells"] > 0
assert summary["max_signal_gradient"] > 0.0
```

4. **Pattern correlation is nonzero in deterministic demo**
   - Assert:

```python
assert summary["correlation_count"] > 0
assert summary["avg_correlation_score"] > 0.0
assert summary["max_correlation_score"] > 0.0
```

5. **Bounded storage is asserted**
   - Create `SignalFieldDynamics(max_records=N)`.
   - Record more than `N` signals and observations.
   - Assert internal bounded stores stay within `N`:

```python
assert len(dynamics._signal_history) <= N
assert len(dynamics._observation_history) <= N
```

6. **Signal-disabled safe-zero test remains**
   - Ensure signal-disabled mode returns clean zero summaries and does not crash.

7. **Artifact generation test**
   - If practical, add a CLI or engine/output test confirming `signal_field_dynamics.json` contains nonzero M10 summary fields, including gradient fields.

---

## Blocking issue 3 — full M1–M10 regression reporting missing

`docs/milestone_10_report.md` currently lists only M10 demo commands. Update it to include the full M1–M10 command set:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check

python -m machine_sim.cli.main run -c configs/milestone_1.toml -t 500 -s 42 -o output/demo_m1
python -m machine_sim.cli.main inspect output/demo_m1

python -m machine_sim.cli.main run -c configs/milestone_2_crowded.toml -t 100 -s 42 -o output/demo_m2
python -m machine_sim.cli.main inspect output/demo_m2

python -m machine_sim.cli.main run -c configs/milestone_3_signals.toml -t 100 -s 42 -o output/demo_m3
python -m machine_sim.cli.main inspect output/demo_m3

python -m machine_sim.cli.main run -c configs/milestone_4_correlation.toml -t 100 -s 42 -o output/demo_m4
python -m machine_sim.cli.main inspect output/demo_m4

python -m machine_sim.cli.main run -c configs/milestone_5_adaptive.toml -t 150 -s 42 -o output/demo_m5
python -m machine_sim.cli.main inspect output/demo_m5
python -m machine_sim.cli.main compare -c configs/milestone_5_adaptive.toml -t 150 -s 42

python -m machine_sim.cli.main run -c configs/milestone_6_fabrication.toml -t 200 -s 42 -o output/demo_m6
python -m machine_sim.cli.main inspect output/demo_m6

python -m machine_sim.cli.main run -c configs/milestone_7_calibration_capsules.toml -t 200 -s 42 -o output/demo_m7
python -m machine_sim.cli.main inspect output/demo_m7
python -m machine_sim.cli.main capsule-compare -c configs/milestone_7_calibration_capsules.toml -t 200 -s 42

python -m machine_sim.cli.main run -c configs/milestone_8_telemetry_reconciliation.toml -t 200 -s 42 -o output/demo_m8
python -m machine_sim.cli.main inspect output/demo_m8

python -m machine_sim.cli.main run -c configs/milestone_9_resource_pressure.toml -t 200 -s 42 -o output/demo_m9
python -m machine_sim.cli.main inspect output/demo_m9

python -m machine_sim.cli.main run -c configs/milestone_10_signal_field_dynamics.toml -t 200 -s 42 -o output/demo_m10
python -m machine_sim.cli.main inspect output/demo_m10
```

The report must include numeric summaries for M1–M10, not only commands.

---

## Blocking issue 4 — review package is stale

`docs/review_package.md` still says `Milestone 9 Final Review Package` and still reports old M9 final values.

Update it to Milestone 10 final state after this hardening pass:

- Retitle to `# Milestone 10 Final Review Package`.
- Add M10 and M10A commit hashes.
- Update final test count and runtime to the current run.
- Update final coverage to the current run.
- Include M1–M10 regression summary.
- Include M10 artifact path: `output/demo_m10/signal_field_dynamics.json`.
- Include `docs/milestone_10_report.md` in report paths.
- Confirm clean working tree after final push.

---

## Blocking issue 5 — next milestone wording is not machine-native enough

Current next milestone wording contains terms like memory sharing and inheritance and includes a typo/non-English token. Replace it with machine-native wording.

Suggested wording:

```text
Milestone 11: Bounded Operational Trace Compression — compressed signal-field histories, telemetry-window reduction, capsule-compatible diagnostic summaries, lineage-indexed trace comparison, and bounded replay metrics.
```

Do not implement Milestone 11.

---

## Stage closing chores

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

This means the final response must be aligned with updated docs, review package, current test/coverage values, full regression summaries, artifact paths, and final remote hash.

---

## Required verification commands

Run the full M1–M10 command set listed above.

Also run the guardrail command:

```bash
python -m machine_sim.cli.main check
```

Run a wording check against files added or modified for M10/M10A and remove problematic matches introduced by this stage.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
MILESTONE_10A_STATUS: PASS or PARTIAL_PASS
MILESTONE_10_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_11: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Files changed:
Tests:
Coverage:
Guardrail result:
Full M1-M10 regression summary:
M10 demo output:
Artifact paths:
Stage closing chores result:
Documentation updates:
Known limitations:
Clean working tree:
```

Do not claim Milestone 10 is accepted unless all acceptance criteria are satisfied.

---

## Acceptance criteria

```text
M10A_SIGNAL_GRADIENT_EXPOSED_IN_SUMMARY: PASS
M10A_SIGNAL_GRADIENT_EXPOSED_IN_CLI_AND_ARTIFACT: PASS
M10A_STRONG_NUMERIC_TESTS: PASS
M10A_BOUNDED_STORAGE_TEST: PASS
M10A_SIGNAL_DISABLED_SAFE_ZERO: PASS
FULL_M1_M10_REGRESSION_REPORTED: PASS
MILESTONE_10_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
