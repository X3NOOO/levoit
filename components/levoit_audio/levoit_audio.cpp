// ---------------------------------------------------------------------------
// Levoit Sprout — SPIFFS audio playback over I2S
//
// Decoder:
//   MP3 — dr_mp3  https://github.com/mackron/dr_libs
//
// Place vendor/dr_mp3.h next to this file.
//
// Pin defines come from build flags set by __init__.py:
//   SPROUT_I2S_BCLK, SPROUT_I2S_LRCLK, SPROUT_I2S_DOUT, SPROUT_AMP_ENABLE
// ---------------------------------------------------------------------------

// Single-compilation-unit decoder implementation.
// vendor/ headers are not copied by ESPHome to the build tree; they are found
// via CPPPATH injected by build_assets.py pointing to the original vendor/ dir.
#define DR_MP3_IMPLEMENTATION
#include "dr_mp3.h"

#include "levoit_audio.h"

#include "driver/i2s_std.h"
#include "driver/gpio.h"
#include "esp_spiffs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <vector>

static const char *const TAG_AUDIO = "levoit.audio";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
#define SPROUT_SAMPLE_RATE    32000
#define SPROUT_DMA_BUF_COUNT  8
#define SPROUT_DMA_BUF_LEN    512

// SPROUT_I2S_BCLK / LRCLK / DOUT / AMP_ENABLE come from build flags

// ---------------------------------------------------------------------------
// SPIFFS mount
// ---------------------------------------------------------------------------
static bool spiffs_mounted_ = false;

static bool mount_spiffs() {
    if (spiffs_mounted_) return true;

    esp_vfs_spiffs_conf_t conf = {
        .base_path = "/assets",
        .partition_label = "assets",
        .max_files = 20,
        .format_if_mount_failed = false,
    };
    esp_err_t err = esp_vfs_spiffs_register(&conf);
    if (err != ESP_OK) {
        ESP_LOGE(TAG_AUDIO, "SPIFFS mount failed: %s", esp_err_to_name(err));
        return false;
    }
    spiffs_mounted_ = true;
    ESP_LOGI(TAG_AUDIO, "SPIFFS mounted at /assets");
    return true;
}

// ---------------------------------------------------------------------------
// I2S init / deinit  (ESP-IDF 5.x new API)
// ---------------------------------------------------------------------------
static i2s_chan_handle_t i2s_tx_chan_ = nullptr;
static volatile bool stop_requested_ = false;
static TaskHandle_t audio_task_ = nullptr;
static volatile bool loop_enabled_ = false;
static volatile uint8_t audio_volume_ = 200;  // 0–255, default ~80%
static volatile int current_index_ = -1;       // last started sound index, -1 = none

static void i2s_start() {
    if (i2s_tx_chan_ != nullptr) return;

    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num  = SPROUT_DMA_BUF_COUNT;
    chan_cfg.dma_frame_num = SPROUT_DMA_BUF_LEN;
    i2s_new_channel(&chan_cfg, &i2s_tx_chan_, nullptr);

    i2s_std_config_t std_cfg = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(SPROUT_SAMPLE_RATE),
        .slot_cfg = I2S_STD_MSB_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk  = I2S_GPIO_UNUSED,
            .bclk  = SPROUT_I2S_BCLK,
            .ws    = SPROUT_I2S_LRCLK,
            .dout  = SPROUT_I2S_DOUT,
            .din   = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv   = false,
            },
        },
    };
    i2s_channel_init_std_mode(i2s_tx_chan_, &std_cfg);
    i2s_channel_enable(i2s_tx_chan_);

    gpio_set_direction(SPROUT_AMP_ENABLE, GPIO_MODE_OUTPUT);
    gpio_set_level(SPROUT_AMP_ENABLE, 1);
    ESP_LOGI(TAG_AUDIO, "I2S started, amp enabled");
}

static void i2s_stop() {
    if (i2s_tx_chan_ == nullptr) return;
    static const int16_t silence[SPROUT_DMA_BUF_LEN * 2] = {};
    size_t written = 0;
    i2s_channel_write(i2s_tx_chan_, silence, sizeof(silence), &written, pdMS_TO_TICKS(50));
    gpio_set_level(SPROUT_AMP_ENABLE, 0);
    i2s_channel_disable(i2s_tx_chan_);
    i2s_del_channel(i2s_tx_chan_);
    i2s_tx_chan_ = nullptr;
    ESP_LOGI(TAG_AUDIO, "I2S stopped, amp muted");
}

static void write_samples(const int16_t *samples, size_t count) {
    static int16_t stereo_buf[SPROUT_DMA_BUF_LEN * 2];
    while (count > 0) {
        size_t chunk = (count > SPROUT_DMA_BUF_LEN) ? SPROUT_DMA_BUF_LEN : count;
        const int32_t vol = audio_volume_;
        for (size_t i = 0; i < chunk; i++) {
            int16_t s = (int16_t)((int32_t)samples[i] * vol / 255);
            stereo_buf[i * 2]     = s;
            stereo_buf[i * 2 + 1] = s;
        }
        size_t written = 0;
        i2s_channel_write(i2s_tx_chan_, stereo_buf, chunk * 2 * sizeof(int16_t),
                          &written, portMAX_DELAY);
        samples += chunk;
        count -= chunk;
    }
}

// ---------------------------------------------------------------------------
// MP3 playback — streams from file, no whole-file malloc
// ---------------------------------------------------------------------------
static bool play_mp3(const char *path) {
    // drmp3_init_file calls fopen which needs heap for FILE struct + newlib mutex.
    // Guard to prevent a heap-assert crash when memory is fragmented.
    size_t free_heap = heap_caps_get_free_size(MALLOC_CAP_8BIT);
    if (free_heap < 32 * 1024) {
        ESP_LOGE(TAG_AUDIO, "Low heap (%u KB) before MP3 open — skipping", (unsigned)(free_heap / 1024));
        return false;
    }

    // drmp3 struct is ~20 KB — heap-allocate to avoid stack overflow in audio task
    drmp3 *mp3 = (drmp3 *)malloc(sizeof(drmp3));
    if (!mp3) {
        ESP_LOGE(TAG_AUDIO, "OOM for drmp3 struct (%u bytes)", (unsigned)sizeof(drmp3));
        return false;
    }
    if (!drmp3_init_file(mp3, path, nullptr)) {
        ESP_LOGE(TAG_AUDIO, "Cannot open MP3: %s", path);
        free(mp3);
        return false;
    }
    ESP_LOGI(TAG_AUDIO, "Playing MP3: %s  %u Hz  %u ch", path, mp3->sampleRate, mp3->channels);

    static drmp3_int16 pcm[SPROUT_DMA_BUF_LEN];
    drmp3_uint64 frames_read;
    while (!stop_requested_ &&
           (frames_read = drmp3_read_pcm_frames_s16(mp3, SPROUT_DMA_BUF_LEN, pcm)) > 0) {
        if (mp3->channels == 2) {
            for (drmp3_uint64 i = 0; i < frames_read; i++)
                pcm[i] = (int16_t)(((int32_t)pcm[i * 2] + pcm[i * 2 + 1]) / 2);
        }
        write_samples(pcm, (size_t)frames_read);
    }
    drmp3_uninit(mp3);
    free(mp3);
    ESP_LOGI(TAG_AUDIO, "MP3 done: %s", path);
    return true;
}

// ---------------------------------------------------------------------------
// Sound table — populated at init time via add_sound() calls generated by
// __init__.py from the `sounds:` list in the component YAML config.
// ---------------------------------------------------------------------------
struct SoundDef {
    const char *file;
    const char *name;
};

static std::vector<SoundDef> sounds_;

// ---------------------------------------------------------------------------
// FreeRTOS task
// ---------------------------------------------------------------------------
struct AudioTaskParams { uint8_t index; };

static void audio_task_fn(void *arg) {
    AudioTaskParams *p = (AudioTaskParams *)arg;
    uint8_t index = p->index;
    delete p;

    i2s_start();
    bool first = true;
    do {
        if (!first) ESP_LOGI(TAG_AUDIO, "Looped: [%u] %s", index, sounds_[index].name);
        first = false;
        bool ok = play_mp3(sounds_[index].file);
        if (!ok) break;  // don't retry on open/decode failure — would corrupt heap
    } while (loop_enabled_ && !stop_requested_);

    i2s_stop();
    audio_task_ = nullptr;
    vTaskDelete(nullptr);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace levoit_audio {
void LevoitAudio::setup() {
    levoit_audio_setup();
}
void LevoitAudio::add_sound(const char *file, const char *name) {
    sounds_.push_back({file, name});
}
}  // namespace levoit_audio

void levoit_audio_setup() {
    mount_spiffs();
    gpio_set_direction(SPROUT_AMP_ENABLE, GPIO_MODE_OUTPUT);
    gpio_set_level(SPROUT_AMP_ENABLE, 0);
}

void levoit_audio_play(uint8_t index, bool loop) {
    if (index >= sounds_.size()) {
        ESP_LOGE(TAG_AUDIO, "Invalid sound index %u", index);
        return;
    }
    if (!mount_spiffs()) return;

    if (audio_task_ != nullptr) {
        loop_enabled_ = false;
        stop_requested_ = true;
        vTaskDelay(pdMS_TO_TICKS(150));
    }
    stop_requested_ = false;
    loop_enabled_ = loop;
    current_index_ = (int)index;

    ESP_LOGI(TAG_AUDIO, "Play: [%u] %s%s", index, sounds_[index].name, loop ? " (loop)" : "");
    auto *p = new AudioTaskParams{index};
    // Pin to APP_CPU (core 1, same as ESPHome main loop).
    // SPIFFS reads temporarily disable both CPU caches via IPC. Running on the
    // same core as the main app avoids cross-core cache-disable conflicts that
    // can crash if the other core is in a critical section.
    xTaskCreatePinnedToCore(audio_task_fn, "levoit_audio", 8192, p, 5, &audio_task_, 1);
}

void levoit_audio_stop() {
    loop_enabled_ = false;
    stop_requested_ = true;
    current_index_ = -1;
}

void levoit_audio_set_loop(bool loop) { loop_enabled_ = loop; }
bool levoit_audio_is_looping() { return loop_enabled_; }

void levoit_audio_set_volume(uint8_t vol) { audio_volume_ = vol; }
uint8_t levoit_audio_get_volume() { return audio_volume_; }

bool levoit_audio_is_playing() { return audio_task_ != nullptr; }
int  levoit_audio_current_index() { return current_index_; }

size_t levoit_audio_sound_count() { return sounds_.size(); }

const char *levoit_audio_sound_name(size_t index) {
    return (index < sounds_.size()) ? sounds_[index].name : "";
}

// ---------------------------------------------------------------------------
// LevoitAudioSelect
// ---------------------------------------------------------------------------
namespace levoit_audio {

void LevoitAudioSelect::dump_config() {
    ESP_LOGCONFIG(TAG_AUDIO, "White Noise Sound Select");
}

void LevoitAudioSelect::control(const std::string &value) {
    if (value == "Off") {
        levoit_audio_stop();
    } else {
        for (size_t i = 0; i < sounds_.size(); i++) {
            if (value == sounds_[i].name) {
                levoit_audio_play((uint8_t)i, true);
                break;
            }
        }
    }
    publish_state(value);
}

}  // namespace levoit_audio
