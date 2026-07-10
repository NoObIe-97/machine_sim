# Milestone 17 Report: Internal Neural Processing Unit

## Date

2026-07-10

## Summary

Implemented a compact recurrent neural processing unit inside each adaptive unit. The neural controller converts local sensor inputs plus recurrent state into action preferences and selected action parameters. Its internal state and plastic parameters update from local operational feedback during runtime. The neural controller replaces the scalar adaptive controller for normal action selection when enabled.

## Design Summary

- `NeuralController` — compact recurrent neural controller with deterministic initialization from unit id and seed
- `NeuralProcessingConfig` — configuration for input/hidden/output sizes, plasticity rate, and weight bounds
- `NeuralProcessingState` — bounded internal state including weight matrices and recurrent hidden state
- Sensor input vector built from 16 local runtime values only (no global map, no future state, no external scores)
- Action selection via softmax over neural action logits
- Local plasticity update using eligibility trace: `W_out += lr * delta * outer(h, a_onehot)`
- Successor neural-state transfer with bounded Gaussian variation
- M17 independent judge with 12 required checks

## Why Neural Controller Instead of Transformer/Token Model

The current simulator uses low-dimensional sensorimotor inputs, not token streams. An untrained token-sequence model would be computationally expensive and scientifically noisy at this stage. The immediate need is a compact internal processing unit with inspectable local plasticity. The neural controller uses pure Python with no ML framework dependencies.

## Neural Controller Architecture

```
h_t = tanh(W_in @ x_t + W_rec @ h_{t-1} + b_hidden)
action_logits = W_out @ h_t + c_action
action_preferences = softmax(action_logits)
param_biases = clamp(W_param @ h_t + c_param, -1, 1)
```

- Input size: 16 (sensor input vector)
- Hidden/recurrent state size: 16
- Action output size: 7 (MOVE, SCAN, HARVEST, EMIT_SIGNAL, IDLE, MAINTAIN, FABRICATE)
- Parameter output size: 3 (signal intensity bias, scan interval bias, extraction threshold bias)
- Weight initialization: Xavier-like with deterministic seed

## Sensor Input Vector Schema

```
0: power_ratio
1: average_component_health
2: local_resource_detected (0/1)
3: local_resource_strength (0-1)
4: local_hazard_detected (0/1)
5: local_hazard_strength (0-1)
6: signal_observed_recent (0/1)
7: signal_emitted_recent (0/1)
8: movement_blocked_recent (0/1)
9: resource_extracted_recent (0/1)
10: scan_result_count_recent (normalized)
11-14: previous_action_one_hot (MOVE/SCAN/HARVEST/SIGNAL)
15: time_since_last_signal_normalized (0-1)
```

All inputs derived from local unit state only. No global map input, no future state input, no external analysis scores.

## Action Output Schema

7 action types with softmax-normalized preferences:
- MOVE: move toward resource gradient or random direction
- SCAN: scan local area
- HARVEST: extract resources at current position
- EMIT_SIGNAL: emit signal with adaptive parameters
- IDLE: conserve power
- MAINTAIN: repair weakest critical component
- FABRICATE: mapped to IDLE (fabrication not directly controlled)

## Plasticity Update Rule

```
feedback_delta = normalized local feedback score
eligibility = outer(hidden_state, selected_action_onehot)
W_out += plasticity_rate * feedback_delta * eligibility
```

- Plasticity rate: 0.01
- Weight bound: [-2.0, 2.0]
- Deterministic under seed
- Uses only local feedback (power delta, resource extraction, hazard exposure, signal observation, movement blocks)

## Successor Neural-State Transfer

When fabrication occurs, the successor receives:
- Bounded recurrent processing state (hidden state with Gaussian noise)
- Weight matrices with bounded variation (variation=0.05)
- Controller configuration id
- Source/successor neural-state delta recorded in transfer trace

## Neural-vs-Scalar Comparison Results

- Neural active: 7, Scalar active: 6
- Neural successor transfers: 5
- Neural plasticity events: 25296
- Nontrivial neural difference detected: yes
- Signal observations: 189 emissions, 16001 observations

## Long-Run Parameters

```
grid: 120x120, resource_density=0.45, hazard_density=0.01
6 initial units, 20000 ticks, seed=42, power_drain_rate=0.08
unit_capacity=40, fabrication_interval=5
fabrication_power_cost=3.0, fabrication_material_cost=0.3
component_degradation_scale=0.2
signal_enabled=true, signal_pattern_count=4
neural_controller_enabled=true, neural_controller_mode=replace
neural_plasticity_enabled=true
```

## Signal Observation Summary

- Total emissions: 189
- Total observations: 16001
- Total associations: 2258
- 4 signal patterns with balanced emission rates

## M14/M15/M16 Regression Judge Results

| Milestone | Status | Checks |
|-----------|--------|--------|
| M14 | PASS | 12/12 |
| M15 | PASS | 12/12 |
| M16 | PASS | 12/12 |

## M17 Judge Result

M17_JUDGE_STATUS: PASS (12/12 checks passed, 0 SKIP)

| Check | Status |
|-------|--------|
| long_run_ticks_check | PASS |
| neural_controller_enabled_check | PASS |
| neural_state_trace_check | PASS |
| neural_action_trace_check | PASS |
| plasticity_update_check | PASS |
| local_input_only_check | PASS |
| neural_vs_scalar_difference_check | PASS |
| successor_neural_transfer_check | PASS |
| signal_observation_check | PASS |
| bounded_artifact_size_check | PASS |
| m14_m15_m16_regression_check | PASS |
| machine_native_wording_check | PASS |

## Artifact Paths

- `output/demo_m17/neural_processing_summary.json`
- `output/demo_m17/neural_state_trace.jsonl`
- `output/demo_m17/neural_action_trace.jsonl`
- `output/demo_m17/neural_plasticity_trace.jsonl`
- `output/demo_m17/neural_successor_transfer_trace.jsonl`
- `output/demo_m17/neural_vs_scalar_compare.json`
- `output/demo_m17/resource_hazard_field_summary.json`
- `output/demo_m17/neural_controller_config.json`
- `output/demo_m17/neural_parameter_snapshot_initial.json`
- `output/demo_m17/neural_parameter_snapshot_final.json`
- `output/demo_m17/milestone_17_judge_result.json`

## Tests and Coverage

```
332 passed in 35.03s
Coverage: 82.77%
```

## Commands Actually Run

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_17_internal_neural_processing_unit.toml -t 20000 -s 42 -o output/demo_m17
python -m machine_sim.cli.main inspect output/demo_m17
python -m machine_sim.verification.milestone_17_judge output/demo_m17
python -m machine_sim.verification.milestone_14_judge output/demo_m14
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

## Full M1-M17 Regression Summary

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
| M16 | 6 source records, 3 compressed segments, ratio 0.695, replay stable, 12/12 judge PASS |
| M17 | 20000 ticks, 120x120, 7 active, 5 transfers, 25296 plasticity events, 12/12 judge PASS |

## Known Limitations

- Neural controller uses pure Python matrix operations; NumPy would improve performance for larger hidden sizes
- Fabrication rate is limited by cooldown; neural successor transfers occur only when fabrication succeeds
- The neural controller does not yet support hybrid mode (combining neural and scalar scores)

## Next Recommended Milestone

Implement cross-configuration adaptive comparison between neural controller variants with different hidden sizes, plasticity rates, or input vector schemas. This would allow systematic evaluation of neural controller hyperparameter sensitivity across field configurations.
