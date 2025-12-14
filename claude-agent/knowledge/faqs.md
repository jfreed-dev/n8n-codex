# UniFi Network Frequently Asked Questions

## General Questions

### What is the difference between UniFi and AmpliFi?

**UniFi** is Ubiquiti's prosumer/enterprise line designed for scalability and advanced features. It uses a centralized controller (UniFi Network Application) and offers granular control.

**AmpliFi** is Ubiquiti's consumer mesh WiFi system designed for simplicity. It's managed via mobile app with limited advanced features.

### What UniFi controller options are available?

1. **Self-hosted** - Install on your own server (Windows, Linux, macOS)
2. **Cloud Key** - Dedicated hardware controller (Gen2, Gen2 Plus)
3. **Dream Machine** - All-in-one router with built-in controller (UDM, UDM Pro, UDM SE)
4. **Ubiquiti Cloud** - HostiFi or similar cloud-hosted options

### How do I access my UniFi controller?

- **Local**: `https://<controller-ip>:8443` (self-hosted) or `https://<udm-ip>`
- **Remote**: Via unifi.ui.com with Ubiquiti account linked
- **Mobile**: UniFi Network app (iOS/Android)

## Wireless Questions

### Should I use WPA2 or WPA3?

**Recommendation:** Use WPA2/WPA3 Transitional mode

**Why:**
- WPA3 provides stronger security (SAE authentication)
- Transitional allows older devices to connect via WPA2
- Pure WPA3 may exclude some devices

**Check compatibility:** Some older devices, IoT devices, and printers may not support WPA3

### Why are my 2.4 GHz speeds slow?

**Common causes:**
1. **Interference** - 2.4 GHz is congested (neighbors, Bluetooth, microwaves)
2. **Wrong channel** - Use only channels 1, 6, or 11
3. **Wide channel** - Don't use 40 MHz on 2.4 GHz
4. **Too many devices** - 2.4 GHz has limited capacity

**Solution:** Push capable devices to 5 GHz using band steering

### What is band steering?

Band steering encourages dual-band devices to connect to 5 GHz instead of 2.4 GHz, improving performance for capable devices while leaving 2.4 GHz for legacy devices.

**Enable:** Settings > WiFi > [Network] > Advanced > Band Steering

### How many devices can one AP handle?

**Rough guidelines:**
- Light usage (browsing): 50-60 clients per AP
- Medium usage (video): 30-40 clients per AP
- Heavy usage (4K streaming, gaming): 15-25 clients per AP

**Factors:**
- AP model capabilities
- Channel width and band
- Application requirements
- Physical environment

## Network Questions

### How do I set up VLANs?

1. **Create Network**: Settings > Networks > Create New
2. **Assign VLAN ID**: e.g., 20 for IoT
3. **Configure DHCP**: Set IP range
4. **Assign to Ports**: Settings > Ports > Select port > Network
5. **Assign to WiFi**: Settings > WiFi > [Network] > Network

### Why can't devices on different VLANs communicate?

**By design** - VLANs isolate network segments

**To allow communication:**
1. Create firewall rules allowing specific traffic
2. Settings > Firewall & Security > Firewall Rules
3. Create rule: Allow, Source VLAN A, Destination VLAN B

### How do I set up a guest network?

1. **Create Guest Network**: Settings > WiFi > Create New
2. **Enable Guest Hotspot**: Toggle on
3. **Configure Isolation**: Enable "Block LAN Access"
4. **Optional**: Enable captive portal for terms acceptance
5. **Optional**: Set bandwidth limits

### What ports does UniFi use?

| Port | Protocol | Purpose |
|------|----------|---------|
| 8080 | TCP | Device inform (adoption) |
| 8443 | TCP | Controller web UI |
| 8880 | TCP | HTTP portal redirect |
| 8843 | TCP | HTTPS portal redirect |
| 6789 | TCP | Speed test |
| 3478 | UDP | STUN |
| 10001 | UDP | Device discovery |

## Device Questions

### How do I factory reset a UniFi device?

**Physical reset:**
1. Locate reset button (small hole or button)
2. Power on device
3. Hold reset button for 10+ seconds
4. Release when LED flashes

**Via SSH:**
```
ssh ubnt@<device-ip>
set-default
```

**Via Controller:**
Devices > [Device] > Settings > Manage > Forget

### Why is my device stuck "Adopting"?

**Common causes:**
1. Device can't reach controller on port 8080
2. Inform URL mismatch
3. Previous adoption not cleared

**Solution:**
```
ssh ubnt@<device-ip>
set-inform http://<controller-ip>:8080/inform
```

### How do I update firmware?

**Single device:**
Devices > [Device] > Settings > Manage > Firmware > Upgrade

**All devices:**
Devices > (top bar) > Upgrade All

**Automatic:**
Settings > System > Updates > Enable automatic updates

### What is "Custom Upgrade" for?

Custom upgrade allows installing firmware not yet available through the controller, such as:
- Beta firmware
- Specific older version (rollback)
- Release candidate builds

**Use with caution** - may cause instability

## Security Questions

### What is PMF (Protected Management Frames)?

PMF protects WiFi management frames from spoofing attacks like:
- Deauthentication attacks (forcing disconnect)
- Disassociation attacks
- Beacon spoofing

**Settings:**
- **Required**: All clients must support PMF (WPA3 requirement)
- **Optional**: Use PMF when client supports it
- **Disabled**: Not recommended

### How do I enable IDS/IPS?

1. Go to Settings > Firewall & Security > Threat Management
2. Enable IDS (detection only) or IPS (active blocking)
3. Set sensitivity level (1-5)
4. Review alerts in Dashboard

**Note:** IPS can impact throughput on non-UDM hardware

### Should I hide my SSID?

**No** - Hiding SSID provides no real security benefit

**Problems with hidden SSIDs:**
- Devices constantly probe for hidden networks (privacy issue)
- Connection issues with some devices
- Makes troubleshooting harder
- Easily discovered with basic WiFi scanning tools

## Performance Questions

### What speeds should I expect from WiFi 6?

**Theoretical maximums:**
- WiFi 6 (802.11ax): Up to 9.6 Gbps (multi-stream)
- Practical single device: 1-2 Gbps under ideal conditions
- Real-world typical: 500-800 Mbps

**Factors affecting speed:**
- Distance from AP
- Interference
- Channel width (80 MHz vs 160 MHz)
- Client device capabilities

### Why is my internet slower than my ISP plan?

**Check in order:**
1. **Test wired**: Bypass WiFi, test directly connected
2. **Check gateway stats**: Dashboard > Internet > Throughput
3. **IDS/IPS overhead**: May reduce throughput by 20-40%
4. **Hardware limits**: Check gateway throughput specs
5. **ISP issues**: Test during different times

### How do I optimize for gaming/streaming?

1. **Use wired connection** when possible
2. **Enable QoS**: Settings > Traffic Management
3. **Use 5 GHz or 6 GHz** for wireless
4. **Reduce channel congestion**: Use DFS channels
5. **Enable WMM**: Usually on by default
6. **Minimize latency**: Disable IPS if needed
