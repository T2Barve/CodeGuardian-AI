# Static Analysis Scanner Configuration & Rulesets

This directory contains rule configurations, ignore lists, and adapter specifications for CodeGuardian's deterministic SAST engines:

- `semgrep/`: Custom Semgrep YAML rules for multi-language security patterns.
- `bandit/`: Python-specific AST security analyzer configurations.
- `gitleaks/`: Gitleaks regex rules and entropy thresholds for high-entropy secret detection.
- `eslint/`: Security and code quality rules for TypeScript / JavaScript.
