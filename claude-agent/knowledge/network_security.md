# Network Security Best Practices for UniFi

## Network Segmentation

### Why Segment?
- Limit blast radius of security incidents
- Comply with regulatory requirements (PCI-DSS, HIPAA)
- Separate trust levels (IoT, Guest, Corporate)
- Improve network performance

### Recommended VLAN Structure

| VLAN ID | Name | Purpose |
|---------|------|---------|
| 1 | Management | Network infrastructure only |
| 10 | Corporate | Trusted workstations, servers |
| 20 | IoT | Smart devices, cameras |
| 30 | Guest | Visitor access |
| 40 | VoIP | Voice/video systems |
| 50 | Security | Cameras, access control |

**UniFi Path:** Settings > Networks > Create New Network

### Creating VLANs in UniFi

1. Navigate to Settings > Networks
2. Click "Create New Network"
3. Select "VLAN Only" or "Standard"
4. Assign VLAN ID
5. Configure DHCP range
6. Apply to appropriate ports/WiFi networks

## Firewall Rules

### Default-Deny Approach

**Principle:** Block everything, then explicitly allow needed traffic

**Recommended Rule Order:**
1. Allow established/related connections
2. Allow specific inter-VLAN traffic
3. Block IoT to Corporate
4. Block Guest to all internal
5. Allow internet access

### Essential Firewall Rules

```
# Allow established connections (implicit in UniFi)

# Block IoT to Corporate
Action: Drop
Source: IoT Network
Destination: Corporate Network

# Block Guest to all LAN
Action: Drop
Source: Guest Network
Destination: All RFC1918 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)

# Allow Corporate to IoT (for management)
Action: Accept
Source: Corporate Network
Destination: IoT Network
```

**UniFi Path:** Settings > Firewall & Security > Firewall Rules

### Traffic Rules vs Firewall Rules

**Traffic Rules:**
- Application-layer filtering
- Rate limiting
- QoS marking
- Per-client limits

**Firewall Rules:**
- Traditional L3/L4 filtering
- Inter-VLAN access control
- Port-based rules

## Wireless Security

### WPA3 Benefits

- SAE (Simultaneous Authentication of Equals) replaces PSK
- Forward secrecy (past sessions can't be decrypted)
- Protected Management Frames required
- Resistant to offline dictionary attacks

### PMF (Protected Management Frames)

**What it protects against:**
- Deauthentication attacks
- Disassociation attacks
- Management frame spoofing

**Configuration:**
- Required: For WPA3, all clients must support
- Optional: Clients that support PMF use it
- Disabled: Not recommended for any network

**UniFi Path:** Settings > WiFi > [Network] > Security > PMF

### RADIUS Authentication

**When to use:**
- Enterprise environments
- Individual user authentication needed
- Integration with Active Directory/LDAP

**Configuration:**
1. Settings > Profiles > RADIUS
2. Add RADIUS server (IP, port, secret)
3. Settings > WiFi > [Network] > Security
4. Select "WPA Enterprise"
5. Choose RADIUS profile

## IDS/IPS (Threat Management)

### UniFi Threat Management

**Capabilities:**
- Intrusion Detection System (IDS)
- Intrusion Prevention System (IPS)
- GeoIP filtering
- Known malicious IP blocking

**Sensitivity Levels:**
- Level 1: Lowest (fewer alerts, less blocking)
- Level 5: Highest (more aggressive, may cause false positives)

**Recommendation:** Start at Level 3, adjust based on alerts

**UniFi Path:** Settings > Firewall & Security > Threat Management

### GeoIP Filtering

**Use Cases:**
- Block traffic from high-risk countries
- Restrict access to specific regions
- Compliance requirements

**UniFi Path:** Settings > Firewall & Security > Country Restriction

## Guest Network Security

### Isolation Options

**Client Isolation:**
- Prevents guest clients from seeing each other
- Essential for guest networks

**Network Isolation:**
- Blocks access to other VLANs
- Default for guest networks

### Captive Portal

**Benefits:**
- Terms of service acceptance
- Usage tracking
- Bandwidth vouchers
- Social login integration

**UniFi Path:** Settings > WiFi > [Guest Network] > Guest Portal

## SSH/Management Security

### Best Practices

1. **Change default credentials** immediately after setup
2. **Enable SSH only when needed** for troubleshooting
3. **Use SSH keys** instead of passwords when possible
4. **Limit management access** to specific VLANs
5. **Enable 2FA** for UniFi application access

**UniFi Path:** Settings > System > Advanced

## Firmware Security

### Keep Firmware Updated

**Why:**
- Security patches
- Bug fixes
- New features

**Update Strategy:**
1. Check release notes before updating
2. Update non-critical devices first
3. Schedule updates during maintenance windows
4. Have rollback plan

**UniFi Path:** Devices > [Device] > Settings > Manage > Firmware

### Auto-Update Considerations

**Pros:**
- Always current on security patches
- Reduced administrative overhead

**Cons:**
- May introduce new bugs
- Unplanned downtime
- Feature changes without testing

**Recommendation:** Enable for small deployments, disable for enterprise
