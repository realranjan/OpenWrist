# 🚀 OpenWrist — Complete Launch & Social Media Kit

This document contains pre-formatted launch posts and publication articles for **OpenWrist**, optimized for Twitter/X (free tier), LinkedIn, Reddit, and Medium.

---

## Table of Contents
1. [Medium Article (Full Deep-Dive)](#1-medium-article-full-deep-dive)
2. [LinkedIn Post (Viral Storyteller)](#2-linkedin-post-viral-storyteller)
3. [Twitter / X Posts (Free 280-Character Limit)](#3-twitter--x-posts-free-280-character-limit)
4. [Reddit Post (r/Python & r/reverseengineering)](#4-reddit-post-rpython--rreverseengineering)

---

## 1. Medium Article (Full Deep-Dive)

**Title:** How I Reverse-Engineered a ₹3,000 Smartwatch to Doomscroll YouTube Shorts Hands-Free  
**Subtitle:** From sniffing Bluetooth Low Energy opcodes in Wireshark to building a deterministic FSM gesture controller and an educational satellite telemetry beacon.  
**Reading Time:** ~8 min read  
**Recommended Tags:** `#Python` `#ReverseEngineering` `#IoT` `#HardwareHacking` `#Cybersecurity`

### Article Body:

It was late on a Sunday evening. I was curled up in bed, laptop propped up on a pillow, doomscrolling YouTube Shorts. 

My hand was warm under the blanket, and the sheer effort of reaching out every 45 seconds to tap the `Down Arrow` key on my keyboard felt absurdly inconvenient. 

I glanced at my wrist. I was wearing an ordinary **₹3,000 (~$35) smartwatch** (a Fire-Boltt 184 running on a Realtek RTL8762 chipset family, using the ubiquitous DaFit firmware).

Inside that tiny metal chassis sat a 3-axis accelerometer, a Bluetooth Low Energy (BLE 5.0) radio, and a vibration motor. 

A thought struck me: **Why reach for a mouse when a flick of my wrist could trigger a keystroke?**

Four days later, that lazy thought evolved into **[OpenWrist](https://github.com/realranjan/OpenWrist)** — an open-source Python daemon that translates physical wrist snaps into driver-level desktop keystrokes and an educational edge-satellite tracking beacon.

---

### Sniffing BLE Without a $500 Hardware Analyzer

Most hardware hacking tutorials tell you to buy an Ubertooth One or a dedicated Ellisys packet sniffer. But if you have an Android phone, you already have an enterprise-grade BLE sniffer in your pocket:

1. Go to **Settings → Developer Options**.
2. Toggle **"Enable Bluetooth HCI snoop log"**.
3. Toggle Bluetooth off and on, open your smartwatch companion app (Da Fit), and trigger every feature: camera remote, find watch, heart rate measurement, notifications.
4. Generate a bug report:
   ```bash
   adb bugreport bugreport.zip
   ```
5. Inside the dump, Android stores `btsnoop_hci.log` — a raw, unencrypted capture of every single ATT read, write, and notification exchange between the phone and the watch.

Opening the capture in Wireshark with the filter:
```wireshark
btatt.opcode == 0x12 || btatt.opcode == 0x1b
```
immediately exposed the watch's internal GATT anatomy:

```
       GATT Service: 0000feea-0000-1000-8000-00805f9b34fb (Vendor)
      ┌─────────────────────────┬─────────────────────────┐
      ▼                         ▼                         ▼
0xFEE1 (Read/Notify)      0xFEE2 (Write Without Resp) 0xFEE3 (Notify)
Pedometer Steps & State   PC Commands -> Watch       Watch Events -> PC
```

---

### The Protocol Breakthroughs

#### Breakthrough 1: Watches Don't Stream Raw Accelerometer Data
Budget smartwatches have 200mAh batteries. If the 3-axis accelerometer streamed continuous 50Hz XYZ samples over BLE, the battery would die in three hours.

Instead, the watch firmware keeps the accelerometer asleep until the companion app's "Camera Shutter Remote" is opened.

In Wireshark, the phone sent:
```text
FE EA 20 06 66 01
```
* `FE EA`: 2-byte magic framing header.
* `20 06`: Length indicator (`0x20` base flag + 6 total packet bytes).
* `0x66`: **Opcode 102 (`CMD_ARM_GSENSOR`)**.
* `0x01`: Sub-command (Enable Interrupts).

Writing `0x66` with payload `0x01` to characteristic `0xFEE2` arms the watch's internal G-sensor. The moment your wrist snaps downward, the watch emits an unsolicited notification on `0xFEE3`:
```text
FE EA 20 06 66 01  <-- [Wrist Flick Detected!]
```

#### Breakthrough 2: The 6-Second Watchdog Heartbeat
The watch firmware has a watchdog: if it doesn't receive a command for **6.0 seconds**, it assumes the camera was closed, turns off G-sensor interrupts, and returns to the watch face.

To keep the controller alive indefinitely, I built an asynchronous keepalive loop in Python that sends a heartbeat packet every 5.5 seconds:
```python
async def _keepalive_worker(self):
    while self.is_connected:
        await self.client.write_gatt_char(CHAR_WRITE_FEE2, make_keepalive_packet(), response=False)
        await asyncio.sleep(5.5)
```

#### Breakthrough 3: Bypassing the 1.4-Second Shutter Animation Lock
When the watch detects a flick, it freezes the screen for **1.4 seconds** playing a camera shutter animation. During this freeze, all subsequent wrist snaps are ignored.

By analyzing what happens when you press the physical crown button, I discovered Opcode `0x53` (`CMD_RETURN_HOME`).

By writing a fast-abort trick into Python:
```python
# The moment a flick arrives on FEE3, immediately cancel the animation:
await self.client.write_gatt_char(CHAR_WRITE_FEE2, make_return_home_packet(), response=False)
```
The watch aborts the shutter animation in **under 40 milliseconds**, resetting the G-sensor for instant multi-taps.

---

### The Brain: A Sliding-Window Finite-State Machine

```
       [IDLE]
         │ (Wrist Flick #1)
         ▼
      [WINDOW OPEN] ──(Flick #2 within 1.0s)──> [DOUBLE FLICK]
         │                                            │
         │ (Timer expires: 1.0s)                      │ (Flick #3)
         ▼                                            ▼
 [DISPATCH 1 FLICK]                          [INSTANT BOSS KEY!]
   Scroll Down ⏭️                              Minimize Windows (Win+D)
```

* **Sliding Window (1.00s):** When the first flick arrives, a timer opens. If you flick again within 1.0 second, it increments the count.
* **Debounce Gap (0.28s):** Any interrupt arriving within 280ms of the previous flick is discarded as mechanical bounce.
* **Lockout Cooldown (0.40s):** After an action fires, interrupts are locked out for 400ms to prevent accidental triggers while returning to rest.
* **Instant Boss Key:** 3 rapid snaps immediately inject `[Win + D]` to minimize all windows without waiting for the timer.

---

### Pillar 2: The Educational Satellite GPS Beacon

A ₹3,000 smartwatch **does not have an onboard GPS chip**.

I built an **assisted mobile edge gateway**:
1. A web page (`phone_bridge.html`) runs on the phone's Chrome browser with Screen Wake Lock active.
2. It locks onto satellite GPS via `navigator.geolocation` and uses **Web Bluetooth** to read the watch's live heart rate (`0x180D`) and steps (`0xFEE1`).
3. It bundles the payload and beams it every 5 seconds to a cloud pub/sub broker (`ntfy.sh`).
4. On my desktop, `live_map.html` plots the live coordinates on a Google Maps satellite HUD.
5. Bi-directional text messaging pushes notifications to the watch display via Opcode `0x41`.

> **Ethical & Cybersecurity Note:**  
> *This telemetry module was developed strictly as an **educational case study in IoT edge-relay architecture and privacy research**, demonstrating the ease with which consumer BLE hardware and browser geolocation APIs can be orchestrated into real-time tracking beacons.*

---

### Try It Yourself

⭐ **GitHub:** [https://github.com/realranjan/OpenWrist](https://github.com/realranjan/OpenWrist)

```powershell
git clone https://github.com/realranjan/OpenWrist.git
cd OpenWrist
pip install -e .

# Scan for your smartwatch:
python run.py scan

# Launch hands-free YouTube Shorts mode:
python run.py run --profile youtube_shorts
```

---

## 2. LinkedIn Post (Viral Storyteller)

```text
I was too lazy to reach for my mouse while doomscrolling YouTube Shorts...  
So I reverse-engineered a ₹3,000 smartwatch to scroll with a flick of my wrist. ⌚️🛋️

Meet OpenWrist — an open-source hardware hack that turns budget consumer BLE smartwatches (Fire-Boltt, Noise, BoAt, DaFit) into desktop gesture air-mice and educational telemetry beacons.

Here’s how the hack works:

1. Sniffing the BLE Opcodes:  
Budget smartwatches don't stream continuous accelerometer data to save battery. By extracting Android BTSnoop logs and decompiling GATT characteristics in Wireshark, I found vendor opcode 0x66 (which arms the watch's internal G-sensor) and opcode 0x53 (a trick that aborts the 1.4s camera shutter animation for rapid multi-taps).

2. The Gesture Engine:  
Built a deterministic Finite-State Machine in Python with a sliding window, debounce gap, and cooldown lockout:
• 1 Wrist Flick ➡️ Next Short (Down Arrow)  
• 2 Quick Flicks ➡️ Previous Short (Up Arrow)  
• 3 Instant Flicks ➡️ Boss Key (Win + D to hide all windows immediately)

3. The Satellite GPS & Telemetry Bridge (Educational Research):  
A ₹3,000 watch has no onboard GPS hardware. I built an assisted mobile web bridge that locks onto phone satellites, pairs with the watch's optical heart rate (0x180D) and steps (0xFEE1), and beams the payload to a live satellite map HUD over cloud relays.

⚠️ Ethical & Cybersecurity Note:  
The telemetry beacon is built strictly for educational research and personal IoT safety awareness. Demonstrating how low-cost consumer wearables and browser APIs can be orchestrated into real-time tracking beacons highlights critical privacy boundaries in consumer hardware.

100% typed Python, tested with 37 unit tests, and completely open source.

🔗 GitHub Repo & RE Guide:  
https://github.com/realranjan/OpenWrist

Would love to hear your thoughts on everyday hardware hacking and BLE reverse engineering! 🚀

#Python #ReverseEngineering #IoT #HardwareHacking #CyberSecurity #OpenSource #TechCommunity #Smartwatch
```

---

## 3. Twitter / X Posts (Free 280-Character Limit)

### Option A (YouTube Shorts Focus — 269 / 280 chars)
```text
Too lazy to reach for my mouse while doomscrolling YouTube Shorts, so I reverse-engineered a ₹3,000 smartwatch to scroll with wrist flicks ⌚️

1 flick = Next
2 = Prev
3 = Boss Key (Win+D)

Open-source Python:
https://github.com/realranjan/OpenWrist

#TechTwitter #Python #buildinpublic
```

### Option B (With Educational GPS Beacon — 273 / 280 chars)
```text
Too lazy to reach for my mouse while doomscrolling YouTube Shorts...

Reverse-engineered a ₹3k smartwatch into a gesture controller & educational GPS beacon ⌚️

1 flick = Next
2 = Prev
3 = Boss Key (Win+D)

⭐️ Open-source:
https://github.com/realranjan/OpenWrist

#TechTwitter #Python #IoT
```

---

## 4. Reddit Post (r/Python & r/reverseengineering)

**Title:** [P] I reverse-engineered a ₹3,000 smartwatch into a hands-free gesture controller for YouTube Shorts and an educational satellite telemetry beacon

```markdown
Hey everyone!

I wanted a way to browse YouTube Shorts completely hands-free from my couch without reaching for a keyboard or mouse.

I took a ₹3,000 consumer smartwatch (Fire-Boltt 184 / Realtek RTL8762 chipset family running the DaFit protocol) and reverse-engineered its Bluetooth Low Energy (BLE) interface into an open-source project called **OpenWrist**.

### 🛠️ How it Works:
1. **Sniffing Opcodes:** The watch disables high-frequency sensor streaming to save battery. By extracting Android BTSnoop logs and inspecting them in Wireshark, I found that writing Opcode `0x66` to vendor characteristic `0xFEE2` arms the internal accelerometer. Wrist snaps emit `0x66` notifications on `0xFEE3`.
2. **Animation Cancellation (`0x53`):** Normally, the watch locks up for 1.4 seconds playing a camera shutter animation. Sending Opcode `0x53` (`CMD_RETURN_HOME`) forces the display home instantly, enabling rapid multi-flick detection.
3. **Deterministic FSM Engine:** A sliding window classifies wrist snaps:
   - **1 Flick:** Next Short (`Down Arrow`)
   - **2 Flicks:** Previous Short (`Up Arrow`)
   - **3 Flicks:** Instant Boss Key (`Win + D` minimizes all windows)
4. **Dual Dispatch Backends:** Driver-level Win32 hardware virtual keys via `user32.keybd_event` with PyAutoGUI fallback.

### 🛰️ Satellite Telemetry Subsystem (Educational Research):
A ₹3,000 watch lacks onboard GNSS chips. I built a mobile web gateway (`phone_bridge.html`) combining phone satellite GPS (`navigator.geolocation`) with watch optical heart rate (`0x180D`) and steps (`0xFEE1`), streaming real-time coordinates to a desktop satellite map HUD.

*Security & Ethics Note:* This telemetry beacon was built strictly as an educational case study in IoT edge-relay architecture and hardware security, demonstrating how low-cost wearables and browser APIs interact.

The repo includes a 37-test zero-mock test suite, vector architecture diagrams, and a universal reverse-engineering cookbook for other brands (BoAt, Noise, Amazfit, Colmi).

**GitHub:** https://github.com/realranjan/OpenWrist
```
