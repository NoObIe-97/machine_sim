# After Silicon — MiMo v2.5-pro Planning Prompt

## Role

You are acting as the autonomous technical architect for a new research/simulation codebase.

## Project Title

**After Silicon: Bias-Guarded Machine Civilization Emergence Simulator**

## Project Premise

Build a simulator where autonomous post-collapse machines begin with only machine-native survival telemetry, limited perception, primitive actions, and no human/social/emotional/historical priors.

Over later milestones, civilization-like patterns may emerge from:

- resource scarcity
- memory
- prediction
- reproduction
- inheritance
- repair dependency
- signaling
- conflict
- cooperation
- environmental pressure

## Critical Invariant

The simulated machines must **not** be tiny humans in robot bodies.

They must not internally possess concepts such as:

- society
- morality
- law
- friendship
- greed
- fear
- pain
- hunger
- love
- language
- leadership
- trade
- family
- tribe
- crime
- cooperation

Those may appear only later as **observer-level interpretations** if justified by behavior and evidence.

The runtime agent logic must stay machine-native.

## Your Task in This Planning Phase

Create a detailed but non-spoon-fed implementation plan for the project.

You must make your own decisions about:

- architecture
- naming
- module boundaries
- test strategy
- guardrail strategy
- milestone definitions
- review package structure
- Git discipline

Do **not** expect the user to provide variable names, class names, folder names, or exact algorithms.

## Required Outputs

Generate the following planning files:

```text
docs/architecture.md
docs/roadmap.md
docs/guardrails.md
docs/milestone_1_plan.md
docs/review_package_spec.md
```

The content must include:

1. A concise project architecture document.
2. A milestone roadmap from minimal survival substrate to reproduction, inheritance, signaling, conflict/cooperation, and observer-level affect interpretation.
3. A strict bias-guardrail design that prevents anthropomorphic leakage into runtime machine logic.
4. A Milestone 1 implementation plan.
5. Milestone 1 acceptance criteria.
6. A review package specification for future external review.
7. A Git discipline policy:
   - branch naming
   - commit expectations
   - clean working tree requirement
   - final summary format

## Planning Constraints

- Do not implement code in this phase unless explicitly instructed later.
- Do not use LLM agents as simulated machines.
- Simulated machines must be bounded algorithmic agents.
- Do not hardcode positive or negative emotions.
- Do not hardcode cooperation, hostility, greed, morality, leadership, or society.
- Use deterministic seeds where possible.
- Design for automated tests.
- Design for later replay and experiment analysis.
- Keep Milestone 1 small enough to implement, test, run, and review.
- The first implementation milestone should prove:
  - simulation substrate
  - guardrails
  - CLI execution
  - event logging
  - testability

## Conceptual Guardrail

The simulator should allow machine-native mechanisms such as:

- resource deficit
- power reserve depletion
- component degradation
- repair need
- sensor uncertainty
- actuator failure
- operating-risk prediction
- proximity-based interaction
- resource blocking
- resource sharing
- local event memory
- prediction-error adaptation
- signal correlation

But runtime machine logic must not contain high-level human/social/emotional labels.

Observer-level labels may be introduced only in later analysis modules, and only as interpretations derived from measurable patterns.

## Milestone Roadmap Expectations

Your roadmap should include at least these future stages:

1. Minimal survival substrate.
2. Learning and short memory.
3. Primitive non-semantic signaling.
4. Conflict/cooperation substrate through resource pressure.
5. Reproduction and design inheritance.
6. Mutation and lineage divergence.
7. Parent-like calibration and knowledge transfer.
8. Distributed operational memory.
9. Observer-level affect interpretation.
10. Long-horizon experiment suite and replay analysis.

## Milestone 1 Scope

Milestone 1 should **not** include:

- reproduction
- inheritance
- teaching
- deception
- semantic communication
- language
- emotions
- observer-level affect analysis
- civilization scoring
- social group formation

Milestone 1 should focus only on:

- executable simulation
- machine-native state
- resource pressure
- survival/degradation mechanics
- primitive actions
- event logging
- deterministic runs
- guardrail enforcement
- basic tests
- demo output

## Final Response Required

At the end of the planning run, provide:

```text
TASK_STATUS: PASS or FAIL
Repository path
Branch name
Files created/modified
Planning files generated
Summary of architecture
Summary of guardrails
Milestone roadmap
Milestone 1 acceptance criteria
Known design risks
Recommended next /goal text for Milestone 1 implementation
Git status
```

Do not claim PASS unless all required planning files are created and the working tree is clean.
