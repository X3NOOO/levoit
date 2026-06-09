# Declares IDF component dependencies so ESP-IDF CMake compiles and links them.
# Actual C++ compilation is handled by ESPHome's external_components mechanism,
# so SRCS is intentionally empty — no double-compilation of levoit_audio.cpp.
idf_component_register(
    REQUIRES esp_driver_i2s spiffs driver freertos
)
