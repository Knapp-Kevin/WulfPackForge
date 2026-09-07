# Image Generation Index (original glyph set)

## Implementation status

- **Complete:** all 34 inventory glyph masters are approved, bundled under `assets/glyphs/items/`, mapped in `data/glyphs.py`, and rendered with material tinting in the Inventory grid and item editor.
- **Complete:** all 38 hairstyle and 27 beard thumbnails are bundled under `assets/glyphs/hair/` and `assets/glyphs/beard/`. The Appearance tab and New Character dialog load them automatically by catalog id.

Lists every original image the bundled glyph set needs so the batch can be generated in one pass. Nothing here derives from Iron Gate art; each glyph depicts the concept, in one consistent house style, and is keyed on data the item catalog already carries (`item_type`) plus a material tint inferred from the prefab name. See `docs/BRAND_GUIDE.md` for the product palette this extends.

## Prompt template (paste into the image generator, one glyph per request)

```
Flat vector game inventory icon of a {DEPICTS}, single centred object on a fully transparent background,
one dark charcoal outline, two-tone cel shading, light from the top left, cool slate grey material
(#7d7f83) with no colour tint, no text, no border, no background scene, no drop shadow, square 512x512,
silhouette must stay readable at 32 pixels. Norse-fantasy character editor style, clean and modern,
not photorealistic, not pixel art. Original design, not based on any existing game's art.
```

Generate item masters in grey; the app applies the material tint at load time. For hair and beard thumbnails use the second template below.

```
Flat vector schematic head-and-shoulders silhouette, front view, neutral face with no features, showing
the hairstyle "{STYLE NAME}" as a solid mid-grey hair mass on a dark charcoal head, transparent background,
one dark outline, no text, square 512x512, readable at 48 pixels. Norse-fantasy character editor style,
original design.
```

## House style (apply to every prompt)

- 64x64 target, authored at 512x512, transparent background, single centred object.
- Flat vector look with one dark outline and two-tone shading; no text, no backgrounds, no borders.
- Consistent light from top-left. Silhouette must read at 32 px.
- Palette: cool slate base; material tint applied only to the object's primary surface.

## Material tints (8)

| tint | hex | applies to prefab tokens |
|---|---|---|
| wood | #8a5a2b | Wood, FineWood, Yggdrasil, Root, Bow (unless metal) |
| stone | #7d7f83 | Stone, Flint, Obsidian |
| bronze | #b07a2a | Bronze, Copper, Tin |
| iron | #5c6068 | Iron, Blackmetal/BlackMetal (darker variant #2f3238) |
| silver | #c9d2dc | Silver, Frost, Crystal |
| bone | #e6dcc3 | Bone, Antler, Chitin, Carapace |
| flame | #d9531e | Flametal, Fire, Ashlands, Lava |
| eitr | #4fb3ff | Eitr, Mistlands, Dvergr, magic staves |

## Item silhouettes (23) with catalog coverage (selectable items, Valheim 0.221.12)

| glyph id | depicts | item_type(s) covered | count |
|---|---|---|---|
| G01 sword | one-handed straight blade | OneHandedWeapon (swords) | part of 90 |
| G02 axe | one-handed axe | OneHandedWeapon (axes), Tool (axes) | part of 90 |
| G03 mace | club or mace | OneHandedWeapon (clubs, maces) | part of 90 |
| G04 knife | dagger | OneHandedWeapon (knives) | part of 90 |
| G05 spear | spear | OneHandedWeapon (spears) | part of 90 |
| G06 greatsword | two-handed sword | TwoHandedWeapon | part of 58 |
| G07 battleaxe | two-handed axe | TwoHandedWeapon | part of 58 |
| G08 polearm | atgeir | TwoHandedWeapon | part of 58 |
| G09 sledge | two-handed hammer | TwoHandedWeapon | part of 58 |
| G10 staff | magic staff | TwoHandedWeapon, TwoHandedWeaponLeft | part of 59 |
| G11 bow | bow | Bow | 22 |
| G12 crossbow | crossbow | Bow (crossbow prefabs) | part of 22 |
| G13 arrow | arrow or bolt | Ammo, AmmoNonEquipable | 31 |
| G14 shield | round shield | Shield | 17 |
| G15 helmet | helmet | Helmet | 42 |
| G16 chest | chest armour | Chest | 52 |
| G17 legs | leg armour | Legs | 21 |
| G18 cape | cloak | Shoulder | 11 |
| G19 trinket | amulet or belt | Trinket, Utility | 25 |
| G20 ingot | material bar or lump | Material | 215 |
| G21 food | bowl or cooked item | Consumable, Fish | 116 |
| G22 trophy | mounted head plaque | Trophy | 60 |
| G23 torch | torch | Torch | 4 |

## Round 2 item silhouettes (11), complete

Bundled under `assets/glyphs/items/`, resolved by `data/glyphs.py`, and rendered with the same runtime material tinting as the first 23 masters.

| glyph id | depicts | prefabs |
|---|---|---|
| G24_bomb | round clay bomb with a short fuse | Bomb* (ooze, bile, smoke, blob, lava) |
| G25_pickaxe | pickaxe head on a handle | Pickaxe* |
| G26_hammer | one-handed building hammer | Hammer; Tool default |
| G27_hoe | hoe or cultivator, long handle | Hoe, Cultivator |
| G28_key | old iron key | CryptKey, DvergrKey, HildirKey_* |
| G29_egg | single egg | DragonEgg, ChickenEgg, AsksvinEgg, VoltureEgg |
| G30_misc | tied sack or bundle | Misc default: saddles, bell, barber kit, chests, serving tray |
| G31_tankard | drinking horn or tankard | Tankard* |
| G32_fishing | fishing rod with line, small bait tin | FishingRod, FishingBait* |
| G33_fist | clawed fist weapon | Fist* |
| G34_scythe | scythe | Scythe |

Customization (109) is not an inventory surface and needs no glyph. Modded prefabs with no catalog row fall back to G20 with the slate tint.

The 34 masters cover both item rounds. Each is tinted in code, avoiding separate rendered files for every material.

## Hairstyle thumbnails (38)

One original schematic head-and-shoulders silhouette per catalog hairstyle, same house style, saved as `assets/glyphs/hair/<id>.png`. Hair colour is applied in the app from the save's hair_color, so generate in mid-grey. Accuracy rule: the silhouette must match the in-game style's shape (length, braids, buns, parting, shaved sides), not just the name. The maintainer holds a private reference sheet rendered from the game's own meshes for the styles marked "mesh reference available"; the rest are generated from the name and in-game knowledge.

| id | name | reference |
|---|---|---|
| HairNone | No Hair | name only |
| Hair27 | Braids of Strength | mesh reference available |
| Hair34 | Castellan | name only |
| Hair35 | Champion | name only |
| Hair36 | Chronicler | name only |
| Hair7 | Dragonslayer | name only |
| Hair16 | Gathered Braids | mesh reference available |
| Hair31 | Gathered Locs | mesh reference available |
| Hair2 | High Ponytail | name only |
| Hair25 | Knot | mesh reference available |
| Hair6 | Long and Loose | mesh reference available |
| Hair11 | Long Braid | mesh reference available |
| Hair30 | Loose Waves | mesh reference available |
| Hair4 | Low Ponytail | mesh reference available |
| Hair12 | Matronly | mesh reference available |
| Hair28 | Merchant's Braid | mesh reference available |
| Hair32 | Mullet | name only |
| Hair17 | Neat Braids | mesh reference available |
| Hair9 | Old One-Eye | mesh reference available |
| Hair19 | Painter Curls | mesh reference available |
| Hair8 | Parted | mesh reference available |
| Hair3 | Pigtails | mesh reference available |
| Hair15 | Pulled Back Curls | mesh reference available |
| Hair18 | Royal Braids | mesh reference available |
| Hair24 | Shaved and Braided | mesh reference available |
| Hair5 | Short | mesh reference available |
| Hair23 | Short Curls | mesh reference available |
| Hair26 | Short Locs | mesh reference available |
| Hair10 | Side Swept | mesh reference available |
| Hair22 | Single Bun | mesh reference available |
| Hair14 | Speed Demon | mesh reference available |
| Hair37 | Sunbringer | name only |
| Hair20 | Tidy Curls | mesh reference available |
| Hair29 | Tucked Back | mesh reference available |
| Hair13 | Twin Braids | mesh reference available |
| Hair21 | Twin Buns | mesh reference available |
| Hair33 | Vinland Shave | name only |
| Hair1 | Windswept | mesh reference available |

## Beard thumbnails (27)

One silhouette per catalog beard, saved as `assets/glyphs/beard/<id>.png`. Beard shapes in the game are carried mostly by textures, so the mesh renders are not a useful reference; generate from the names with the following shape hints: Majestic (full, long, squared), Twin Braids (two braids from the chin), Short (close-cropped full beard), Straight (medium full beard combed straight down), Single Braid (one central chin braid), Loose Braid (loose chin braid), Split Shave (beard split down the middle), Thick (dense full beard), Trobadour (goatee with mustache), Top Braid (braid across the upper lip line), Facewarmer (very long full beard), Royal (long, groomed, pointed), Triplets (three braids), Split Braid (forked braid), Mini Braid (short single braid), Stonedweller (broad dwarf-style beard), Neat (short trimmed full beard), Jarl Braids (long with multiple ornamented braids), Bushy (wild full beard), Spiky (short beard with spiked chin), Tidy (neat short goatee), Mustache (mustache only), Crumb Catcher (mustache with small chin patch), Waxed (waxed handlebar mustache), Trimmed (stubble-length beard), Handlebar (handlebar mustache with short beard).

| id | name |
|---|---|
| BeardNone | No Beard |
| Beard19 | Bushy |
| Beard23 | Crumb Catcher |
| Beard11 | Facewarmer |
| Beard26 | Handlebar |
| Beard18 | Jarl Braids |
| Beard6 | Loose Braid |
| Beard1 | Majestic |
| Beard15 | Mini Braid |
| Beard22 | Mustache |
| Beard17 | Neat |
| Beard12 | Royal |
| Beard3 | Short |
| Beard5 | Single Braid |
| Beard20 | Spiky |
| Beard14 | Split Braid |
| Beard7 | Split Shave |
| Beard16 | Stonedweller |
| Beard4 | Straight |
| Beard8 | Thick |
| Beard21 | Tidy |
| Beard10 | Top Braid |
| Beard25 | Trimmed |
| Beard13 | Triplets |
| Beard9 | Trobadour |
| Beard2 | Twin Braids |
| Beard24 | Waxed |

## Output manifest

Approved files move to `assets/glyphs/` as original bundled art. Work in progress stays outside the runtime asset tree:

```
assets/glyphs/items/G01_sword.png ... G34_scythe.png   (masters, 512x512, untinted grey)
assets/glyphs/hair/Hair1.png ... Hair37.png, HairNone.png
assets/glyphs/beard/Beard1.png ... Beard26.png, BeardNone.png
```

The app maps prefab -> (glyph, tint) with a small rules table in `data/glyphs.py` and tints at load time. The complete hair and beard sets are picked up automatically from the paths above.
