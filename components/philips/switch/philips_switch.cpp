#include "philips_switch.h"
#include "esphome/core/log.h"

namespace esphome {
namespace philips {

static const char *const TAG = "philips.switch";

void PhilipsSwitch::dump_config() { LOG_SWITCH("", "Philips Switch", this); }

void PhilipsSwitch::write_state(bool state) {
  if (this->parent_ != nullptr) this->parent_->set_switch(this->type_, state);
  this->publish_state(state);
}

}  // namespace philips
}  // namespace esphome
