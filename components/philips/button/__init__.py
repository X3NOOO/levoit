import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import button
from esphome.const import CONF_ID

from .. import Philips, CONF_PHILIPS_ID, philips_ns

CONF_TYPE = "type"

PhilipsButton = philips_ns.class_("PhilipsButton", button.Button, cg.Component)
ButtonType = philips_ns.enum("ButtonType", is_class=True)

TYPE_MAP = {
    "reset_prefilter": ButtonType.RESET_PREFILTER,
    "reset_hepa": ButtonType.RESET_HEPA,
}

CONFIG_SCHEMA = button.button_schema(PhilipsButton).extend(
    {
        cv.Required(CONF_PHILIPS_ID): cv.use_id(Philips),
        cv.Required(CONF_TYPE): cv.one_of(*TYPE_MAP.keys(), lower=True),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_PHILIPS_ID])
    var = cg.new_Pvariable(config[CONF_ID])
    await button.register_button(var, config)
    await cg.register_component(var, config)
    cg.add(var.set_parent(parent))
    cg.add(var.set_type(TYPE_MAP[config[CONF_TYPE]]))
