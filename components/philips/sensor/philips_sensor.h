#pragma once
#include "esphome/components/sensor/sensor.h"
#include "esphome/core/component.h"

namespace esphome {
namespace philips {

// Filter % sensor. The parent computes the value (remaining / total) from the
// group 0x05 status and calls publish_state().
class PhilipsSensor : public sensor::Sensor, public Component {
 public:
  void dump_config() override;
};

}  // namespace philips
}  // namespace esphome
