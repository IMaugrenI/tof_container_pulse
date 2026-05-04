# Pulse Suite platform support

Pulse Suite is local, static, read-only, and advisory.

It does not change Docker, firewall rules, SSH settings, users, services, storage mounts, system settings, or security settings.

## Support levels

| Page | Linux | macOS | Windows |
| --- | --- | --- | --- |
| Container Pulse | Docker CLI | Docker CLI | Docker CLI |
| Hardware Pulse | deep collector | baseline adapter | baseline adapter |
| Port Pulse | `ss` / `netstat` | `netstat` | PowerShell / `netstat` |
| Storage Pulse | mount, inode, lsblk details | baseline volume usage | baseline volume usage |
| Services Pulse | configured checks | configured checks | configured checks |
| Security Pulse | deep local v0.3 collector | baseline safety orientation | baseline safety orientation |

## Linux

Linux remains the deepest supported platform.

Linux collectors can use:

- `/proc` for CPU, memory, uptime, and mounts
- `/sys/class/hwmon` and `/sys/class/thermal` for optional sensors
- `ss` or `netstat` for listening ports
- `lsblk` for storage orientation
- local security tools and files such as `ufw`, `firewall-cmd`, `fail2ban-client`, `systemctl`, `/etc/ssh/sshd_config`, and auth logs when readable

## macOS

macOS uses calm baseline adapters.

macOS collectors can use:

- `sysctl`, `df`, and `netstat`
- optional `psutil` if installed for better Hardware and Storage data
- macOS firewall status through `socketfilterfw` when readable
- FileVault status through `fdesetup` when readable
- SIP status through `csrutil` when readable
- current-user SSH permission hygiene without showing key names or contents

## Windows

Windows uses calm baseline adapters.

Windows collectors can use:

- PowerShell for listening ports and security visibility when available
- `netstat` fallback for listening ports
- drive usage from normal filesystem APIs
- optional `psutil` if installed for better Hardware and Storage data
- Windows Firewall profile visibility
- Microsoft Defender visibility when readable
- BitLocker visibility when readable
- current-user SSH permission hygiene without showing key names or contents

## Optional psutil

`psutil` is optional.

When installed, it improves cross-platform Hardware and Storage values on macOS and Windows.

Pulse Suite still runs without it and shows unavailable values as optional, unknown, or N/A instead of crashing.

## Privacy and safety boundaries

Pulse Suite avoids exposing sensitive details in screenshot-friendly pages.

It intentionally does not show:

- serial numbers
- UUIDs
- WWN values
- SSH key contents
- SSH key file names
- local user names in cross-platform security views
- sensitive file contents

It intentionally does not perform:

- external scans
- sudo/admin elevation
- auto-fix actions
- firewall changes
- SSH changes
- service restarts
- storage cleanup or repair
