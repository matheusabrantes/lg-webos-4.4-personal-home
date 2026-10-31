# LG webOS 4.4 PersonalHome

PersonalHome is an owner-specific native QML home interface for an LG webOS 4.4 TV. It integrates with the existing compositor rather than launching a separate browser app.

The interface provides remote and pointer navigation, installed-app shortcuts, a connected-network label, an input dropdown, a clock, and owner-supplied rotating wallpapers. The recovery code validates the original compositor, release hashes, process identity, and mount ownership before acting.

The last recorded device acceptance was provisional. Cold-boot delay and complete recovery acceptance remain unresolved. This repository does not claim a performance improvement or general compatibility with other TVs.

Personal photos, SSH keys, credentials, firmware dumps, device backups, and raw diagnostic captures remain local and are not published.

## Target and recorded status

The recorded device is an LG 49UK6310PSE running firmware 05.50.70, webOS 4.4.0, ARMv7, and Qt 5.6.2. Compatibility with another model or firmware must be established separately.

This repository migration does not connect to, restart, install anything on, or benchmark the TV. The on-screen interface remains in Brazilian Portuguese; repository documentation and new development history are in English.

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/personalhome/qml/` | Current interface, navigation logic, and non-personal assets |
| `src/personalhome/operations/runtime/` | Startup, validation, installation, and local recovery actors |
| `src/personalhome/operations/` | Release preparation, controlled-session tools, and runtime tests |
| `src/personalhome/integration/` | Firmware-specific integration builder and QML adapter |
| `src/personalhome/diagnostics/` | Isolated compatibility probes and diagnostic helpers |
| `src/personalhome/tests/` | Interface, integration, and recovery tests |
| `tools/` | Repository-level development helpers |
| `docs/` | Architecture, development, device safety, and recorded limitations |

Historical experiments and owner data are retained locally but excluded from Git. They are not an alternative supported installation path.

## Start with offline checks

Requirements: Python 3 and Node.js. These checks use fixtures and do not contact the TV:

```sh
node src/personalhome/operations/test_policy.js
node src/personalhome/operations/test_guard.js
python3 -m unittest discover -s src/personalhome/operations -p test_device_session.py -v
python3 src/personalhome/tests/test_recovery.py
```

UI preview and native builds require additional local inputs. See [development](docs/development.md). Do not run installation or physical-fault tools as setup steps.

## Device changes

Read [device safety](docs/device-safety.md) before using any device tool. Existing authorization records from historical sessions do not authorize a new session. Builds require the owner's matching firmware artifacts and release inputs; these are intentionally absent from a fresh clone.

See [architecture](docs/architecture.md), [recorded status](docs/status.md), and [contributing](CONTRIBUTING.md).
