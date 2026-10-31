# Recorded device status

As of October 31, 2026, PersonalHome is permanently enabled on the recorded LG
49UK6310PSE running firmware 05.50.70, webOS 4.4.0 and Qt 5.6.2. Original LG
executable and configuration backups remain available to the recovery guards.

The owner confirmed that Power starting from a playing TV channel opens
PersonalHome first, without Live TV picture or sound, and with responsive controls.
Abrantesflix-button wake also passed. Native readback confirmed the expected wake
reasons, composed and focused Home, current activation, fresh guards and a
persistent startup hook without an expiry or disabled latch.

The latest full boot reached composed and focused Home. Cold first-image and
silent-start observations come from earlier packages with the same cold-stream
close implementation; the owner did not repeat those observations on the latest
package.

## Validation

| Check | Recorded result |
| --- | --- |
| Power from playing Live TV | Owner confirmed first Home, no TV picture or sound, and normal controls |
| Abrantesflix-button wake | Owner confirmed app picture and controls; native app foreground matched |
| Native Power controller | Five focused offline tests passed |
| Guard and cold-stream close | 67 guard cases and nine close cases passed on TV Node 0.12.2, with device operations mocked |
| Startup bridge and readiness service | 17 bridge tests, nine service tests and the joined protocol replay passed |
| Native compatibility | Changed QML compiled in memory on target Qt 5.6.2 without constructing a scene or window |
| Recovery | Original LG recovery was verified before the accepted installation; backups and guards remain available |
| Natural standby longer than one hour | Pending |

These results cover targeted startup and wake behavior on one TV. Long standby,
overnight stability and compatibility with other models or firmware remain
unverified. This work does not establish a startup-speed improvement or complete
application and playback coverage.

See [startup reliability](startup-reliability.md) for the implementation and
[device safety](device-safety.md) before using device tools. Raw session records,
personal captures and release-specific recovery state remain local.
