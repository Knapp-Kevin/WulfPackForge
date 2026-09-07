# Agent Instructions

This repository may be maintained with AI-assisted development. Agents working here are expected to follow the same evidence, safety, and governance standards as human contributors.

## Start here

Before changing code, read:

1. `README.md`
2. `GOVERNANCE.md`
3. `CONTRIBUTING.md`
4. the relevant open issue, especially issue #2 for roadmap work
5. tests covering the area being changed

## Product boundary

Wulfpack Forge is the product. `miskamero/VikingEditor` is the upstream lineage, not the active implementation target.

Do not submit changes upstream, open upstream issues, or contact the upstream maintainer unless the repository owner explicitly requests it.

## Safety rules

Agents must preserve the save-safety invariants in `GOVERNANCE.md`.

Changes that touch parsing, serialization, write constraints, backup behavior, atomic replacement, or compatibility claims are high risk. Add or update tests before treating the work as complete.

Do not weaken a safety check merely to make a failing test or UI path pass.

## Evidence discipline

Prefer this order of evidence:

1. current tests and reproducible runtime behavior;
2. current source code;
3. versioned repository documentation and issues;
4. external documentation when game/platform behavior must be established.

Do not present planned behavior as implemented behavior.

## Development workflow

- Work on a focused branch.
- Keep issue #2 or the relevant issue current as milestones land.
- Add tests for behavioral changes.
- Update README/support/governance documentation when user-visible or policy behavior changes.
- Run source tests before opening a PR.
- Keep every source file at or below 250 lines, every function at or below 40 lines, and control-flow nesting at or below three levels; do not use star imports or import PySide6 outside `ui/`. `tests/test_razor.py` enforces these limits.
- Require the Windows packaged-app workflow for changes affecting assets, packaging, runtime imports, or bundle behavior.
- Merge only after the required evidence is green.

## Player-first UX

The normal player should not need Python, Git, prefab expertise, or Steam directory knowledge.

Prefer simple primary actions, human-readable labels, safe defaults, and clear recovery guidance. Keep advanced/raw controls available when they are necessary to preserve modded or unknown data.

## Branding

Use **Wulfpack Forge** as the product name, **Character Editor for Valheim** as the descriptive subtitle, and **by Frostwulf** as the creator line.

Preserve the statement that Wulfpack Forge is based on VikingEditor by miskamero. Do not imply affiliation with Iron Gate Studio, Coffee Stain Publishing, Valve, or Steam.

The approved banner lives at `assets/wulfpack-forge-banner.jpg`. See `docs/BRAND_GUIDE.md` for usage rules.

## Documentation standard

Documentation must be current, user-centered, and verifiable. Commands, paths, filenames, compatibility claims, and release behavior should be checked against the current branch before writing them.

Do not let documentation drift become a separate future chore. If the code changes the user's reality, update the relevant documentation in the same tranche.
