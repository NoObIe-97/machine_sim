# Roadmap

## Milestone 1: Survival Substrate ✓
- Executable simulation with tick loop
- Machine-native units with hardware variants
- Resource pressure, survival/degradation mechanics
- Event logging, deterministic runs
- Guardrail enforcement, basic tests

## Milestone 2: Interaction Substrate ✓
- Unit-unit proximity detection
- Occupancy-aware movement
- Collision/movement-denial mechanics
- Local spatial pressure metric
- Machine-native event logging

## Milestone 3: Non-Semantic Signaling ✓
- Signal emission (EMIT_SIGNAL action)
- Signal propagation with bounded radius
- Signal decay and expiration
- Signal sensing by nearby units (source excluded from own signal)
- Energy cost for emission
- Deterministic replay

## Milestone 4: Signal Correlation and Statistical Association ✓
- SignalCorrelator with bounded observation window
- Temporal association computation
- Per-pattern co-occurrence statistics
- Engine integration with correlation recording
- CLI correlation summary output

## Milestone 5: Adaptive Signal Response ✓
- LocalFieldTracker with bounded window statistics
- AdaptiveEmissionPolicy (interval, intensity, radius, pattern selection)
- AdaptiveScanPolicy (scan cadence)
- Lag-weighted association scores with confidence and normalized rate
- Engine integration with adaptive behavior tracking

## Milestone 6: Fabricated Descent and Design Inheritance ✓
- FabricationEngine with resource/placement constraints
- DesignTemplate with bounded variation
- LineageRecord tracking
- Unit capacity and lineage dynamics
- FABRICATION_SUCCEEDED/FAILED events

## Milestone 7: Calibration Assist and Parameter Transfer ✓
- CalibrationCapsule with bounded source/world statistics
- CapsuleGenerator for deterministic capsule creation
- Warm-start application to successor units
- CapsuleManager for storage and summary

## Milestone 8: Distributed Operational Telemetry ✓
- Persistent telemetry frames across ticks
- Proximity-based reconciliation
- Divergence and continuity metrics
- Lineage drift tracking

## Milestone 9: Resource Pressure Analysis ✓
- Resource pressure cells and depletion rate
- Extraction load and peak cell load
- Proximity pressure and blocked-motion rate
- Field perturbation scoring

## Milestone 10: Signal Pattern Field Dynamics ✓
- Pattern-indexed field dynamics
- Signal clustering and gradient exposure
- Observer-level interpretation surface

## Milestone 11: Bounded Operational Trace Compression ✓
- TraceCompressor with bounded segment count
- Compression ratio reporting
- Replay-stable compressed segments

## Milestone 12: Multi-Generation Trace Drift and Compression Stability ✓
- Generation-indexed trace drift
- Capsule compatibility across generations
- Compression stability under drift

## Milestone 13: Compressed Summary Cross-Unit Consistency ✓
- Cross-unit consistency scoring
- Combined stability score
- Summary consistency analyzer

## Milestone 14: Long-Run Internal Adaptive Control ✓
- 20000-tick 120x120 adaptive control runs
- AdaptiveController with local feedback
- Long-run adaptation summary and exact-PASS judge

## Milestone 15: Multi-Generation Adaptive Trace Evolution ✓
- Adaptive state transfer to successors
- Generation span tracking
- Descendant adaptive state traces

## Milestone 16: Adaptive Trajectory Compression and Offline Analysis ✓
- Adaptive trajectory compression with bounded segments
- Replay-stable offline analysis
- Compression ratio 0.695 on the primary run

## Milestone 17: Internal Neural Processing Unit ✓
- Compact recurrent controller with local plasticity
- Deterministic seeding through stable_seed()
- Neural-versus-scalar comparison
- Strict exact-PASS-only judging (M17A, M17B)

## Milestone 18: Neural Controller Variant Sensitivity ✓
- 6-variant controller sweep
- Variant similarity matrix
- Controller parameter sensitivity summary
- Per-variant runtime validation (M18A)

## Milestone 19: Successor-Transferred Neural Architecture Variation ✓
- Per-unit neural architecture descriptors
- Bounded successor architecture variation
- Dimension-changing neural-state transfer
- Sparse recurrent connection masks
- Architecture-dependent processing and fabrication cost
- Fixed-versus-variable architecture comparison

## Milestone 20: User-Owned Unattended Run Control ✓
- Schema-versioned run lifecycle manifest with atomic writes
- Deterministic dependency-free checkpoint capture and restore
- Checkpoint integrity digests and an explicit validator
- File-based user-owned control channel (pause, stop)
- Resume from checkpoint in a separate process
- Per-tick digest chain and continuation-equivalence verification
- Read-only local status surface and artifact location index

## Milestone 21: Unattended Multi-Hour Architecture Run (next)
- Multi-hour architecture run over the M20 checkpoint substrate
- Interruption and resumption across long wall-clock spans
- Post-run trajectory analysis over retained checkpoints
- Bounded artifact growth over extended runs
