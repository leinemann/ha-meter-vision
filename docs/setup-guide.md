# Setup guide

From a meter in a cupboard to a reading sensor on the Energy dashboard, in four steps:

1. [The camera](#1-the-camera): a frame of the counter that Home Assistant can fetch.
2. [The AI model](#2-the-ai-model): an AI Task entity that reads images (Claude, OpenAI, Kimi, a local
   Qwen and others).
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

Use `/capture_with_flashlight`, not the device's stored images (`/img_tmp/raw.jpg` and the like): fetched
while the device is in the middle of its own round, `raw.jpg` has come back as a completely black frame.
Meter Vision draws its own [annotated frame](#5-the-annotated-frame), so nothing else of the device is
needed.

### Option C: any other camera

An IP camera, a Reolink or UniFi camera already pointed at the meter room, an old phone with an IP-webcam
app: if Home Assistant has a `camera` entity for it and the digits are legible when you zoom into a
snapshot, it works. A wide view is fine for the model as long as the counter is sharp. Use *Notes about
the meter* to say where the meter is in the frame if there is more than one.

---

## 2. The AI model

Meter Vision never sees an API key. It calls Home Assistant's `ai_task.generate_data` action with the
frame and a short prompt, and the integration behind the AI Task entity does the rest. Any AI Task
entity that **takes image attachments and returns structured data** works. These routes are checked
against Home Assistant's own integration code:

| You want | Integration | Images | Structured data | Key |
| --- | --- | --- | --- | --- |
| Claude | Anthropic | ✓ | ✓ | Anthropic API key |
| OpenAI GPT models | OpenAI | ✓ | ✓ | OpenAI API key |
| Kimi, Qwen (hosted), Mistral, Llama… | OpenRouter | ✓ (if the model takes images) | ✓ (only such models are offered) | OpenRouter key |
| Gemini | Google Generative AI | ✓ | ✓ | Google AI key |
| A local model | Ollama | ✓ (vision models only) | ✓ | none |

Whichever you choose, **set a monthly spend limit** in the provider's console. A reading costs a
fraction of a cent, so a limit of a few dollars is plenty and protects you from a misconfiguration.

### Claude (Anthropic)

1. Create an API key in the [Anthropic Console](https://console.anthropic.com/) and add a little credit.
2. *Settings → Devices & services → Add integration → **Anthropic*** and paste the key.
3. On the integration page, make sure there is an **AI Task** entry (add one if there isn't) and choose
   the model in its options. Its entity is called something like `ai_task.claude_ai_task`.

### OpenAI

1. Create an API key on [platform.openai.com](https://platform.openai.com/).
2. *Add integration → **OpenAI*** and paste the key, then add or open its **AI Task** entry and pick a
   model that takes images (the current GPT models do; the Codex models are tuned for code, and a
   general GPT model is the better fit for reading a frame).

Home Assistant's OpenAI integration talks to OpenAI only: it has no setting for another server address,
so it can't be pointed at an OpenAI-compatible service such as Moonshot's own API or a local server.

### Kimi (Moonshot AI) through OpenRouter

Home Assistant has no Moonshot integration. The supported route is
[OpenRouter](https://openrouter.ai/), which resells many providers' models behind one key:

1. Create a key on openrouter.ai and add credit.
2. *Add integration → **OpenRouter*** and paste the key, then add an **AI Task** entry.
3. Choose a Kimi model. The list only offers models that support structured outputs; check on the
   model's OpenRouter page that it also lists **image** input, because a text-only model can't read a
   frame. (Not every Kimi model takes images, and the lineup changes: this guide doesn't name one.)

The same route works for hosted Qwen-VL, Mistral and other vision models.

### A local Qwen vision model through Ollama

[Ollama](https://ollama.com/) runs open models on your own machine, for example a desktop or a small
server with a GPU on the same network as Home Assistant. Readings then cost nothing and the frames never
leave your network.

1. On that machine, install Ollama and pull a Qwen vision model, for example:

   ```bash
   ollama pull qwen2.5vl:7b
   ```

   `qwen3-vl` models work too. Pick the size by memory: a 7–8B model needs roughly 6–8 GB of GPU memory
   (or more RAM and a lot more time on a CPU). Text-only Qwen models (`qwen3`, `qwen2.5`) can't read
   images.
2. Make Ollama reachable from Home Assistant. By default it listens on `127.0.0.1` only. Set
   `OLLAMA_HOST=0.0.0.0` in its environment and restart it, then check `http://<machine>:11434` answers
   from another device. Only do this on a trusted network: Ollama has no authentication.
3. *Add integration → **Ollama***, URL `http://<machine>:11434`, then add an **AI Task** entry and pick
   the model.
4. In the entry's options:
   - turn **thinking off** if the model offers it (it slows each reading for no gain here);
   - leave **keep alive** at its default of `-1`, so the model stays loaded between readings instead of
     reloading every 15 minutes.

Small local models read sharp, well-lit wheels well and struggle with glare, dirty glass and dials.
The prompt is written for them: numbered rules, about 300 words, and a schema of three or four fields.
Section 4 matters even more with a local model. A cloud model as the **fallback AI Task entity** is a
good safety net: it is only called when the local one fails or is offline.

---

## 3. Model and cost

Every reading is one call: one frame plus the instructions in, a few dozen tokens out. An unreadable
frame is retried once, so a bad frame costs two calls.

- **Local (Ollama):** no cost per reading. A 7B vision model takes a few seconds per frame on a GPU.
- **Cloud:** you pay per token. An image costs roughly *width × height ÷ 750* input tokens on Claude
  (≈ 410 for 640×480); other providers count image tokens differently, but the order of magnitude is
  similar. The instructions and schema add a few hundred tokens, and the answer is about 100 tokens out.

For Claude, at Anthropic's list prices of November 2026:

| Model | Price per million tokens (in / out) | Per reading | Every 15 min (≈2,900 / month) | Every hour (≈730 / month) |
| --- | --- | --- | --- | --- |
| Claude Haiku 5.5 | $0.10 / $0.50 | ≈ $0.0002 | ≈ $0.50 | ≈ $0.15 |
| Claude Sonnet 5.5 | $2 / $10 | ≈ $0.003 | ≈ $9 | ≈ $2.50 |
| Claude Opus 5.5 | $4 / $20 | ≈ $0.006 | ≈ $19 | ≈ $5 |

For other cloud providers, multiply their per-token prices the same way (about 1,100 tokens in and
100 out per reading). **These are estimates, not measurements.** Models that think before answering bill
that thinking as output tokens, and Home Assistant adds its own wrapper to the prompt. After the first
day, check the real figure in your provider's usage page.

Which model:

- **Start with the cheapest vision model of your provider** (Claude Haiku, a small GPT model, or a local
  7B Qwen-VL). Mechanical wheels in a sharp frame are an easy task.
- **Move up a size** if the *Last result* sensor often shows `unreadable` or the confidence stays low:
  older meters with scratched glass, fogged dials, LCD displays at an angle.
- Before moving up, fix the frame (section 4). It helps every model more than a bigger one does.

Which interval: water usually only needs **30–60 minutes** for hourly graphs and leak checks, which cuts
a cloud bill by 2–4×. Read more often when you want to see individual events (a shower, a pool top-up).

### Comparing providers on your own meter

The plausibility check makes providers interchangeable: whichever model reads the frame, a reading only
gets into your statistics if it agrees with the last one. To see how models compare on *your* meter, try
them side by side for a few days:

1. Add a second Meter Vision entry for the same camera (for example named `Water meter qwen`), with the
   other AI Task entity and **without** adding it to the Energy dashboard.
2. Compare the two devices: *Last result* (how often each is `accepted`), *Confidence*, and *Last value
   read* against the meter itself. The `ai_engine` attribute says which entity answered.
3. Keep the better one as the main AI Task entity and, if you like, the other as the fallback. Then
   delete the test entry.

Every provider's answer goes through the same parser, which accepts the small differences between them
(numbers as text, `"true"` instead of `true`, spaces in the digits). The test suite checks this with
representative answer shapes; it does not call real providers, so how well each model *reads* your
meter is something only the side-by-side comparison above can tell.

---

## 4. Mounting: glare and spiders

Most bad readings are bad frames, and most bad frames come from mounting. The *Frame sent to the AI*
image shows exactly what the model saw, and the *Last frame* what it read
([annotated](#5-the-annotated-frame)): check them after mounting and again after a week.

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

---

## 5. The annotated frame

The *Last frame* image (and the card) shows the frame the model was given, with what it made of it:

- a banner on top: the result (`ACCEPTED`, `IMPLAUSIBLE`, `UNREADABLE`, …), the published reading after
  it, the time of the frame, and the digits and dials the model read with its confidence;
- one box per wheel with the digit read above it, once you give the counter position. The model gives one
  confidence for the whole reading, so every box has its colour: green from 7, amber from 4, red below.
  A wheel it marked unreadable is red and crossed out. A rolling last wheel is labelled `5/6`. If the
  model read a different number of digits than the counter has, every box is red;
- a circle on each pointer dial with the digit read, once you give the dial positions.

The boxes are the counter position cut into equal slices, one per wheel (*Digits of the counter*), not
positions returned by the model. That works the same with every provider, local models included, and
never moves between readings. The model always gets the whole frame; the positions are only for the
drawing.

**Finding the positions.** Open the *Frame sent to the AI* image (a diagnostic entity of the device), save
it, and open it in any image editor that shows the pointer position in pixels (GIMP, Paint, Preview's
inspector, or an online one). Note the top-left corner of the row of wheels and its width and height, and
type them as `x, y, width, height` in *Configure → Counter position*, for example `192, 158, 296, 50`.
Include all wheels, the red ones too, and no frame around them, so each slice falls on one wheel. Do the
same for each pointer dial, separated by `;`, largest factor first.

Saving the options redraws the last frame straight away, without a new reading, so you can adjust the
numbers until the boxes sit on the wheels. If the camera moves, the boxes no longer fit: the reading
doesn't depend on them, but it is a sign to fix the mount.

The drawing never affects the reading. If a frame can't be drawn (a camera that sends something other
than a JPEG or PNG), the clean frame is shown instead and a warning is logged.

