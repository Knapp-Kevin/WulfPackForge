# Governance

Wulfpack Forge is a small community project with one primary maintainer, but save-editing software still benefits from explicit rules. This document defines who decides, what must be protected, and what evidence is required before a change is treated as releasable.

## Maintainer authority

The repository owner, `Knapp-Kevin`, is the current project maintainer and final decision-maker for scope, architecture, release readiness, compatibility claims, branding, and contribution acceptance.

The maintainer may delegate review or implementation work, but delegation does not transfer final release authority.

## Project scope

Wulfpack Forge exists to provide a simple, safe, player-first Valheim character editor.

In scope:

- character appearance editing;
- inventory editing;
- supported skills;
- character metadata;
- local discovery of Valheim character files;
- safe save verification, backup, and replacement;
- packaging and release tooling required for a normal desktop-user experience.

Out of scope unless explicitly approved:

- editing live game memory;
- bypassing platform security controls;
- remote Steam Cloud access that relies on unsupported or private interfaces;
- claiming official affiliation with Iron Gate Studio, Coffee Stain Publishing, or Valve;
- weakening save-safety behavior solely for convenience.

## Safety invariants

The following are release-level invariants:

1. Valheim must not be running when Wulfpack Forge writes a character save.
2. Save candidates must be produced separately from the destination.
3. Generated candidates must pass strict envelope and checksum validation.
4. Generated candidates must be reparsed before replacement.
5. Existing destinations must be backed up before replacement.
6. Replacement must occur atomically after verification.
7. Verification failure must leave the existing destination untouched.
8. Unknown or modded data should be preserved unless the user explicitly changes it.
9. Compatibility claims must be backed by evidence for the stated Valheim version.

Changes to these invariants require an explicit governance update and a documented rationale in the pull request.

## Compatibility policy

Wulfpack Forge distinguishes between three states:

- **Verified:** tested against the stated Valheim build with appropriate automated and, when required, in-game evidence.
- **Expected compatible:** no known format break, but full validation for the new build has not yet completed.
- **Unknown:** insufficient evidence exists to make a compatibility claim.

The README and releases must not collapse these states into a generic "supported" claim.

Major Valheim releases require deliberate compatibility review. For Valheim 1.0, the release gate is tracked in issue #2 and includes real `.fch` load, no-op round trip, appearance edit, inventory edit, backup/replacement behavior, and in-game acceptance.

## Item catalog governance

Catalog discovery data and write constraints are separate policy surfaces.

A generated catalog refresh may update names, item presence, item type, asset metadata, and source-version metadata. It must not silently alter curated stack, quality, or variant constraints.

Constraint changes require focused tests and review because they affect what values Wulfpack Forge may write into a save.

## Release gates

A normal release candidate must satisfy the following as applicable:

- source compilation succeeds;
- automated tests pass;
- packaged Windows build succeeds;
- packaged executable smoke test succeeds;
- required runtime assets are present in the package;
- user-facing documentation matches actual behavior;
- compatibility status is accurate;
- save-format changes have the required real-save validation;
- GPLv3 and upstream attribution remain intact.

A release should not be published because a deadline exists. Dates are scheduling information, not evidence.

## Change review

Pull requests should be reviewed according to risk.

Low risk:

- documentation corrections;
- wording changes;
- nonfunctional branding changes.

Moderate risk:

- UI behavior;
- discovery paths;
- catalog resolution;
- packaging changes.

High risk:

- save parsing;
- save serialization;
- write constraints;
- backup/replacement behavior;
- compatibility claims.

Higher-risk changes require proportionally stronger tests and validation.

## Upstream relationship

Wulfpack Forge is a derivative of VikingEditor by miskamero. This repository is developed as its own product surface. Work is not submitted upstream unless the maintainer explicitly chooses to do so.

Upstream attribution and GPLv3 obligations remain in force regardless of whether a Wulfpack Forge change is intended for upstream submission.

## Decision records

Small implementation decisions may live in issues and pull requests. Changes to core safety invariants, compatibility policy, release gates, or project scope should update this document or be captured in a dedicated architecture/governance document before release.

## Amendments

The maintainer may amend this governance model through a reviewed repository change. Governance text must match actual project behavior. A rule that exists only in prose and is routinely ignored is decorative, and decorative governance is not governance.