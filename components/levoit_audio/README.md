# levoit_audio — ESPHome component for Sprout I2S audio

Plays white noise MP3 files from the ESP32 `assets` SPIFFS partition via the onboard I2S amplifier (NS4168 / MAX98357A).

## Dependencies

One vendored single-header decoder is required but not committed (gitignored). Download once:

```bash
cd components/levoit_audio
mkdir -p vendor

# MP3 decoder
curl -L https://raw.githubusercontent.com/mackron/dr_libs/master/dr_mp3.h -o vendor/dr_mp3.h
```

`esp_spiffs.h` is part of ESP-IDF and does not need to be downloaded.

## Configuration

```yaml
external_components:
  - source:
      type: local
      path: ../../components
    components: [levoit_audio]

levoit_audio:
  bclk_pin: 5        # I2S bit clock
  lrclk_pin: 18      # I2S word select / LR clock
  dout_pin: 17       # I2S serial data out
  amp_enable_pin: 19 # Amplifier enable / SD pin
  sounds:            # Up to 6 names; auto-maps index → 100001.mp3, 100002.mp3, …
    - "Summer Rain"
    - "Gentle Sea Wave"
    - "Sound 03"
```

## API (callable from ESPHome lambdas)

```cpp
levoit_audio_play(uint8_t index, bool loop = false);  // non-blocking
levoit_audio_stop();
levoit_audio_set_loop(bool loop);
levoit_audio_set_volume(uint8_t vol);  // 0–255
levoit_audio_is_playing();             // bool
levoit_audio_sound_count();            // size_t
levoit_audio_sound_name(size_t index); // const char*
```

## Notes

- Only MP3 files are supported. OGG/Vorbis is not — the ESP32 (no PSRAM) lacks free heap for stb_vorbis codebook state (~200–300 KB).
- MP3 is streamed frame-by-frame via dr_mp3 — no large heap allocation required.
- Playback runs on a background FreeRTOS task (8 KB stack, priority 5) — ESPHome main loop is not blocked.
- Mono output: stereo sources are mixed down before writing to I2S.
- `levoit_audio_play()` while playing stops the current track first, then starts the new one.
- The SPIFFS image is built by `build_assets.py` using `spiffsgen.py` (bundled with ESP-IDF — no extra pip install).
