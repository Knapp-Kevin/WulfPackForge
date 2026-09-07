# Wulfpack Forge Brand Guide

This guide keeps the product identity consistent across the application, README, releases, screenshots, and future UI work.

## Product hierarchy

Use the identity in this order:

**Wulfpack Forge**  
*Character Editor for Valheim*  
**by Frostwulf**  
*Based on VikingEditor by miskamero*

`Wulfpack Forge` is the product name. `Character Editor for Valheim` describes what the application does. `Frostwulf` is the creator identity. The VikingEditor lineage remains visible in documentation and attribution surfaces.

## Approved banner

Canonical repository asset:

`assets/wulfpack-forge-banner.jpg`

The banner establishes the visual direction: a frozen wolf, dark Norse-fantasy atmosphere, ice-blue illumination, dark charcoal/navy surfaces, silver highlights, and restrained warm ember accents.

The canonical raster is a **2048×682** progressive JPEG suitable for full-width README display. Do not replace it with a thumbnail or aggressively compressed derivative. Runtime validation confirms that the asset is bundled, non-trivial, and decodable; visual quality remains a human review responsibility rather than a pretend CI sharpness score.

Do not replace the approved banner casually or create competing product marks inside the repository.

## Application icon

Canonical repository asset:

`assets/FrostWulf-favicon.png`

The Frostwulf mark (white wolf head on an ice-blue compass ring, transparent background, 1254×1254) is the application icon. It is applied once at application level so every window and dialog inherits it, and it is the icon of the packaged executable through `assets/wulfpack-forge.ico`, which `tools/make_app_icon.py` generates from the PNG. Edit the PNG, re-run the tool, and commit both files together.

## README usage

The banner should appear across the top of the README before the product heading.

Keep the title/subtitle/byline in text beneath the image so the product remains accessible, searchable, and understandable even when images do not load. The README should reference the canonical repository asset directly rather than a separately compressed copy.

## Application usage

The application may use the banner or cropped portions of the approved imagery as a header or supporting visual element.

Rules:

- branding must not reduce editor readability;
- keep the main editing controls visually dominant after the header;
- preserve accessible names/descriptions for image-based elements;
- scale/crop rather than distort the wolf artwork;
- provide a text fallback if the image cannot be loaded;
- keep the visual treatment restrained enough that this remains a utility, not a game launcher.

### In-app inventory glyphs

Canonical inventory masters live in `assets/glyphs/items/`. They are original 512×512 transparent grayscale artwork, selected by item shape and catalog type, then tinted at runtime using the material palette in `data/glyphs.py`.

- keep silhouettes readable at the 56 px Inventory size and the 32 px design floor;
- preserve transparent backgrounds, one dark outline, and top-left two-tone lighting;
- use the neutral generic-material glyph for unknown items rather than blocking or rewriting them;
- keep item-art decisions strictly presentational;
- record approved asset hashes in `assets/glyphs/SHA256SUMS`;
- do not substitute extracted Valheim art, official logos, or VikingEditor branding.

The complete original hair and beard thumbnail sets live under `assets/glyphs/hair/` and `assets/glyphs/beard/`; approved asset hashes are recorded alongside the inventory masters in `assets/glyphs/SHA256SUMS`.

## UI direction

Preferred visual language:

- dark charcoal, navy, and near-black base surfaces;
- ice-blue or pale-cyan highlights;
- restrained metallic/silver separators;
- occasional warm ember/gold accent only when useful;
- strong contrast and legible controls;
- geometric/rune-inspired details used sparingly.

Do not sacrifice native platform clarity for decorative theming.

## Screenshots

README screenshots live in `docs/screenshots/` and should show the **actual current Wulfpack Forge UI**, not concept art or mockups. Capture them from a validated packaged or source build after the relevant UI tranche is stable, and refresh them when the visible product materially changes.

Prefer a small set of useful screenshots, such as the main character/status view, appearance editing, and inventory editing. Use synthetic or disposable character data, exclude personal filesystem paths and private character details, and make the visible state understandable to ordinary players. Screenshots should demonstrate the product rather than becoming a second gallery of decorative imagery.

## Typography

The banner artwork may use stylized display lettering. Application controls and documentation should use normal readable system/document fonts.

Do not require custom font installation for the desktop application.

## Naming consistency

Preferred forms:

- Product: `Wulfpack Forge`
- Executable: `WulfpackForge.exe`
- Windows package: `WulfpackForge-windows-x64.zip`
- Repository: `Knapp-Kevin/WulfPackForge`

Avoid reverting visible product surfaces to `VikingEditor`, `Valheim Character Save Editor`, or other temporary working names.

## Valheim and third-party marks

Wulfpack Forge is unofficial community software.

Do not use official Valheim, Iron Gate, Coffee Stain, Steam, or Valve logos in a way that implies sponsorship, endorsement, or official status.

The descriptive phrase `Character Editor for Valheim` is used to explain compatibility and purpose, not to claim ownership of the Valheim brand.

## Upstream attribution

Wulfpack Forge is derived from VikingEditor by miskamero. Preserve upstream attribution in the README, NOTICE/license context, and other appropriate distribution documentation.

Do not use the original VikingEditor name or logo as the primary branding for modified Wulfpack Forge distributions.
