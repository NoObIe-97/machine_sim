# Guardrails

## Bias Firewall

### Banned in Runtime Logic
- Anthropomorphic: goal, desire, want, wish, intend, aim, motivation
- Emotional: love, hate, fear, anger, joy, sadness, happy, angry, afraid, mood, temperament
- Moral/ethical: moral, ethical, ethics, virtue, sin, guilt, shame, conscience
- Social: social, society, community, friend, enemy, ally, tribe, family, group
- Language: language, speak, word, sentence, communicate, talk, dialogue
- Consciousness: consciousness, awareness, aware, sentient, sentience, experience
- Institutional: law, crime, trade, commerce, economy, government, leadership
- Identity: personality, character, identity, ego

### Allowed (Machine-Native)
- learning, adaptation, model_update, correlation, prediction, optimization
- calibration, tuning, parameter_adjustment, weight_update, signal_processing
- pattern_recognition, gradient, reinforcement, memory_recall, state_estimation

## Three-Layer Defense

### Layer 1: Lexical Scan
Regex scan of non-test Python files for banned anthropomorphic terms.

### Layer 2: AST Check
Python AST parsing to detect forbidden assignments, class bases, and parameters.

### Layer 3: Runtime Validation
Validates state fields, component names, action names, event labels, config keys, memory labels.

## Scope
- Scans `sim/`, `agents/`, `environment/` directories
- Excludes `tests/`, `docs/`, `guardrails/`, `cli/` (infrastructure)
