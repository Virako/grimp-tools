# grimp-tools — Claude guidance

## Design principles

When writing or refactoring code, keep these in mind:

- **GRASP**: assign responsibilities by role. Information Expert (the
  class with the data does the operation), Low Coupling, High Cohesion,
  Pure Fabrication when no domain class fits, Polymorphism over
  conditionals, Protected Variations behind stable interfaces.
- **SOLID**: Single Responsibility, Open/Closed (extend without
  modifying), Liskov substitution, Interface Segregation, Dependency
  Inversion (depend on abstractions, not concretions).
- **DRY**: factor shared logic into `config.py` / `graph.py`. New
  commands must reuse `load_root_packages`, `get_skip_modules`,
  `build_graph`, and `build_edge_set` instead of re-implementing.

Apply pragmatically — do not over-abstract. Three similar lines is
better than a premature abstraction.
