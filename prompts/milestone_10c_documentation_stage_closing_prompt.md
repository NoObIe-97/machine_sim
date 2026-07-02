# After Silicon — MiMo Milestone 10C Documentation-Only Stage Closing Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 10B remote head:

```text
78a4ee7
```

Milestone 10 runtime, gradient exposure, and test hardening are now accepted. Final Milestone 10 acceptance is blocked only by stale documentation and incomplete stage-closing chores.

Do not modify runtime code unless a documentation command reveals a genuine breakage. Do not start Milestone 11.

Before final handoff, invoke and satisfy the updated shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M10_CORE_IMPLEMENTATION: PASS
M10A_SIGNAL_GRADIENT_EXPOSED_IN_SUMMARY: PASS
M10A_SIGNAL_GRADIENT_EXPOSED_IN_CLI_AND_ARTIFACT: PASS
M10B_STRONG_NUMERIC_TESTS: PASS
M10B_BOUNDED_STORAGE_TEST: PASS
MILESTONE_10_REPORT_CURRENT: FAIL
REVIEW_PACKAGE_CURRENT: FAIL
FULL_M1_M10_REGRESSION_REPORTED: FAIL
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: FAIL
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_10_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_11: NO
```

---

## Required scope

This is a documentation-only corrective pass unless a verification command fails.

Update exactly the documentation needed for stage closing:

```text
docs/milestone_10_report.md
docs/review_package.md
```

No runtime feature work. No Milestone 11 implementation.

---

## Required milestone report updates

Update `docs/milestone_10_report.md` so it is current with M10B.

Required contents:

1. Current tests and coverage from the latest run:

```text
194 passed in 16.14s
Coverage: 83.06%
```

Use exact values from your rerun if different.

2. Full M1–M10 verification command set, not only M10 commands.

3. Numeric M1–M10 regression summary.

4. M10 output including the signal-gradient line:

```text
Signal dynamics: patterns=3, total_signals=30, clusters=4
Pattern correlation: records=3, avg_score=12.295, max_score=21.538
Signal gradient: cells=4, avg_gradient=1.180, max_gradient=3.701
```

Use exact current output from your rerun if different.

5. Artifact path:

```text
output/demo_m10/signal_field_dynamics.json
```

6. Current known limitations.

7. Replace the current next milestone wording with this machine-native wording:

```text
Milestone 11: Bounded Operational Trace Compression — compressed signal-field histories, telemetry-window reduction, capsule-compatible diagnostic summaries, lineage-indexed trace comparison, and bounded replay metrics.
```

Remove the old wording containing `pattern摘要`, `memory sharing`, or `inheritance`.

---

## Required review package updates

Update `docs/review_package.md` so it is fully current through M10C.

Required contents:

- Title: `# Milestone 10 Final Review Package`
- Commit list includes at least:
  - `3173b3f` — Milestone 10 signal pattern field dynamics
  - `24261e9` — Milestone 10A signal-gradient exposure
  - `78a4ee7` — Milestone 10B test hardening
  - the new M10C documentation commit hash after you create it
- Final tests match latest run.
- Final coverage matches latest run.
- M1–M10 regression summary is present.
- M10 output includes the signal-gradient line.
- Artifact paths include:

```text
output/demo_m10/signal_field_dynamics.json
```

- Report paths include:

```text
docs/milestone_10_report.md
```

- Clean working tree status is current after push.

A one-line commit append is not sufficient.

---

## Required verification commands

Run the current verification set and record exact outputs:

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

Run the freshness checks from:

```text
prompts/skills/stage_closing_chores.md
```

Before final handoff, reopen or inspect the committed docs and verify the stage-closing evidence block below.

---

## Required stage-closing evidence block

Your final handoff must include this block with all values set to `yes`:

```text
STAGE_CLOSING_SKILL_INVOKED: yes
MILESTONE_REPORT_TITLE_CURRENT: yes
MILESTONE_REPORT_TESTS_CURRENT: yes
MILESTONE_REPORT_COVERAGE_CURRENT: yes
MILESTONE_REPORT_FULL_REGRESSION_CURRENT: yes
REVIEW_PACKAGE_TITLE_CURRENT: yes
REVIEW_PACKAGE_TESTS_CURRENT: yes
REVIEW_PACKAGE_COVERAGE_CURRENT: yes
REVIEW_PACKAGE_CURRENT_MILESTONE_SUMMARY: yes
CURRENT_ARTIFACT_PATHS_REPORTED: yes
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes
NO_STALE_DOC_VALUES_FOUND: yes
CLEAN_WORKTREE_AFTER_PUSH: yes
FINAL_REMOTE_HASH_REPORTED: yes
```

If any value is `no`, report `PARTIAL_PASS` or `HOLD`.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
MILESTONE_10C_STATUS: PASS or PARTIAL_PASS
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

---

## Acceptance criteria

```text
M10C_MILESTONE_10_REPORT_CURRENT: PASS
M10C_REVIEW_PACKAGE_CURRENT: PASS
FULL_M1_M10_REGRESSION_REPORTED: PASS
CURRENT_TESTS_AND_COVERAGE_REPORTED: PASS
M10_DEMO_OUTPUT_WITH_GRADIENT_REPORTED: PASS
M10_ARTIFACT_PATH_REPORTED: PASS
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
