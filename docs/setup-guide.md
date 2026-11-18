# Setup guide

From a meter in a cupboard to a reading sensor on the Energy dashboard, in four steps:

1. [The camera](#1-the-camera): a frame of the counter that Home Assistant can fetch.
2. [Claude with your own key](#2-claude-with-your-own-key): an AI Task entity that reads images.
3. [Model and cost](#3-model-and-cost): which model to pick, and what a reading costs.
4. [Mounting](#4-mounting-glare-and-spiders): getting frames a model can read, month after month.

Then [add Meter Vision](../README.md#setup).

---

## 1. The camera

Meter Vision reads any Home Assistant `camera` entity. It asks for one still frame per reading, so the
camera doesn't need to stream. What matters is a **sharp, evenly lit close-up of the counter**. 640×480
is plenty when the counter fills most of the frame.

### Option A: ESP32-CAM with ESPHome

An AI-Thinker ESP32-CAM board with an OV2640 camera costs a few euros, has a flash LED on board and is
supported by ESPHome. This is the configuration for that board (other boards use other pins: see the
[ESPHome `esp32_camera` docs](https://esphome.io/components/esp32_camera.html)):

```yaml
esphome:
  name: water-meter-cam

esp32:
  board: esp32cam

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

api:
ota:
  - platform: esphome
logger:

esp32_camera:
  name: Water meter
  external_clock:
    pin: GPIO0
    frequency: 20MHz
  i2c_pins:
    sda: GPIO26
    scl: GPIO27
  data_pins: [GPIO5, GPIO18, GPIO19, GPIO21, GPIO36, GPIO39, GPIO34, GPIO35]
  vsync_pin: GPIO25
  href_pin: GPIO23
  pixel_clock_pin: GPIO22
  power_down_pin: GPIO32
  resolution: 800x600
  jpeg_quality: 10
  max_framerate: 1 fps
  idle_framerate: 0.05 fps

output:
  - platform: ledc
    pin: GPIO4
    id: flash_led

light:
  - platform: monochromatic
    name: Water meter flash
    output: flash_led
```

Adopt the device in Home Assistant, then in Meter Vision pick `camera.water_meter` as the camera and
`light.water_meter_flash` as the camera light. Keep the light warm-up at 20–30 s: the OV2640 adjusts its
exposure slowly, and frames taken sooner come out dark.

Power it from a good 5 V supply of at least 1 A. Most "random reboot" and "brown stripes" problems with
ESP32-CAMs are weak power or a long thin USB cable.

### Option B: an AI-on-the-Edge device you already have

If an [AI-on-the-Edge](https://github.com/jomjol/AI-on-the-edge-device) ESP32-CAM is already mounted on the
meter, keep the hardware and use it as a plain camera. Its web server serves a flash-lit still at
`/capture_with_flashlight`.

1. *Settings → Devices & services → Add integration → **Generic Camera***.
2. **Still image URL**: `http://<device-ip>/capture_with_flashlight`. Leave the stream source empty.
   Turn off *Verify SSL certificate* (it's plain HTTP).
3. Check the preview shows the counter with the flash on, then finish. You now have a camera entity
   (rename it to something like `camera.water_meter`).
4. In Meter Vision pick that camera and **leave the camera light empty**: the URL fires the flash itself.
   The light warm-up then doesn't apply.

You can leave the device's own digit recognition running. Its readings and Meter Vision's are
independent, and comparing them for a week is a good way to build trust before you switch your Energy
dashboard over. If a capture ever times out because the device is busy with its own round, give its round
a longer interval.

### Option C: any other camera

An IP camera, a Reolink or UniFi camera already pointed at the meter room, an old phone with an IP-webcam
app: if Home Assistant has a `camera` entity for it and the digits are legible when you zoom into a
snapshot, it works. A wide view is fine for the model as long as the counter is sharp. Use *Notes about
the meter* to say where the meter is in the frame if there is more than one.

---

## 2. Claude with your own key

Meter Vision never sees your key. It calls Home Assistant's `ai_task.generate_data` action, and Home
Assistant's Anthropic integration makes the API call with the key you gave it.

1. Create an API key in the [Anthropic Console](https://console.anthropic.com/) (*Settings → API keys*).
   Add a little credit, and **set a monthly spend limit** (*Settings → Limits*): a reading costs a
   fraction of a cent, so a limit of a few dollars is plenty and protects you from a misconfiguration.
2. In Home Assistant: *Settings → Devices & services → Add integration → **Anthropic*** and paste the key.
3. On the Anthropic integration page, make sure there is an **AI Task** entry (add one with *Add AI
   Task* if there isn't). Open its options to choose the model (see below). Its entity is called
   something like `ai_task.claude_ai_task`.
4. Pick that entity as the *AI Task entity* in Meter Vision.

Want a backup? Add a second AI Task entity (another model, or another provider) as the *fallback AI Task
entity* in the Meter Vision options. It's used when the first one is unavailable or fails.

---

## 3. Model and cost

Every reading is one call: one frame plus the instructions in, a few dozen tokens out. An unreadable
frame is retried once, so a bad frame costs two calls.

Rough cost per reading, at Anthropic's list prices of November 2026, for a 640×480 frame:

| Model | Price per million tokens (in / out) | Per reading | Every 15 min (≈2,900 / month) | Every hour (≈730 / month) |
| --- | --- | --- | --- | --- |
| Claude Haiku 5.5 | $0.10 / $0.50 | ≈ $0.0002 | ≈ $0.50 | ≈ $0.15 |
| Claude Sonnet 5.5 | $2 / $10 | ≈ $0.003 | ≈ $9 | ≈ $2.50 |
| Claude Opus 5.5 | $4 / $20 | ≈ $0.006 | ≈ $19 | ≈ $5 |

How these were estimated: an image costs about *width × height ÷ 750* input tokens (≈ 410 for 640×480,
≈ 640 for 800×600), the instructions and schema about 700 more, and the answer about 100 tokens out.
**These are estimates, not measurements.** Models that think before answering bill that thinking as
output tokens, and Home Assistant adds its own wrapper to the prompt. After the first day, check the
real figure in the Anthropic Console under *Usage*. Prices change: see
[anthropic.com/pricing](https://www.anthropic.com/pricing).

Which model:

- **Start with Claude Haiku 5.5.** On a sharp, well-lit frame of mechanical wheels it's the cheapest
  option by far and fast.
- **Move to Claude Sonnet 5.5** if the *Last result* sensor often shows `unreadable` or the confidence
  stays low: older meters with scratched glass, fogged dials, LCD displays at an angle.
- **Opus** is rarely worth it for this task. Fix the frame first (section 4).

Which interval: water usually only needs **30–60 minutes** for hourly graphs and leak checks, which cuts
the cost by 2–4×. Read more often when you want to see individual events (a shower, a pool top-up).

---

## 4. Mounting: glare and spiders

Most bad readings are bad frames, and most bad frames come from mounting. The *Last frame* image shows
exactly what the model saw: check it after mounting and again after a week.

**Distance and framing**

- Put the lens 5–10 cm from the glass for an ESP32-CAM. Closer is out of focus; further wastes pixels.
  The OV2640 lens can be refocused by turning it gently (break the glue dot first).
- Fill the frame with the counter and the pointer dials. A little margin around them helps if the
  mount moves slightly.
- Fix the camera rigidly to the meter or the pipe, not to a wall, so it can't drift. The AI-on-the-Edge
  community has 3D-printable mounts for most meter models.

**Glare**

- The flash reflecting off the meter glass is the most common reason a wheel is unreadable. Tilt the
  camera 10–20° off-axis so the reflection falls outside the counter.
- Diffuse the LED: a piece of white tape or baking paper over it softens the hotspot.
- Shade the meter from daylight. Sun moving across the glass gives different frames at different hours;
  a closed meter box is ideal.
- If one particular wheel is often hidden by a reflection, say so in *Notes about the meter*, but fixing
  the angle is better.

**Spiders, dust and damp**

- Meter boxes are warm, dark and quiet, and spiders love them. A single strand across the lens lights
  up in the flash and can hide a wheel. Close gaps around the camera housing, run the cable through a
  grommet or gland, and wipe the lens when you check the frame.
- Outdoor and pit meters fog up. A small sachet of silica gel in the enclosure helps, and a camera
  facing slightly downward collects less condensation.
- Dust on the meter glass looks like noise to the model. Wipe it when you service the camera.

**When it still misreads**

- Look at `digits_read` on the *Last result* sensor next to the *Last frame*. If the model counts a
  digit too many or too few, set *Digits of the counter*.
- Describe anything unusual in *Notes about the meter*, for example "the counter is upside down" or
  "ignore the black wheel on the far left, it is a test digit".
- A wrong value that slipped in before you set things up: fix it with `meter_vision.set_reading`.
