#pragma once
#include "esphome/components/switch/switch.h"
#include "esphome/core/component.h"
#include "../philips.h"

namespace esphome {
namespace philips {

class PhilipsSwitch : public switch_::Switch, public Component {
 public:
  void set_parent(Philips *p) { parent_ = p; }
  void set_type(SwitchType t) { type_ = t; }
  void dump_config() override;

 protected:
  void write_state(bool state) override;
  Philips *parent_{nullptr};
  SwitchType type_{SwitchType::STANDBY_SENSOR};
};

}  // namespace philips
}  // namespace esphome
