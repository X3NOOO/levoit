[← Back to ESPHome Projects](../README.md)

# ESPHome Components 

Collection of custom ESPHome components developed for various projects.

* [Levoit](./levoit) – Generic Levoit ESPHome component supporting Core (200/300/400/600), Vital (100/200), Everest Air, and Sprout series — UART communication, fan + presets, filter tracking, air-quality sensors, auto modes, and multi-entity support.
* [Philips / MUJI](./philips) – ESPHome component for Philips-made (Versuni) MUJI 600-series purifiers (AC0650 / AC0651) over their `FE FF` binary UART protocol — fan, filters, PM2.5, allergen index, Auto mode, and MCU version. Works much like the Levoit component.
* [levoit_audio](./levoit_audio) – I2S audio playback for the Levoit Sprout: white-noise MP3s streamed from the ESP32 SPIFFS `assets` partition (NS4168 / MAX98357A). Requires a vendored `dr_mp3.h` (see its README).

