# Ablation Study Report

**Model**: gemma3:1b
**Timestamp**: 2026-01-19T14:21:44.383628
**Tasks**: 2
**Configurations**: 7

## Summary

### Component Contributions

| Config | Avg Time (s) | Avg Tokens | Ground Truth Match |
|--------|--------------|------------|-------------------|
| baseline | 10.9 | 740 | N/A |
| locality_only | 21.2 | 1460 | N/A |
| interference_only | 11.6 | 860 | N/A |
| dialectic_only | 10.2 | 740 | N/A |
| resonance_only | 9.9 | 740 | N/A |
| gradient_only | 11.5 | 860 | N/A |
| full | 21.3 | 1460 | N/A |

## Per-Task Results

### locality-001

**baseline**:
- Time: 11.7s
- Signals: 9
- Cultures: 1

**locality_only**:
- Time: 21.7s
- Signals: 27
- Cultures: 3

**interference_only**:
- Time: 13.2s
- Signals: 9
- Cultures: 1

**dialectic_only**:
- Time: 10.3s
- Signals: 9
- Cultures: 1

**resonance_only**:
- Time: 9.9s
- Signals: 9
- Cultures: 1

**gradient_only**:
- Time: 9.9s
- Signals: 9
- Cultures: 1

**full**:
- Time: 21.4s
- Signals: 27
- Cultures: 3

### locality-002

**baseline**:
- Time: 10.1s
- Signals: 9
- Cultures: 1

**locality_only**:
- Time: 20.8s
- Signals: 27
- Cultures: 3

**interference_only**:
- Time: 10.1s
- Signals: 9
- Cultures: 1

**dialectic_only**:
- Time: 10.1s
- Signals: 9
- Cultures: 1

**resonance_only**:
- Time: 9.8s
- Signals: 9
- Cultures: 1

**gradient_only**:
- Time: 13.0s
- Signals: 9
- Cultures: 1

**full**:
- Time: 21.2s
- Signals: 27
- Cultures: 3
