# Local development

Keep the checkout outside Desktop and Documents. The owner uses `~/Developer/lg-webos-4.4-personal-home` so active source files are outside the iCloud-synchronized Documents location.

## Offline runtime checks

Run the four commands in the root README. The policy and guard JavaScript tests use mocked native operations. The Python session tests verify authorization and restart sequencing without device calls. The legacy recovery tests use temporary local files.

Other tests can require the owner's captured firmware, a matching release, PyQt5, or local wallpapers. Do not remove an integrity check or replace a missing device artifact with an arbitrary binary just to make those tests pass.

## UI preview

Use a local virtual environment for PyQt5. The recorded host setup used PyQt5 5.15.11; the TV runs Qt 5.6.2. A host preview is not a target-compatibility certification.

Supply your own wallpapers as `tv-02.jpg` through `tv-22.jpg` in `src/personalhome/qml/assets/`. The existing 21-image manifest intentionally excludes `tv-01.jpg`. Personal images are ignored by Git. Bundled fonts and application/control icons are already present; do not run historical asset-preparation scripts over them as an installation step.

Create `src/personalhome/qa/` for local preview output, then run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install PyQt5==5.15.11
mkdir -p src/personalhome/qa
.venv/bin/python src/personalhome/tools/run_preview.py
```

The preview uses local assets and does not connect to the TV. Full UI tests also require those assets. Asset conversion scripts additionally use FontTools and Brotli and retain references to the owner's historical input assets.

## Native build preparation

The integration builder is `src/personalhome/integration/build_candidate.py`; release assembly is in `src/personalhome/operations/build_release.py`. They depend on the exact original compositor, extracted matching QML/resources, and verified baseline manifests. Those private inputs are intentionally absent from Git. The dated local paths in the builders describe the recorded preparation environment, not a portable build recipe.

Read [architecture](architecture.md), [recorded status](status.md), and [device safety](device-safety.md) before preparing a new baseline. A fresh clone supports the documented offline checks and a locally configured preview; it cannot build or install a native release without the matching firmware inputs. No device connection or system executable overwrite is part of repository setup.

## Private device inputs

Keep SSH keys, known-host records, and connection settings under `.local/`. Never commit the actual connection settings or a private key. Device scripts require the exact matching firmware inputs and a new authorization appropriate to the requested action.

The shared transport is `tools/tv.py`; `work/abrantesflix/tv.py` is a relative compatibility symlink for existing imports. A fresh clone refuses to connect until a target is configured. Configure `PERSONALHOME_TV_HOST`, `PERSONALHOME_SSH_KEY`, and `PERSONALHOME_KNOWN_HOSTS`, or supply the owner's private `.local/device/config.json`. Strict host-key verification stays enabled. Configuration alone does not authorize a device operation.

Historical JSON files can reference temporary directories from October 2026. They are evidence, not portable defaults. Do not rewrite them to make an old release appear current. Prepare a fresh, verified baseline before a future release or physical session.

The migration preserves the previous local Git database and uncommitted changes under `.local/`. That archive is not pushed to GitHub because it contains historical device state and reports.
