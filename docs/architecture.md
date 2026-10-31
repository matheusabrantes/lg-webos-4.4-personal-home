# Architecture

PersonalHome is a QML scene integrated with the existing LG compositor. It is not a separate browser-based launcher and does not remove the compositor process.

`qml/PersonalHome.qml` contains the interface. `HomeLogic.js` and `InputLogic.js` implement navigation, labels, and input-list normalization. `PhotoBackdrop.qml` manages owner-provided wallpapers. `InputsController.qml` queries the native input and attached-storage services.

The integration adapter uses native launchpoints and application-manager helpers. An accepted launch request does not establish that an application rendered or that playback works. Update and login dialogs remain owned by their applications and the LG platform.

The runtime bootstrap verifies the release and original compositor, waits for native readiness, and coordinates one guarded activation restart. Its durable journal distinguishes preparation before the bind mount from an applying or verified transaction. Only a validated pre-bind interruption may retry on a later boot.

A silent first-app bridge covers startup until native Home composition and focus are verified through a nonce-bound readiness service. Cold startup closes the fresh, unmanaged broadcast stream when no real input app owns the lifecycle. Native Power handling reads the wake reason at `LastInput Ready`/`Screen On` and preserves app-button intent. See [startup reliability](startup-reliability.md).

Two local actors monitor identity, integrity, peer pulses, and interface health. Visible Home checks use the real Qt window/context and composition signals. When a native app is fullscreen, its independently verified foreground surface is relevant; a hidden Home timer is not video-frame or playback evidence.

Recovery removes only its own verified overlay and attempts to restore the original compositor and a usable context. Restoring the executable hash and restoring a usable foreground are separate results. Neither a live PID nor a progressing timer proves that the user can operate the TV.

Original LG resources, extracted executables, private wallpapers, and release-specific state are external inputs. The repository contains integration code, not a redistributable firmware image or a universal installer.

## Source layout

| Path | Purpose |
| --- | --- |
| `src/personalhome/qml/` | Interface, navigation logic, and non-personal assets |
| `src/personalhome/operations/runtime/` | Startup, validation, installation, and recovery actors |
| `src/personalhome/operations/` | Release preparation, controlled sessions, and runtime tests |
| `src/personalhome/integration/` | Firmware-specific integration builder and QML adapter |
| `src/personalhome/startup-bridge/` | Silent first-app cover, readiness service and offline tests |
| `src/personalhome/diagnostics/` | Isolated compatibility probes and diagnostic helpers |
| `src/personalhome/tests/` | Interface, integration, and recovery tests |
| `tools/` | Repository-level development helpers |
| `docs/` | Architecture, development, device safety, and recorded limitations |

Historical experiments and owner data are retained locally but excluded from Git. They are not an alternative supported installation path.
