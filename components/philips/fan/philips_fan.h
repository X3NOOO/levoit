#pragma once
#include "esphome/core/component.h"
#include "esphome/components/fan/fan.h"

namespace esphome {
namespace philips {

class Philips;

// 3-speed fan: speed 1 = Sleep, speed 2 = Medium, speed 3 = Turbo.
// On/off maps to device power.
class PhilipsFan : public Component, public fan::Fan {
 public:
  void set_parent(Philips *p) { parent_ = p; }
  void setup() override;
  void dump_config() override;
  fan::FanTraits get_traits() override {
    this->wire_preset_modes_(this->traits_);  // include entity-owned preset modes
    return this->traits_;
  }

  // called by the parent when the MCU reports state (group 0x03)
  void apply_state(bool power, uint8_t mode);

 protected:
  void control(const fan::FanCall &call) override;
  Philips *parent_{nullptr};
  fan::FanTraits traits_;
};

}  // namespace philips
}  // namespace esphome
