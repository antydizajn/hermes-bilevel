# Experiment protocol

1. Lock datasets (train / selection / heldout).
2. Record purity registry hash + evaluator contract hash.
3. Import/validate candidates.
4. Evaluate in a labeled mode (replay/counterfactual/shadow/sandbox).
5. Compare with Pareto + statistics.
6. Emit dossier. Do not auto-promote.
