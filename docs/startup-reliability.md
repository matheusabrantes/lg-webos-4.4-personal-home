# Startup reliability

PersonalHome uses the existing LG compositor on the recorded webOS 4.4 target.
The startup correction preserves guarded recovery while bringing Home to the
foreground on ordinary Power and leaving app-button wake to the selected app.
See [recorded status](status.md) for the physical checks and their limits.

## Startup and recovery

The bootstrap verifies the release, original executable, process identity and
mount ownership before activation. Its journal distinguishes `prepared`,
`applying` and `verified`. Only a validated `prepared` record from before the bind
mount can retry on a later boot; ambiguous or incomplete compositor changes fail closed.

A silent, opaque `com.personalhome.startup` web app covers the native first-app
phase. The owned boot configuration changes only
`common.firstApp.firstAppInNormal` and the `remoteKey`/`localKey` targets in
`/var/luna/preferences/bootd.json`. App-key mappings, including Abrantesflix,
retain native handling.

Activation still uses one guarded compositor restart after native readiness.
Before replacement, a durable, checked `general.lastInputApp` transaction directs
SAM's fresh last-input enquiry to the bridge. The candidate's bounded
`forceMinimize` hold covers an empty surface during startup. The transaction
restores the real input after acceptance or recovery and preserves foreign
changes; `physicalLastInputApp` stays unchanged.

Cold boot can leave a reserved TV stream playing without a Live TV application
or an ACB context. In that case the root guard obtains the fresh boot broadcast ID,
checks its native state and conflict status, and closes only that stream through
`com.webos.service.utp.broadcast/close`. Acceptance requires the matching native
invalid-ID readback; transport and permission failures remain failures. The normal
TV launch opens a fresh stream. Global volume and mute settings are preserved.

Home acceptance requires the actual Qt window/context, a composed frame and
focus. The bridge subscribes to `com.personalhome.startup.service/subscribe`; the
native controller or guard acknowledges the current pending cycle through
`/ready` with the release nonce. Acknowledgement does not launch or activate an
application. The black bridge never qualifies as a usable final interface.

The bridge's 75-second watchdog falls back once to Live TV and records a
release-specific disabled latch. Explicit hide pauses the timer and subscription
without setting that latch. Explicit show resumes an unacknowledged cycle without
activating the bridge; an accepted cycle does not rearm on later show. The timeout
also checks for a missed hide event. Unknown visibility keeps the foreground
black-screen fallback.

Two guards monitor identity, integrity, peer pulses and usable presentation.
Recovery removes only the verified owned overlay, restores owned startup settings
and checks the original LG interface or a usable native app. Foreign settings are
preserved. Since bootd reads its override at construction, restoring that file
takes effect on a later fresh boot; the bridge's fallback also protects the current
session. Small rotated logs retain activation and recovery outcomes.

## Native behavior addressed

Matching shipped QML, bounded ARM disassembly and device probes established these
requirements:

- Read the Power wake reason at `LastInput Ready`/`Screen On`. Earlier reads can
  return `other`; native callbacks also cover transitions missed by polling.
- Treat Home as an idempotent request while PersonalHome is already shown. Native
  startup and inactivity timers must preserve a healthy visible custom Home.
- Pause an existing Live TV surface through its native minimize, deactivate and
  ACB Background/Paused lifecycle. Explicit TV selection resumes normal playback.
- Handle a cold reserved stream separately. Broadcast pause alone unrealized
  video but left audible TV sound; full native close performs resource teardown.
- Deliver readiness through a service subscription. On this TV,
  `launchHidden:true` still foregrounded the bridge and hid Home.

No firmware or boot partition is modified. The integration remains specific to
the matching LG resources and release inputs; they are not included in the public
repository.

## Validation and remaining work

Five focused native-controller tests passed. The latest TV Node 0.12.2 run passed
67 guard and nine cold-close cases with device operations mocked. The bridge and
readiness service passed 17 and nine tests respectively, plus their joined protocol
replay. Changed QML compiled in memory on target Qt 5.6.2 without creating a scene
or window.

The owner confirmed Power from playing TV and Abrantesflix-button wake on the
accepted installation. Its latest full boot reached native composition and focus;
cold first-image and silence observations were confirmed on earlier packages with
the same close behavior and were not repeated by the owner on the latest package.

Natural standby longer than one hour and overnight stability remain pending.
A native foreground surface does not establish application playback or DRM
compatibility. Retain recovery logs and the disabled record if fallback occurs.
