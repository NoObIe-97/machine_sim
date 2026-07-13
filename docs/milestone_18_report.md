# Milestone 18 Report: Neural Controller Variant Sensitivity

## Date

2026-07-14

## Summary

Implemented deterministic cross-variant comparison for internal neural processing units. M18 runs multiple neural controller variants under controlled field conditions, collects bounded per-variant artifacts, compares neural trajectories and runtime outcomes, and produces a sensitivity report identifying which controller parameters most strongly change observable metrics.

## Design Summary

- Variant sweep configuration with 6 variants (1 scalar baseline + 5 neural variants)
- Configurable `neural_hidden_size` and `neural_plasticity_rate` through SimConfig
- Per-variant artifact directories under `output/demo_m18/variants/<id>/`
- Cross-variant comparison module (`neural_variant_comparison.py`) with cosine similarity matrices
- Controller sensitivity analysis attributing metric deltas to specific parameter changes
- M18 independent judge with 14 required checks, all must be exactly PASS

## Relation to M17

M18 preserves the accepted M17 neural processing unit, stable deterministic seeding, strict M17 judge, and local-only neural input boundary. M18 adds configurability (hidden_size, plasticity_rate) and a variant sweep infrastructure without modifying the core neural controller architecture.

## Variant Definitions

| Variant ID | Hidden Size | Plasticity Rate | Plasticity Enabled | Run Ticks |
|------------|-------------|-----------------|--------------------|-----------| 
| scalar_baseline | 16 | 0.01 | true | 5000 |
| neural_h16_rate001 | 16 | 0.01 | true | 10000 |
| neural_h8_rate001 | 8 | 0.01 | true | 5000 |
| neural_h32_rate001 | 32 | 0.01 | true | 5000 |
| neural_h16_rate000 | 16 | 0.0 | false | 5000 |
| neural_h16_rate005 | 16 | 0.05 | true | 5000 |

- `neural_h16_rate001` matches accepted M17 baseline settings
- `neural_h8_rate001` and `neural_h32_rate001` test hidden-size sensitivity
- `neural_h16_rate000` tests plasticity-disabled behavior
- `neural_h16_rate005` tests increased plasticity rate (5x baseline)

## Controller Parameters Varied

- `neural_hidden_size`: 8, 16, 32 (M17 default: 16)
- `neural_plasticity_rate`: 0.0, 0.01, 0.05 (M17 default: 0.01)
- `neural_plasticity_enabled`: true/false

## Per-Variant Runtime Summary

| Variant | Active | Transfers | Plasticity Events |
|---------|--------|-----------|-------------------|
| scalar_baseline | 8 | 0 | 0 |
| neural_h16_rate001 | 7 | 5 | 29036 |
| neural_h8_rate001 | 9 | 3 | 14892 |
| neural_h32_rate001 | 8 | 4 | 15249 |
| neural_h16_rate000 | 9 | 4 | 0 |
| neural_h16_rate005 | 9 | 5 | 73109 |

## Similarity Matrix Summary

- Nontrivial off-diagonal difference detected: yes
- Action distribution similarity ranges from ~0.85 to ~0.99 across variants
- Neural state similarity shows clear separation between hidden-size variants

## Controller Sensitivity Summary

- Nontrivial controller parameter effect detected: yes
- Most sensitive parameter: plasticity_rate
- Least sensitive parameter: hidden_size
- Plasticity-disabled variant shows zero plasticity events as expected
- Higher plasticity rate (0.05) produces ~2.5x more plasticity events than baseline

## M14/M15/M16/M17 Regression Judge Results

| Milestone | Status |
|-----------|--------|
| M14 | PASS |
| M15 | PASS |
| M16 | PASS |
| M17 | PASS (12/12, strict exact-PASS-only) |

## M18 Judge Result

M18_JUDGE_STATUS: PASS (14/14 checks passed, 0 SKIP)

| Check | Status |
|-------|--------|
| variant_count_check | PASS |
| accepted_m17_variant_check | PASS |
| hidden_size_variant_check | PASS |
| plasticity_rate_variant_check | PASS |
| plasticity_disabled_variant_check | PASS |
| per_variant_artifact_check | PASS |
| per_variant_runtime_check | PASS |
| similarity_matrix_check | PASS |
| nontrivial_difference_check | PASS |
| sensitivity_summary_check | PASS |
| m17_regression_check | PASS |
| m14_m15_m16_regression_check | PASS |
| bounded_artifact_size_check | PASS |
| machine_native_wording_check | PASS |

## Artifact Paths

- `output/demo_m18/neural_variant_sweep_summary.json`
- `output/demo_m18/neural_variant_similarity_matrix.json`
- `output/demo_m18/neural_controller_sensitivity_summary.json`
- `output/demo_m18/per_variant_runtime_summary.jsonl`
- `output/demo_m18/per_variant_neural_summary.jsonl`
- `output/demo_m18/milestone_18_judge_result.json`
- `output/demo_m18/variants/<variant_id>/` (per-variant artifacts)

## Tests and Coverage

```
385 passed in 46.99s
Coverage: 80.02%
```

## Commands Actually Run

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main variant-sweep -c configs/milestone_18_neural_controller_variant_sensitivity.toml -o output/demo_m18
python -m machine_sim.verification.milestone_18_judge output/demo_m18
python -m machine_sim.verification.milestone_17_judge output/demo_m17
python -m machine_sim.verification.milestone_14_judge output/demo_m14
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

## Full M1-M18 Regression Summary

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
| M17 | 20000 ticks, 120x120, 7 active, 5 transfers, 29036 plasticity events, 12/12 judge PASS |
| M18 | 6 variants, nontrivial sensitivity detected, 14/14 judge PASS |

## Known Limitations

- Variant sweep run times are practical but not instant; larger tick counts would increase runtime proportionally
- Sensitivity analysis is comparative, not causal — it identifies correlations between parameter changes and metric deltas
- The scalar baseline uses default SimConfig values for hidden_size/plasticity_rate even though it doesn't use a neural controller

## Next Recommended Milestone

Implement multi-seed variant robustness testing: run each variant configuration across multiple seeds to assess variance in sensitivity scores and determine which parameter effects are consistent vs. seed-dependent.
