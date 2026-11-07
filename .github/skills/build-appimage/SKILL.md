---
name: build-appimage
description: "Use when building, releasing, or republishing a new Umbriel Settings AppImage: bumping the <Umbriel version>-<revision> version, running appimage/build-appimage.sh, testing the result, and updating the GitHub release."
---

# Build and release an Umbriel Settings AppImage

## Version scheme

`__version__` in `python/umbriel_config_gui/__init__.py` is `<Umbriel version>-<NNN>`, for example `0.1.0-001`.

- New GUI build for the same Umbriel version: increment `NNN` (`001` -> `002`).
- New Umbriel version (check `umbriel --version`): use it and reset `NNN` to `001`.

This single value is used by `--version` and by the AppImage file name.

## Steps

1. Bump `__version__` as described above.
2. Build: `appimage/build-appimage.sh` (needs network, `python3` with `venv`, FUSE or `APPIMAGE_EXTRACT_AND_RUN=1`). Output: `dist/Umbriel-Settings-<version>-<arch>.AppImage`.
3. Test: `dist/Umbriel-Settings-<version>-<arch>.AppImage --appimage-extract-and-run --version` must print the new version. The image must contain `usr/share/licenses/Umbriel-Settings/LICENSE`.
4. Commit the version bump, then `git push origin main`.
5. Tag and release (tag is `v<version>`):
   ```sh
   git tag v<version> -m "v<version>" && git push origin v<version>
   gh release create v<version> dist/Umbriel-Settings-<version>-<arch>.AppImage \
     --title "v<version>" --notes "<what changed>"
   ```
6. Remove superseded AppImages from `dist/`; `dist/` is git-ignored.

## Rules

- Do not force-push, delete tags, or replace an existing release's assets unless the user asks.
- Ask before pushing, tagging, or publishing if the user has not requested a release.
