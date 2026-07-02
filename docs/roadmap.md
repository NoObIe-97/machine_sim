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
- Machine-native event logging
- Deterministic replay

## Milestone 4: Signal Correlation and Statistical Association ✓
- SignalCorrelator with bounded observation window
- Temporal association computation
- Per-pattern co-occurrence statistics
- Engine integration with correlation recording
- CLI correlation summary output
- Signal energy cost wiring fix

## Milestone 5: Adaptive Signal Response ✓
- LocalFieldTracker with bounded window statistics
- AdaptiveEmissionPolicy (interval, intensity, radius, pattern selection)
- AdaptiveScanPolicy (scan cadence)
- Improved association scores (lag-weighted, confidence, normalized rate)
- Engine integration with adaptive behavior tracking
- CLI adaptive summary output
- signal_energy_cost wiring fix

## Milestone 6: Reproduction and Design Inheritance ✓
- FabricationEngine with resource/placement constraints
- DesignTemplate with bounded variation
- LineageRecord tracking
- Population cap and dynamics
- FABRICATION_SUCCEEDED/FAILED events
- Fabrication summary artifacts

## Milestone 7: Calibration Assist and Knowledge Transfer ✓
- CalibrationCapsule with bounded source/world statistics
- CapsuleGenerator for deterministic capsule creation
- Warm-start application to successor units
- CapsuleManager for storage and summary
- Capsule artifact output (capsules.json)
- 8 new tests for capsule mechanics

## Milestone 8: Distributed Operational Memory
- Persistent memory across ticks
- Memory sharing via physical proximity
- Distributed consensus primitives
- Memory corruption and repair

## Milestone 5: Reproduction and Design Inheritance
- Unit replication (copy parameters + noise)
- Offspring placement
- Design inheritance with variation
- Population dynamics

## Milestone 6: Mutation and Lineage Divergence
- Parameter mutation during replication
- Lineage tracking
- Fitness-proportional selection pressure
- Lineage divergence and specialization

## Milestone 7: Calibration Assist and Knowledge Transfer
- Parent-like parameter calibration for offspring
- Experience capsule transfer
- Calibration refinement through feedback loops
- Knowledge accumulation across generations

## Milestone 8: Distributed Operational Memory
- Persistent memory across ticks
- Memory sharing via physical proximity
- Distributed consensus primitives
- Memory corruption and repair

## Milestone 9: Conflict/Cooperation Experiments
- Multi-unit resource competition scenarios
- Cooperative resource extraction
- Deception-like signaling
- Alliance-like coordination patterns

## Milestone 10: Observer-Level Affect Interpretation
- Observer-level interpretation engine
- Civilization pattern detection
- Emergent behavior classification
- Long-horizon experiment suite and replay analysis
