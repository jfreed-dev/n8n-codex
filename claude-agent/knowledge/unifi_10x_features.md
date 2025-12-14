# UniFi Network Application 10.x Features

## Overview

UniFi Network Application 10.x represents a major update to the UniFi ecosystem, introducing enhanced API capabilities, improved user experience, and new security features.

## New Features in 10.0.x

### Official Network API Improvements (10.0.160+)

The Integration API has been significantly expanded:

- **Devices**: Retrieve unadopted devices and adopt new ones programmatically
- **Networks (VLANs)**: Create and manage VLANs via API
- **ACLs**: Create and manage Access Control Lists
- **Supporting APIs**:
  - Retrieve country list
  - Retrieve application list (DPI apps)
  - Retrieve WANs
  - Retrieve VPN Servers
- Improved API filtering options and error reporting

### Network Configuration

- Added support for DS-Lite over PPPoE
- Added Additional IPs option to IPv4 VLAN Network Settings
- Added Stats option to Port Manager when viewing All Ports
- Added Remove and Pause actions in Policy Table side panels
- Added remote subnet overlapping validation for all Site-to-Site VPNs

### User Interface Improvements

- Improved WiFi, Hotspot, Network, and Internet settings UX
- Enhanced device management interface
- Better visualization of network topology

## System Requirements

- Requires UniFi OS 4.4.6 or newer
- Supported on UDM, UDM Pro, UDM SE, UDM Max, and Cloud Key Gen2+
- Minimum 2GB RAM recommended for larger deployments

## API Endpoints Reference

### Integration API (Read-Only with X-API-KEY)

Base URL: `https://{controller}/proxy/network/integration/v1/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sites` | GET | List all sites |
| `/sites/{id}/devices` | GET | List devices for a site |

### Local Controller API (Full Access with Cookie Auth)

Base URL: `https://{controller}/proxy/network/api/s/{site}/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stat/health` | GET | Site health metrics |
| `/stat/device` | GET | Detailed device statistics |
| `/rest/networkconf` | GET/POST | Network/VLAN configuration |
| `/rest/wlanconf` | GET/POST | Wireless configuration |
| `/rest/firewallrule` | GET/POST | Firewall rules |
| `/rest/setting` | GET | Site settings |

## Release Notes Summary

### Version 10.0.162 (December 2025)
- Bug fixes and stability improvements
- Security patches

### Version 10.0.161
- Performance optimizations
- Minor UI fixes

### Version 10.0.160
- Extended Official API capabilities
- Improved settings UX
- DS-Lite over PPPoE support

### Version 10.0.156
- Initial 10.x stable release
- New network configuration options
- API improvements
