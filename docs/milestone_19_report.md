# Milestone 19 Report: Successor-Transferred Neural Architecture Variation

## Date

2026-07-14

## Summary

Implemented successor-transferred neural architecture variation so units can produce successors with different neural processing capacity and connection density. Architecture varies during successor creation through bounded deterministic variation. Overlapping neural state is preserved during dimension changes. Explicit processing and fabrication costs are charged for neural complexity.

## Design Summary

- `NeuralArchitectureDescriptor` — per-unit architecture descriptor with hidden_size, recurrent_density, plasticity_rate
- `NeuralArchitectureConfig` — global bounds and cost coefficients
- `vary_architecture()` — deterministic bounded successor variation using stable_seed()
- `resize_state_for_successor()` — dimension-changing neural state transfer (expansion and contraction)
- `compute_recurrence_mask()` — sparse recurrent connection representation
- `compute_processing_cost()` — architecture-dependent per-decision power cost
- `compute_fabrication_cost()` — architecture-dependent successor construction cost
- `neural_architecture_lineage.py` — read-only lineage and distribution analyzer
- M19 judge with 21 exact-PASS-only checks

## Architecture Descriptor Schema

```python
NeuralArchitectureDescriptor(
    architecture_id: str,
    hidden_size: int,           # 8-64
    recurrent_density: float,   # 0.15-1.0
    plasticity_rate: float,     # 0.0-0.05
    plasticity_enabled: bool,
)
```

## Bounded Successor Variation

Variation occurs only during successor creation:
- Hidden size: delta in {-2, -1, 0, +1, +2}, probability 0.5
- Recurrent density: delta within ±0.10, probability 0.5
- Plasticity rate: delta within ±0.005, probability 0.3
- All values clamped to configured bounds
- Deterministic under stable_seed() + tick + index

## Dimension-Changing Transfer

- Expansion: preserves all overlapping elements, initializes new dimensions deterministically
- Contraction: selects retained indices deterministically, copies retained entries
- Recurrent mask remapped to match new dimensions
- All transfer is deterministic under same source state, descriptor, tick, and seed

## Recurrent Mask Representation

Binary mask of shape [hidden_size][hidden_size]. Forward pass applies: `(W_rec * mask) @ h_prev`. Inactive connections contribute zero. Mask density equals configured recurrent_density. Mask is created deterministically under seed.

## Processing Cost Equation

```
processing_cost = base_cost + hidden_unit_cost * hidden_size
                + recurrent_connection_cost * active_recurrent_connections
                + plastic_update_cost * changed_parameter_count (if plasticity enabled)
```

Default coefficients: base=0.05, hidden_unit=0.002, recurrent_conn=0.001, plastic_update=0.0005

## Fabrication Cost Equation

```
fabrication_cost = hidden_unit_fab_cost * successor_hidden_size
                 + connection_fab_cost * successor_active_connections
```

Default coefficients: hidden_unit=0.5, connection=0.02

## M14-M18 Regression Judge Results

| Milestone | Status |
|-----------|--------|
| M14 | PASS |
| M15 | PASS |
| M16 | PASS |
| M17 | PASS (12/12) |
| M18 | PASS (14/14) |

## M19 Judge Result

M19_JUDGE_STATUS: PASS (21/21 checks passed, 0 SKIP)

## Tests and Coverage

```
417 passed in 50.60s
```

## Artifact Paths

- `output/demo_m19/neural_architecture_run_summary.json`
- `output/demo_m19/neural_architecture_initial_descriptors.jsonl`
- `output/demo_m19/neural_architecture_transfer_trace.jsonl`
- `output/demo_m19/neural_architecture_distribution_trace.jsonl`
- `output/demo_m19/neural_architecture_cost_trace.jsonl`
- `output/demo_m19/neural_architecture_lineage_summary.json`
- `output/demo_m19/fixed_vs_variable_architecture_compare.json`

## Known Limitations

- Recurrent mask is binary; sub-density connections are either fully active or fully inactive
- Processing cost is per-decision and does not account for computational overhead of mask application
- Architecture variation only occurs at successor creation, not during unit lifetime

## Next Recommended Milestone

Milestone 20 — User-Owned Unattended Run Control and Basic Dashboard Preparation
