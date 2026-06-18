#include "philips_sensor.h"
#include "esphome/core/log.h"

namespace esphome {
namespace philips {

static const char *const TAG = "philips.sensor";

void PhilipsSensor::dump_config() { LOG_SENSOR("", "Philips Sensor", this); }

}  // namespace philips
}  // namespace esphome
