#pragma once
#include "esphome/components/button/button.h"
#include "esphome/core/component.h"
#include "../philips.h"

namespace esphome {
namespace philips {

class PhilipsButton : public button::Button, public Component {
 public:
  void set_parent(Philips *p) { parent_ = p; }
  void set_type(ButtonType t) { type_ = t; }
  void dump_config() override;

 protected:
  void press_action() override;
  Philips *parent_{nullptr};
  ButtonType type_{ButtonType::RESET_PREFILTER};
};

}  // namespace philips
}  // namespace esphome
