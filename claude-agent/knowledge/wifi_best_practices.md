# WiFi Best Practices for UniFi Networks

## Channel Planning

### 2.4 GHz Band

**Recommended Configuration:**
- Use only channels 1, 6, or 11 (non-overlapping in North America)
- Channel width: 20 MHz only (avoid 40 MHz in dense environments)
- Transmit power: Medium or lower to reduce co-channel interference

**Why This Matters:**
- 2.4 GHz has only 3 non-overlapping channels
- Using other channels causes interference with neighbors
- Lower power reduces cell overlap and improves roaming

**UniFi Path:** Settings > WiFi > [Network] > Advanced > Radio (2.4 GHz)

### 5 GHz Band

**Recommended Configuration:**
- Prefer DFS channels (52-144) when radar is not a concern
- Channel width: 40 MHz for balance, 80 MHz only with few APs
- Enable band steering to push capable clients to 5 GHz

**DFS Channels:**
- 52, 56, 60, 64 (UNII-2A)
- 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144 (UNII-2C)
- Less congested, more available spectrum
- May experience radar events requiring channel change

**UniFi Path:** Settings > WiFi > [Network] > Advanced > Radio (5 GHz)

### 6 GHz Band (WiFi 6E/7)

**Recommended Configuration:**
- Use 160 MHz or 320 MHz channels for maximum throughput
- Requires WPA3 (no legacy WPA2 support)
- Ideal for high-bandwidth applications

**Key Points:**
- No legacy device support (clean spectrum)
- Lower range than 5 GHz
- Best for bandwidth-intensive use cases

## Security Settings

### WPA3 Configuration

**Recommended Settings:**
- Security Protocol: WPA3 Personal or WPA2/WPA3 Transitional
- PMF (Protected Management Frames): Required for WPA3, Optional for transitional
- Fast Roaming (802.11r): Enable for enterprise environments

**UniFi Path:** Settings > WiFi > [Network] > Security

### Guest Networks

**Best Practices:**
- Isolate on separate VLAN (e.g., VLAN 30)
- Enable client isolation (prevent client-to-client communication)
- Rate limit bandwidth (e.g., 25/10 Mbps per client)
- Restrict access to local network resources
- Consider captive portal for terms acceptance

**UniFi Path:** Settings > WiFi > Create New > Guest Network

### Hidden SSIDs

**Recommendation: Do NOT hide SSIDs**
- Security by obscurity provides no real protection
- Causes devices to probe for hidden networks (privacy issue)
- Can cause connectivity issues with some devices

## Roaming Optimization

### Fast BSS Transition (802.11r)

**When to Enable:**
- Enterprise WPA2/WPA3 environments
- VoIP/video applications requiring seamless roaming
- High-density deployments with many APs

**Caution:**
- Some older devices incompatible
- Test thoroughly before production deployment

**UniFi Path:** Settings > WiFi > [Network] > Advanced > Fast Roaming

### 802.11k/v

**802.11k (Neighbor Reports):**
- Provides APs list to clients for faster roaming decisions
- Reduces scan time during roaming

**802.11v (BSS Transition Management):**
- Allows APs to suggest better AP to clients
- Helps with load balancing

**Recommendation:** Enable both for modern networks

## Band Steering

### Purpose
Push dual-band capable clients to 5 GHz for better performance

### Configuration Options
- **Prefer 5G**: Gentle steering, falls back to 2.4 GHz
- **Strict**: Forces 5 GHz capable devices to 5 GHz only
- **Balance**: AI-driven decision based on conditions

**Recommendation:** Use "Prefer 5G" for most environments

**UniFi Path:** Settings > WiFi > [Network] > Advanced > Band Steering

## Minimum RSSI

### Purpose
Disconnect weak clients to force roaming to closer AP

### Recommended Values
- Aggressive: -75 dBm
- Moderate: -80 dBm
- Conservative: -85 dBm

**Caution:** Too aggressive settings can cause connection issues

**UniFi Path:** Settings > WiFi > [Network] > Advanced > Minimum RSSI

## AP Placement Guidelines

### General Rules
1. Mount APs on ceilings when possible (better coverage pattern)
2. Avoid placing behind metal objects or inside enclosures
3. Maintain line of sight to coverage area
4. Consider 30-50 feet between APs in office environments
5. Account for wall materials (drywall vs concrete vs glass)

### High-Density Environments
- Use more APs at lower power
- Prefer 5 GHz with 20/40 MHz channels
- Enable band steering aggressively
- Consider dedicated SSIDs for high-bandwidth use
