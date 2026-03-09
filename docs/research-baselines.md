# Research Baselines For Architect Role

This file records external baselines used by the architect prompt/rubric.

## Sources

1. PEP 8 (official): line length baseline and team-flex rule (`79`, optional up to `99`).
   - https://peps.python.org/pep-0008/
2. Pylint all options (official):
   - `max-line-length` default `100`
   - `max-module-lines` default `1000`
   - `max-complexity` default `10`
   - `max-attributes` default `7`
   - `max-public-methods` default `20`
   - https://pylint.pycqa.org/en/stable/user_guide/configuration/all-options.html
3. ESLint max-lines rule (official): default `max = 300`.
   - https://eslint.org/docs/latest/rules/max-lines
4. Sonar cognitive complexity references:
   - Concept and method rationale: https://www.sonarsource.com/resources/cognitive-complexity/
   - Rule explanation page (S3776 family): https://rules.sonarsource.com/dart/RSPEC-3776
   - Sonar guidance article mentions default threshold `15` for S3776 in practice: https://www.sonarsource.com/blog/how-to-optimize-sonarqube-for-reviewing-ai-generated-code/
5. Import Linter layered architecture contracts (official):
   - https://import-linter.readthedocs.io/en/stable/contract_types.html

## How These Baselines Map To `rubric.json`

- `line_length.soft=100`: tuned for common Python tooling defaults while remaining close to PEP8 guidance.
- `line_length.hard=120`: stronger warning boundary for review noise control.
- `module_lines.soft=300`: aligned with ESLint's maintainability-oriented default.
- `module_lines.hard=1000`: aligned with Pylint default cap for oversized modules.
- `cyclomatic_complexity.soft=10`: aligned with Pylint McCabe default.
- `cyclomatic_complexity.hard=15`: aligned with stricter maintainability gating used in Sonar practices.
- `class_public_methods.soft=20`, `class_instance_attributes.soft=7`: aligned with Pylint design defaults as a practical encapsulation signal.

## Notes

- These thresholds are defaults, not universal truth.
- Keep per-project overrides in `rubric.json` instead of changing script logic.
- For non-Python repos, keep the same scoring schema but use language-specific linters for deeper checks.
