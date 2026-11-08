# 🛰️ WatchGesture — Satellite GPS & Biometric Telemetry

An autonomous, zero-tap mobile telemetry bridge and desktop command center for live satellite geolocation and smartwatch health tracking.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [The Smartwatch GNSS Problem & Solution](#the-smartwatch-gnss-problem--solution)
3. [Web Bluetooth Sensor Streaming](#web-bluetooth-sensor-streaming)
4. [Cloud Relay PubSub Pipeline](#cloud-relay-pubsub-pipeline)
5. [Desktop Command Center & Live Map HUD](#desktop-command-center--live-map-hud)
6. [Bi-directional Watch Screen Text Injection](#bi-directional-watch-screen-text-injection)
7. [Quickstart Guide](#quickstart-guide)
8. [Chrome Mobile Configuration & Permissions](#chrome-mobile-configuration-site-permissions--secure-context)

---

## Architecture Overview

<p align="center">
  <img src="../assets/telemetry_architecture.svg" alt="Telemetry Architecture Diagram" width="100%" />
</p>

The telemetry subsystem connects three endpoints in real time:
1. **⌚ Smartwatch (BLE Peripheral):** Emits live pulse (BPM) and step counts over Bluetooth Low Energy.
2. **📱 Mobile Phone Gateway (`phone_bridge.html`):** Runs in the phone browser, pulls high-precision satellite GPS coordinates from the phone's hardware GNSS, aggregates watch biometrics via Web Bluetooth, and beams JSON pings every 5 seconds.
3. **💻 Desktop / Laptop Command Center (`live_map.html`):** Subscribes to the live cloud stream, plots real-time coordinates on an interactive satellite map, and enables sending instant text alerts to the smartwatch face.

---

## The Smartwatch GNSS Problem & Solution

### The Hardware Constraint:
Budget consumer smartwatches (\$20–\$80) almost universally lack an integrated satellite GPS receiver to reduce bill-of-materials cost and prevent rapid battery drain.

### The WatchGesture Solution:
Instead of requiring an expensive dedicated GPS tracker or clunky proprietary companion apps (like Da Fit or GloryFit), WatchGesture uses an **instant mobile web bridge**:
- **Zero App Installation:** The phone bridge runs as a lightweight HTML5 web app (`phone_bridge.html`).
- **Zero-Tap Automatic Acquisition:** As soon as the page opens, `navigator.geolocation.watchPosition` locks onto satellites and begins streaming immediately.
- **Accurate to $\pm 3\text{m}$:** Leverages multi-constellation phone GNSS (GPS, GLONASS, Galileo, BeiDou).

---

## Web Bluetooth Sensor Streaming

The phone bridge connects directly to the smartwatch via the **Web Bluetooth API**:

```javascript
// 1. Connect to Vendor Service 0xFEEA & Standard Heart Rate 0x180D
const device = await navigator.bluetooth.requestDevice({
  filters: [{ services: [0xfeea] }],
  optionalServices: [0xfeea, 0x180d]
});

// 2. Arm Continuous Heart Rate Streaming (Opcode 0x68 {0x00})
await writeChar.writeValueWithoutResponse(makeV2Packet(0x68, new Uint8Array([0x00])));

// 3. Subscribe to Pedometer Characteristic (0xFEE1)
await stepsChar.startNotifications();
stepsChar.addEventListener("characteristicvaluechanged", (e) => {
  const b = new Uint8Array(e.target.value.buffer);
  if (b.length >= 7 && b[0] === 0xF6) {
    steps = b[1] | (b[2] << 8); // Little-endian 16-bit integer
  }
});
```

---

## Cloud Relay PubSub Pipeline

Telemetry uses standard HTTP pub/sub relays (`ntfy.sh` or any self-hosted MQTT/SSE broker) with zero account creation required:

### 1. Upstream Stream (Phone $\to$ PC):
- **Endpoint:** `POST https://ntfy.sh/<upstream_topic>`
- **Payload Schema:**
  ```json
  {
    "lat": 37.774929,
    "lon": -122.419416,
    "acc": 5.0,
    "bpm": 78,
    "steps": 4210,
    "msg": "Auto 5s Telemetry Sync",
    "sos": false,
    "timestamp": "2026-11-08T15:20:00Z"
  }
  ```

### 2. Downstream Stream (PC $\to$ Phone $\to$ Watch Screen):
- **Endpoint:** `GET https://ntfy.sh/<downstream_topic>/sse`
- Real-time Server-Sent Events (SSE) channel delivering instant text messages to the phone, which packages them into Opcode `0x41` packets and transmits them over BLE to the watch.

---

## Desktop Command Center & Live Map HUD

The desktop HUD runs locally on your PC:
- **Interactive Satellite Viewport:** Renders live position with auto-centering on movements greater than 5 meters.
- **Metric Cards:** Real-time display for Latitude/Longitude, GPS Accuracy ($\pm X\text{m}$), Heart Rate, Steps, and Last Sync timestamp.
- **Transmission Log:** Complete millisecond-stamped audit trail of incoming telemetry packets.

---

## Bi-directional Watch Screen Text Injection

WatchGesture can inject arbitrary text alerts directly onto the watch screen (Opcode `0x41` / `CMD_SEND_MESSAGE`):

```
+------------+------------+------------+------------+------------+------------+--------------------+
|    0xFE    |    0xEA    |    0x20    |   Length   |    0x41    |  Type (11) |   "Title:Message"  |
+------------+------------+------------+------------+------------+------------+--------------------+
```

The watch firmware interprets the first colon (`:`) as the delimiter between the notification title and the notification body.

---

## Quickstart Guide

### 1. Start the Telemetry Server on PC:
```powershell
python run.py telemetry
```
*Automatically starts the relay listener, hosts the local web server at `http://localhost:8765`, and opens `live_map.html` in your default browser.*

### 2. Connect Your Phone:
1. Connect your phone to the same Wi-Fi network (or open the public tunnel URL).
2. Open `http://<your-pc-ip>:8765/phone_bridge.html` in Chrome on your phone.
3. Satellite GPS tracking begins automatically.
4. *(Optional)* Tap **"Link Smartwatch BLE"** to stream pulse and steps.

---

## Chrome Mobile Configuration (Site Permissions & Secure Context)

Because Chrome for Android enforces modern web security standards, accessing hardware sensors (GPS via `navigator.geolocation` and Bluetooth via `navigator.bluetooth`) over a local network requires granting Chrome permissions:

### Option A: Enable Insecure Origins in Chrome (Recommended for Wi-Fi)
1. On your phone's Chrome browser, navigate to:
   ```
   chrome://flags/#unsafely-treat-insecure-origin-as-secure
   ```
2. Enable the flag and enter your PC's LAN URL:
   ```
   http://192.168.x.x:8765
   ```
3. Tap **Relaunch** at the bottom of Chrome. Chrome will now grant full Geolocation and Web Bluetooth access.

### Option B: Zero-Flag USB Port Forwarding (ADB)
If connected via USB cable:
```powershell
adb reverse tcp:8765 tcp:8765
```
Then simply open `http://localhost:8765/phone_bridge.html` on your phone. Chrome treats `localhost` as an intrinsically secure origin, requiring zero flag changes.

### Option C: Chrome Site Settings (Permissions)
When visiting the bridge:
1. Tap the **tune / padlock icon** on the left of Chrome's address bar.
2. Select **Permissions** $\to$ ensure **Location** is set to **"Allow"** and **Nearby devices / Bluetooth** is enabled.
3. The built-in **Screen Wake Lock API** automatically prevents Chrome from suspending GPS updates when the screen dims or the phone is in your pocket.

---

### 3. Send Text to Watch Screen:
Type a message in the desktop HUD or run:
```powershell
python run.py telemetry-send -m "Dinner is ready!"
```
*The watch will buzz and show "PC: Dinner is ready!" on its display.*

