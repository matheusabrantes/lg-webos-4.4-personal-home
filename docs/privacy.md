# Privacy controls and publication

## Television controls

The privacy components aim to reduce unwanted promotions and optional tracking without removing essential television functions. They are firmware-specific tools, not a network-wide telemetry blocker.

Implemented controls cover optional advertising cookies, customized ads, Home promotions, Live Plus/ACR preferences, watched-list collection, voice and third-party-sharing preferences, and diagnostic log flags. Native agreement handling checks the firmware's agreement mapping before changing the supported optional documents.

The tools preserve backups, validate their ownership and permissions, and verify settings by readback. Essential agreement fields are preserved by the profile transaction. Their presence does not establish that every native service will honor the settings indefinitely.

The maintained sources are:

- [Diagnostic log controls](../src/personalhome/privacy-hardening-20261022/analytics_control.py).
- [Reversible privacy profile](../src/personalhome/finalization-20261022/privacy/profile_control.py).
- [Native agreement handling](../src/personalhome/finalization-20261022/privacy/authoritative_profile.py).
- [Startup flag helper](../src/personalhome/finalization-20261022/privacy/boot-candidate/boot-flags.js).

These links identify the implementation; they are not setup commands. Applying settings requires a separately authorized device session and the appropriate private backups.

## What the recorded evidence supports

Optional preferences and agreements were recorded as disabled. A later readback nevertheless reported `uploader.analyticsLog` enabled. Startup persistence and complete suppression of telemetry have not been established, and no zero-telemetry claim is made.

The [recorded status](status.md) separates those observations from playback, startup, and recovery results. This documentation update performs no device changes or new physical tests.

## Keeping owner data private

Personal wallpapers, raw screenshots, connection settings, SSH keys, firmware inputs, backups, and historical device evidence remain local. The `.local/` directory is excluded from Git.

The [repository ignore rules](../.gitignore) allow only individually named interface PNGs and the two reviewed README JPEGs. A newly created PNG in the application assets directory is ignored until its exact path is deliberately reviewed and allowed. Changing ignore rules does not remove content already committed.

Public images use generic network labels and omit personal photographs, including photographs that were visible through translucent controls. See [image provenance](assets/README.md). Do not add raw captures, account dialogs, storage listings with personal filenames, or metadata containing private identifiers.

Use GitHub's `noreply` address for commits. Changing Git configuration protects future commits; removing an address from existing commits requires rewriting their metadata as a separate, authorized operation. Private archives and recovery copies must remain private.
