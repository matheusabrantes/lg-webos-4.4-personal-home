# Recorded device status

Last recorded device session: **October 23, 2026**. Repository migration: **October 31, 2026**. No live TV verification is performed by this migration.

PersonalHome was left enabled for provisional normal use at the owner's request. The recorded final state showed the native scene visible, directional focus active, 21 photos, and startup enabled. This is historical evidence, not a claim about the TV's current state.

Recorded successful checks included native navigation and pointer use, two controlled recovery cases with Abrantesflix, HDMI picture/sound and volume/mute, USB video/subtitles, Netflix playback, and a short stability observation after a real boot.

The following remain material limitations:

- Cold startup can be delayed and show the original LG interface before PersonalHome. No controlled boot-speed improvement was established.
- Complete recovery acceptance was not achieved. A later manual rollback restored the original executable but reported `usableInterface: false`; the earlier successful controlled cases do not erase that result.
- Optional privacy preferences and agreements were off, but `uploader.analyticsLog` was observed enabled in one readback. The project does not claim zero telemetry.
- Apple TV reached login by choosing the existing-version start option. It was not updated and complete Apple playback was not established.
- Overnight behavior, extended stability, and all remaining production-readiness gates were not completed.

A stale launch-error dialog was corrected before the provisional-use installation. Repository organization does not add new physical acceptance to that change.

Personal captures, raw logs, backups, release manifests, and historical authorizations are retained locally and excluded from GitHub. Treat their original timestamps and release identities as part of the evidence.
