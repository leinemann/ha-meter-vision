# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub:
**Security → Report a vulnerability** on
[leinemann/ha-meter-vision](https://github.com/leinemann/ha-meter-vision/security/advisories/new).
Don't open a public issue for them.

You can expect an acknowledgement within a week. Fixes are released as a new version, and the advisory
is published once the fix is out.

## Supported versions

Only the latest release gets fixes. Update through HACS.

| Version | Supported |
| --- | --- |
| Latest release | ✓ |
| Anything older | ✗ |

## What the integration does with images and keys

- **API keys.** Meter Vision never sees, stores or sends an API key. It calls Home Assistant's
  `ai_task.generate_data` action, and the AI Task integration you chose (Anthropic, OpenAI, OpenRouter,
  Google, Ollama, …) holds its own key in Home Assistant's config entries. No key or secret belongs in
  this repository; secret scanning with push protection is on.
- **Camera frames.** Each reading takes one frame from the camera entity you chose. The frame is:
  - kept in memory for the *Last frame* image entity, which Home Assistant serves only to signed-in users
    with a rotating access token;
  - written to Home Assistant's local media folder (`/media/meter_vision/<meter>.jpg`), overwriting the
    previous one, and never to `/config/www`, which is served without sign-in;
  - sent as an attachment to the AI Task entity, which sends it to its provider. A cloud provider receives
    a picture of your meter; with a local model (Ollama) it stays on your network.
- **No network calls of its own** and no Python dependencies: everything goes through Home Assistant's
  camera and AI Task components.
- **Diagnostics** downloads contain the configuration (with notification services redacted) and the
  validator state, but no frame and no key.
