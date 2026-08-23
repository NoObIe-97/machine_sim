# After Silicon — MiMo Milestone 22A Goal Spec: Fabrication Finalization and Lineage Consistency

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current M22 remote head:

```text
955b343bf66a11e6c0d7a0c938e907bcaf1bb73e
```

M22's executable design-program substrate is technically strong and must be preserved. Do **not** redesign the interpreter, instruction set, program variation model, compatibility projection, or M21 deep semantic oracle.

M22 final acceptance is held on one accounting/causality inconsistency discovered during independent review.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

Do not start M23.

---

# Blocking defect

In current program-enabled construction, `FabricationEngine.fabricate()` finalizes a nominal successful fabrication before M22 program variation/interpretation is known to be valid.

The current order is effectively:

```text
FabricationEngine.fabricate()
  → deduct base power/material cost
  → reserve successor placement/id
  → append LineageRecord
  → set source _last_fabrication_tick
  → increment _fabrication_successes
  → return success

M22 engine program path
  → transfer/vary program
  → execute program
  → if decoded architecture is invalid:
       record FABRICATION_FAILED
       create no successor
       continue
```

Therefore a failed M22 program can currently leave contradictory state:

```text
no successor object exists
but fabrication success count increased
and lineage record exists
and successful-fabrication tick was marked
```

This is unacceptable before M23 because later work will measure differential successor production, lineage continuity, copy success, and endogenous construction rates. A failed program must not be represented as a successful fabricated descendant.

The intended M22 policy remains:

```text
invalid / nonfunctional successor program
→ assembly does not complete
→ no successor unit enters the world
→ costs already physically consumed remain consumed according to the documented model
→ attempt/failure is recorded
→ no successful lineage edge is recorded
→ no fabrication-success counter increment is recorded
```

---

# Required correction

Implement a deterministic transactional or two-phase fabrication finalization boundary.

Exact class/function names are implementation choices, but the semantic phases must be explicit:

```text
1. prerequisite / attempt phase
2. resource consumption / placement reservation phase
3. program transfer + interpretation / successor assembly preparation
4. final successful construction commit
```

Success-only state must be committed only after an actual successor has been assembled successfully and is about to be registered.

At minimum, all of the following must be success-only:

```text
_fabrication_successes increment
LineageRecord append
source _last_fabrication_tick success marker
successful-generation lineage edge
any summary field described as successful fabrication
```

Attempt-only state may still occur on a failed program:

```text
_fabrication_attempts increment
source _last_fabrication_attempt_tick
base power/material consumption already incurred
program execution cost already incurred
failure counter / failure cause
failure event / failed-program trace
```

Be explicit about successor-ID reservation. Either behavior below is acceptable if deterministic and documented:

A. reserve an ID during the attempt and allow gaps after failed assembly; or
B. allocate the definitive successor ID only during success finalization.

Whichever policy is chosen, an unused/reserved ID must never appear in successful lineage summaries as if a unit existed.

---

# Preserve legacy semantics

Legacy M6–M21 fabrication paths must retain their accepted behavior.

For configurations without M22 design-program mode, successful construction should still produce the same lineage, counters, unit creation, resource effects, and deterministic trajectories as before.

Use the M21 deep semantic oracle and existing regression judges to verify this.

Do not change:

```text
fabrication prerequisite thresholds
fabrication cooldown policy for ordinary attempts
base fabrication power cost
base material cost
placement rules
legacy descriptor variation
M19 architecture variation semantics
M22 program interpreter semantics
M22 program variation probabilities
neural-state transfer semantics
```

unless a correction is strictly necessary to implement transactional finalization, in which case document the exact reason and prove legacy equivalence.

---

# Failure accounting semantics

Add an explicit machine-native failure cause for a program that cannot produce a usable successor architecture, reusing the current `successor_program_invalid` name if appropriate.

The fabrication subsystem summary must distinguish:

```text
total attempts
successful completed constructions
failures by cause
```

A program-invalid assembly attempt must satisfy:

```text
attempt_count += 1
success_count unchanged
failure_count[successor_program_invalid] += 1
lineage_count unchanged
active unit count unchanged
no world occupancy added
```

Costs must follow the already documented M22 policy. Add exact tests proving which of these remain consumed after failure:

```text
base fabrication power
base fabrication material
program execution cost
architecture fabrication cost, if and only if that cost is physically incurred before failure under the chosen model
```

Do not silently refund or double-charge costs.

---

# Success accounting semantics

A valid program-backed construction must satisfy exactly once:

```text
attempt_count += 1
success_count += 1
one lineage record appended
one successor unit created
one world placement occupied
source successful-fabrication tick updated
```

No counter or lineage record may be duplicated between provisional and finalization phases.

The design-program transfer/execution traces may record both successful and failed attempts, but their schema/status must make the distinction unambiguous.

If a trace uses a candidate/provisional successor ID for a failed attempt, document that field as provisional rather than a real lineage edge.

---

# Lineage analyzer correction

Audit:

```text
machine_sim/analysis/design_program_lineage.py
FabricationEngine.get_summary()
M22 demo summary generation
review/report metrics
```

Ensure all reported successful descendant/program-transfer counts are based only on completed successor constructions.

Failed program attempts may be summarized separately but must not inflate:

```text
successful transfer count
lineage depth
successor count
generation distribution
fabrication success rate
```

---

# Required live tests

Add integration tests that deliberately force a program failure after fabrication prerequisites pass.

Construct a deterministic fixture where:

```text
source has sufficient power/material
placement is available
fabrication prerequisites pass
program mode is enabled
successor program execution returns invalid_program or invalid_operand
```

Before/after assertions must prove:

```text
fabrication attempts: +1
fabrication successes: +0
lineage records: +0
unit count: unchanged
world occupied-unit count: unchanged
FABRICATION_FAILED emitted exactly once with program failure cause
no FABRICATION_SUCCEEDED event for that attempt
attempt cooldown state is coherent
successful-fabrication marker is not falsely advanced
specified consumed costs changed exactly once
```

Also add a paired valid-program fixture proving:

```text
attempts: +1
successes: +1
lineage: +1
units: +1
world occupancy: +1
one success event
no program-invalid failure event
```

Add a sequence test:

```text
failed program attempt
→ later valid attempt
```

and prove that the failed attempt does not create a phantom generation or lineage edge.

---

# M22 judge hardening

Strengthen `machine_sim/verification/milestone_22_judge.py` with a live transactional-finalization probe.

The M22 judge must fail if any of these are observed after a deliberately invalid program-backed attempt:

```text
success counter increased
lineage record appended
new unit created
world occupancy increased
successful-fabrication marker falsely updated
FABRICATION_SUCCEEDED emitted
failure counter missing
```

And must pass only if a valid paired attempt finalizes exactly one success and one lineage record.

Do not trust only pre-generated artifacts for this check; use a live deterministic probe.

Keep exact-PASS-only semantics. Any missing/inconclusive evidence is FAIL.

If the number of M22 judge checks changes from 25, update all documentation and test fixtures consistently.

---

# Deep-digest / checkpoint requirements

Because fabrication counters, lineage/finalization state, and cooldown state can affect future behavior, audit the M21 deep semantic schema after this refactor.

Required proofs:

1. same valid construction path remains deterministic;
2. same invalid construction path remains deterministic;
3. checkpoint round-trip after an invalid attempt preserves future-causal accounting state;
4. process-isolated pause/resume still yields zero deep-digest mismatches in the M22 program-enabled scenario;
5. legacy M21 reference/equivalence behavior remains accepted where applicable.

Do not add output-only lineage-analysis data to the deep digest unless it affects future runtime decisions.

---

# Verification requirements

Run at minimum:

```text
full pytest suite
coverage >= existing project threshold
machine-sim guardrails
M14 judge
M15 judge
M16 judge
M17 judge
M18 judge
M19 judge
M20 judge
M21 judge
M22 judge
M22 compatibility demo
M22 variable-program demo
M22 process-isolated pause/resume equivalence
```

All required checks must be exact PASS.

---

# Documentation and stage closing

Update:

```text
docs/milestone_22_report.md
docs/review_package.md
```

Document:

- M22A correction commit;
- exact transactional-finalization model;
- invalid-program cost semantics;
- success/failure counter semantics;
- live judge probe;
- final tests and coverage;
- M14–M22 regression status;
- final remote hash;
- readiness for M23.

Do not claim M22 accepted until this consistency issue is fixed and independently judged.

---

# Acceptance criteria

M22A passes only when all of the following are true:

```text
M22A_PROGRAM_FAILURE_DOES_NOT_INCREMENT_SUCCESS: PASS
M22A_PROGRAM_FAILURE_DOES_NOT_APPEND_LINEAGE: PASS
M22A_PROGRAM_FAILURE_DOES_NOT_CREATE_UNIT: PASS
M22A_PROGRAM_FAILURE_DOES_NOT_OCCUPY_WORLD_CELL: PASS
M22A_PROGRAM_FAILURE_EVENT_EXACT: PASS
M22A_PROGRAM_FAILURE_COUNTER_EXACT: PASS
M22A_PROGRAM_FAILURE_COST_ACCOUNTING_EXACT: PASS
M22A_SUCCESS_FINALIZATION_EXACTLY_ONCE: PASS
M22A_FAILED_THEN_VALID_SEQUENCE_NO_PHANTOM_LINEAGE: PASS
M22A_LEGACY_FABRICATION_SEMANTICS_PRESERVED: PASS
M22A_DEEP_DIGEST_AND_CHECKPOINT_CONSISTENCY: PASS
M22A_PROCESS_ISOLATED_PAUSE_RESUME_EQUIVALENCE: PASS
M14_M15_M16_M17_M18_M19_M20_M21_REGRESSIONS_STILL_PASS: PASS
M22_INDEPENDENT_JUDGE_EXACT_PASS_ONLY: PASS
M22_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
```

Only then:

```text
MILESTONE_22_FINAL_ACCEPTANCE: ACCEPTED
READY_FOR_MILESTONE_23: YES
```

---

# Final handoff format

Return a concise GitHub handoff containing:

```text
repository
branch
starting_commit
implementation_commit
final_remote_commit
files_changed
tests
coverage
guardrails
M14–M22 judge statuses
invalid-program accounting evidence
valid-program finalization evidence
failed-then-valid sequence evidence
pause/resume deep-digest mismatch count
stage-closing result
MILESTONE_22_STATUS
READY_FOR_MILESTONE_23
```

Do not start M23.