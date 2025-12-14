# UniFi Troubleshooting Guide

## Device Connectivity Issues

### Device Shows Offline

**Common Causes:**
1. Network connectivity loss
2. Power failure
3. IP address conflict
4. Firmware crash
5. Adoption issues

**Troubleshooting Steps:**

1. **Verify physical connectivity**
   - Check cable connections
   - Verify PoE power delivery
   - Check switch port status

2. **Check from UniFi console**
   - Devices > [Device] > check Last Seen time
   - Look for "Disconnected" or "Adopting" status

3. **Direct device access**
   - SSH to device: `ssh ubnt@<device-ip>` (default password: ubnt)
   - Check with: `info` command
   - View logs: `cat /var/log/messages`

4. **Factory reset if needed**
   - Physical reset button (hold 10+ seconds)
   - Or via SSH: `set-default`
   - Re-adopt to controller

### Device Stuck in "Adopting" State

**Resolution:**
1. Forget device in UniFi controller
2. Factory reset the device
3. Ensure device can reach controller on port 8080
4. Check inform URL: `set-inform http://<controller-ip>:8080/inform`
5. Re-adopt device

### High CPU/Memory Usage

**Diagnostics:**
- Check Devices > [Device] > Insights
- SSH: `top` or `htop` to see processes

**Common Solutions:**
1. Reduce connected clients (if overloaded)
2. Update firmware
3. Restart device
4. Check for DDoS or attack traffic

## WiFi Issues

### Slow WiFi Speeds

**Diagnostic Steps:**

1. **Check client connection**
   - Clients > [Client] > Connection info
   - Note signal strength (RSSI), channel, TX/RX rate

2. **Check for interference**
   - Settings > WiFi > [Network] > Scan
   - Look for overlapping channels

3. **Check AP utilization**
   - Devices > [AP] > Insights
   - High channel utilization = congestion

**Solutions:**
- Change channel (avoid crowded channels)
- Reduce channel width if congested
- Add additional APs
- Enable band steering

### Clients Not Connecting

**Checklist:**
1. SSID visible and enabled?
2. Security protocol compatible with client?
3. Correct password?
4. MAC filtering blocking client?
5. Client isolation preventing connection?

**Debug:**
- Check UniFi events log for connection attempts
- Client > Activity > look for association/authentication events

### Roaming Issues

**Symptoms:**
- VoIP calls dropping when moving
- Reconnection delays between APs
- Sticky clients (won't roam to closer AP)

**Solutions:**
1. Enable 802.11r (Fast Roaming) - test compatibility first
2. Enable 802.11k/v
3. Adjust minimum RSSI setting
4. Reduce AP transmit power (force roaming)
5. Ensure consistent SSID/security across APs

## Network Issues

### DHCP Not Working

**Diagnostics:**
1. Check DHCP server status in Network settings
2. Verify DHCP range has available IPs
3. Check for DHCP conflicts (multiple DHCP servers)

**UniFi DHCP:**
- Settings > Networks > [Network] > DHCP
- Verify "DHCP Server" is enabled
- Check IP range and lease time

**Debug commands (on UniFi device):**
```
cat /var/log/messages | grep dhcp
```

### Inter-VLAN Routing Issues

**Cannot reach other VLANs:**
1. Check firewall rules blocking traffic
2. Verify routing table
3. Check gateway configuration

**Firewall check:**
- Settings > Firewall & Security > Firewall Rules
- Look for Drop rules affecting your traffic

### DNS Issues

**Symptoms:**
- Can ping IP but not domain names
- Slow DNS resolution
- Website access failures

**Solutions:**
1. Check DNS server configuration
   - Settings > Networks > [Network] > DNS
2. Try alternate DNS (8.8.8.8, 1.1.1.1)
3. Clear client DNS cache
4. Check if DNS is blocked by firewall

## Performance Optimization

### Identifying Bottlenecks

**Check in order:**
1. Internet connection (WAN throughput)
2. Gateway/router CPU/memory
3. Switch uplinks (port utilization)
4. AP utilization and channel congestion
5. Client device capabilities

### Optimizing UniFi Gateway

**IDS/IPS Impact:**
- IDS/IPS can reduce throughput significantly
- Start at lower sensitivity levels
- Consider disabling for gigabit+ connections if performance critical

**Hardware Offloading:**
- Ensure hardware offload is enabled when available
- Settings > System > Advanced

### Optimizing WiFi Performance

**Quick Wins:**
1. Use 5 GHz when possible
2. Reduce 2.4 GHz channel width to 20 MHz
3. Enable band steering
4. Update AP firmware
5. Reduce unnecessary SSIDs (each adds overhead)

## Common Error Messages

### "Please adopt through the UniFi Network Application"

**Cause:** Device set-inform URL doesn't match controller

**Solution:**
```
ssh ubnt@<device-ip>
set-inform http://<controller-ip>:8080/inform
```

### "Firmware upgrade failed"

**Possible causes:**
1. Insufficient space on device
2. Network interruption during upgrade
3. Corrupt firmware file

**Solution:**
1. Retry upgrade
2. Manual upgrade via SSH:
   ```
   upgrade https://dl.ui.com/unifi/firmware/<path-to-bin>
   ```

### "RADIUS authentication failed"

**Check:**
1. RADIUS server reachable from controller
2. Shared secret matches
3. Client MAC in correct format
4. RADIUS server logs for specific error

## Log Locations

### UniFi Controller
- Application logs: `/var/log/unifi/`
- Server log: `server.log`
- MongoDB: `mongod.log`

### UniFi Devices (via SSH)
- System log: `/var/log/messages`
- Wireless log: `/var/log/wireless.log` (if exists)

### Viewing Logs in UI
- Settings > System > Updates > Backup > Download Support File
- Or: Settings > System > Support Info
