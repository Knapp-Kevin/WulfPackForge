# Contributing to Wulfpack Forge

Thanks for helping improve Wulfpack Forge.

This project edits Valheim character saves, so contribution quality is measured by more than whether the UI appears to work. Changes must preserve data conservatively, make risk visible, and keep the player experience simple.

## Before you start

For substantial changes, check the open issues first. The durable product roadmap is tracked in [issue #2](https://github.com/Knapp-Kevin/WulfPackForge/issues/2).

Small bug fixes and documentation corrections can go directly to a focused pull request. Larger features should have an issue describing the problem, intended behavior, and validation plan.

## Development setup

```bash
git clone https://github.com/Knapp-Kevin/WulfPackForge.git
cd WulfPackForge
python -m pip install -r requirements.txt
python main.py
```

Run the automated suite with:

```bash
python -m unittest discover -s tests -v
```

Install the development tools and lint with:

```bash
python -m pip install -r requirements-dev.txt
python -m pyflakes main.py data subscripts ui tools tests
```

CI also runs the suite under `coverage` and fails below 85 percent line coverage of `data`, `subscripts`, `ui`, and `main.py`.

Compile-check the Python sources with:

```bash
python -m compileall data subscripts ui tools main.py
```

### Structural limits

`tests/test_razor.py` enforces the repository's simplicity limits:

- source files must not exceed 250 lines;
- functions must not exceed 40 lines;
- control-flow nesting must not exceed three levels;
- nested ternaries are prohibited;
- star imports are prohibited;
- no PySide6 imports under data/ or subscripts/ (the UI layer, main.py, and tests may import it)
- signal connections must not use lambdas that capture `self`.

Keep new code inside these limits instead of weakening the test. Run the Razor test directly with `python -m unittest tests.test_razor` when restructuring code.

### Qt and worker-test rules

Every test module that builds a Qt widget must derive its test classes from `tests.qt_support.QtTestCase`, which owns deterministic widget cleanup. If such a class defines `tearDown`, it must call `super().tearDown()`.

Tests that wait for a worker thread must use a real time deadline. Never wait for an arbitrary iteration count: machine and CI speeds vary, and a loop count turns scheduling luck into a test contract. Keep the timeout finite, process Qt events while waiting when required, and fail with enough context to identify the worker that did not finish.

## Branches

Use short-lived branches with descriptive names, for example:

- `fix/character-discovery-path`
- `feat/save-health-status`
- `docs/steam-cloud-guidance`

Do not develop directly on `main` unless the change is intentionally trivial and repository policy permits it.

## Core safety invariants

Changes touching save loading or writing must preserve these rules:

1. Do not write a character save while Valheim is running.
2. Do not overwrite the destination before a candidate save has been generated and verified.
3. Validate the save envelope and SHA-512 checksum.
4. Reparse generated saves before replacement.
5. Back up an existing destination before replacement.
6. Use atomic replacement after successful verification.
7. Leave the existing destination untouched when verification fails.
8. Preserve unknown or modded data unless the user explicitly changes it.
9. Do not silently claim compatibility with a Valheim version that has not been tested.

A pull request that weakens one of these invariants must explain why and include replacement safeguards. Convenience alone is not sufficient justification.

## Item catalog changes

The generated catalog and curated write constraints have different responsibilities.

- `data/valheim_items.json` supplies discoverability and source-version metadata.
- `data/items.py` contains curated safety constraints and resolution behavior.
- Catalog refreshes must not silently change stack, quality, or variant rules.
- Unknown and modded prefabs must remain editable through the raw-ID path.

When refreshing the catalog, pin the expected Valheim version and inspect the generated diff for unexpected removals, duplicates, and source drift.

Regenerate the two versioned data tables with:

```bash
python tools/update_item_catalog.py --expected-version 0.221.12
python tools/update_item_durability.py
```

## User experience standards

Wulfpack Forge is player-first software.

Prefer:

- human-readable labels;
- clear recovery instructions;
- safe defaults;
- one obvious primary action;
- advanced escape hatches that do not clutter the normal path.

Avoid requiring players to understand Python, Git, prefab internals, Steam directory layouts, or save serialization when the application can safely handle those details for them.

## Documentation

Behavior changes should update documentation in the same pull request when relevant.

At minimum, review:

- `README.md` for player-visible behavior;
- `CHANGELOG.md` for user-facing changes;
- `SUPPORT.md` for troubleshooting changes;
- `GOVERNANCE.md` when policy, compatibility, or release gates change.

## Pull requests

A good pull request includes:

- the user problem being solved;
- the implementation boundary;
- tests added or changed;
- any save-integrity or compatibility risk;
- documentation updates;
- screenshots only when they materially help review UI changes.

Keep changes focused. Mixing unrelated cleanup with save-format changes makes review harder for no useful reason.

## Validation expectations

At minimum, pull requests should pass the normal test workflow. Changes affecting packaging must also pass the Windows packaged-app smoke test.

Save-format or compatibility changes may require manual validation with disposable characters before release. See [GOVERNANCE.md](GOVERNANCE.md).

## Attribution and licensing

Wulfpack Forge is derived from VikingEditor by miskamero and is distributed under GPLv3. Contributions must be compatible with the repository license and preserve required attribution.

By submitting a contribution, you agree that it may be distributed under the repository's GPLv3 license.
