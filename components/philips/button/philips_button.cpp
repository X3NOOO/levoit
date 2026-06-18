#include "philips_button.h"
#include "esphome/core/log.h"

namespace esphome {
namespace philips {

static const char *const TAG = "philips.button";

void PhilipsButton::dump_config() { LOG_BUTTON("", "Philips Button", this); }

void PhilipsButton::press_action() {
  if (this->parent_ != nullptr) this->parent_->reset_filter(this->type_);
}

}  // namespace philips
}  // namespace esphome
