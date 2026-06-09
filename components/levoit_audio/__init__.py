import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import select
from esphome.const import CONF_ID

CODEOWNERS = []

levoit_audio_ns = cg.esphome_ns.namespace("levoit_audio")
LevoitAudio = levoit_audio_ns.class_("LevoitAudio", cg.Component)
LevoitAudioSelect = levoit_audio_ns.class_("LevoitAudioSelect", select.Select, cg.Component)

CONF_BCLK_PIN = "bclk_pin"
CONF_LRCLK_PIN = "lrclk_pin"
CONF_DOUT_PIN = "dout_pin"
CONF_AMP_ENABLE_PIN = "amp_enable_pin"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(LevoitAudio),
        cv.Required(CONF_BCLK_PIN): cv.int_range(min=0, max=39),
        cv.Required(CONF_LRCLK_PIN): cv.int_range(min=0, max=39),
        cv.Required(CONF_DOUT_PIN): cv.int_range(min=0, max=39),
        cv.Required(CONF_AMP_ENABLE_PIN): cv.int_range(min=0, max=39),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    # Pass pin numbers as build-time defines — used in levoit_audio.cpp
    cg.add_build_flag(f"-DSPROUT_I2S_BCLK=(gpio_num_t){config[CONF_BCLK_PIN]}")
    cg.add_build_flag(f"-DSPROUT_I2S_LRCLK=(gpio_num_t){config[CONF_LRCLK_PIN]}")
    cg.add_build_flag(f"-DSPROUT_I2S_DOUT=(gpio_num_t){config[CONF_DOUT_PIN]}")
    cg.add_build_flag(f"-DSPROUT_AMP_ENABLE=(gpio_num_t){config[CONF_AMP_ENABLE_PIN]}")
