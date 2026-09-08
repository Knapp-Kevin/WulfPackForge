# UnityPy packaging and mod skill catalog

Status: Accepted, 2026-09-08

This note records two decisions for the optional game-icon and mod-support features. It does not
change the current application behavior.

## Keep UnityPy out of the standard Windows executable

### Decision

Keep the normal Windows release self-contained and UnityPy-free. If there is enough demand for
game-icon extraction in the packaged application, publish a separately named optional Windows
package built from the same release. Do not install Python packages on first use.

The optional package must be pinned, built, tested, and licensed as its own release artifact. The
standard package remains the default download.

### What the dependency costs today

`requirements-optional.txt` permits UnityPy 1.25.x. Resolving it for 64-bit Windows and CPython
3.12 on 2026-09-08 selected UnityPy 1.25.2 and eleven transitive wheels. The wheel files total
12.51 MiB compressed and 34.68 MiB unpacked. That is the input size, not a measured executable
delta; a Windows PyInstaller build is required for the release-size number.

The unpacked set includes roughly 14.08 MiB of Pillow, 10.69 MiB of `astc-encoder-py`, 4.39 MiB
of `etcpak`, and several smaller native packages. Both ASTC and ETC packages carry multiple SIMD
implementations. `fmod_toolkit` also carries an FMOD runtime DLL. WulfPackForge uses UnityPy for
textures and sprites, not texture encoding or audio, but those packages are mandatory transitive
dependencies in the current release.

### Packaging work

The current spec has no UnityPy hidden imports, binaries, data, or hook paths. A packaged build
would need project hooks for the dependencies that select native implementations at runtime, plus
explicit collection of their extension modules and DLLs. PyInstaller documents hooks as the way
to declare hidden imports, data, and binaries that static analysis cannot reliably find, including
the `collect_dynamic_libs` helper: [PyInstaller hook documentation](https://pyinstaller.org/en/stable/hooks.html).

Before publishing the optional package, its release job must:

- lock the complete Windows dependency set and verify hashes;
- collect and exercise the ASTC, ETC, Pillow, LZ4, Brotli, texture decoder, UnityPyBoost, and FMOD
  native payloads needed by the resolved packages;
- test icon extraction from representative user-supplied bundles on the supported Windows CPU
  range, not just launch the application;
- measure the actual artifact-size increase; and
- generate a dependency and licence inventory for the release.

### Why not download on first use

A PyInstaller executable is not a managed Python environment. Adding `pip` or an equivalent
installer creates mutable application state and introduces proxy, antivirus, interrupted-download,
package-index, and dependency-drift failures at the moment the user asks for the feature. Pinning
and verifying a downloadable helper would reduce those risks, but that helper is effectively a
second package with a more complicated installer.

A separate optional artifact makes the cost explicit, works offline after download, and can be
reproduced and tested in CI. Its trade-off is maintaining and explaining a second Windows download.
That is preferable to making every user carry native codecs they do not use or teaching the app to
modify its own runtime.

### Licence boundary

Most of the Python packages report permissive licences, but that does not remove the obligation to
ship their notices. More importantly, the FMOD DLL is governed by Firelight's terms rather than by
the MIT licence on its Python wrapper. The current FMOD EULA limits how the engine may be integrated
and redistributed and requires product attribution; use outside its grants needs a separate licence:
[FMOD legal information](https://www.fmod.com/legal).

Do not ship the optional artifact until the exact FMOD payload and WulfPackForge's distribution
case have been reviewed against those terms. If UnityPy later offers an image-only dependency extra
without audio and encoder packages, revisit this decision; that would reduce both the native hook
surface and the licence review.

## Retain the complete scanned skill identifier catalog

### Decision

Keep the current behavior: hash and retain every plausible identifier found during the selected
BepInEx profile scan. Do not filter `skills` to identifiers matching the character loaded at scan
time.

The catalog is workspace-local, plugin files are only read, and no plugin code runs. The reported
tens of thousands of JSON entries are untidy, but no measured storage or startup problem currently
outweighs the lookup coverage they provide.

### Resolution behavior

The catalog is applied at startup and supplies the Skills tab's `skill_id -> name` lookup. If a
later save contains a modded skill that was not present in the character used during the scan, the
complete catalog can label it immediately.

A save-filtered catalog would lose that identifier. The Skills tab could only resolve the new skill
by showing `Unknown (id)` until the user rescans the profile, or by silently reopening and rehashing
the plugin DLLs on a lookup miss. The first behavior is a regression; the second duplicates the
scanner, adds I/O during character loading, and still needs rules for a missing or changed profile.
Filtering also makes one workspace catalog depend on whichever character happened to be open when
the scan ran.

If catalog size becomes a demonstrated problem, optimize without changing its meaning. Candidates
include tightening the identifier predicate, using a more compact on-disk index, or retaining one
profile-level hash index shared by every character. Any such change should first record real catalog
sizes and load times and preserve deterministic resolution for skills added to future saves.
