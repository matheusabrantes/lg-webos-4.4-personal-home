# Device safety

Offline development and repository maintenance do not authorize device changes. Do not launch, stop, restart, install, remove, remap, or power-cycle anything on the TV as part of a repository check.

Before a new physical session, establish the exact target, preserve the original executable and configuration, identify the requested release, and obtain the owner's authorization for the concrete actions. Do not reuse historical approval JSON as authorization.

Keep the installed safeguards: original/release SHA-256 verification, trusted file ownership and permissions, process identity, mount-namespace checks, bounded native commands, explicit activation state, independent local recovery, and rollback records. Do not remove them to simplify setup or accelerate a failing test.

Do not overwrite firmware or system partitions. Do not remove unrelated LG services, alter DNS/firewall rules, modify playback settings, update applications, or change privacy configuration without the relevant scope and verification.

Separate the following claims:

- Compilation or a host fixture passed.
- The actual native scene rendered and accepted input.
- An application became foreground.
- A real video played with picture, sound, and subtitles where applicable.
- The original executable was restored.
- The original interface became usable again.

Use physical evidence for physical claims. If recovery fails, preserve that failure and its receipt. A later administrative rescue does not turn the original failure into an autonomous recovery pass.

When the owner ends testing so people can use the TV, stop disruptive work. Do not schedule or resume power, reboot, standby, fault, or stress tests without new authority.
