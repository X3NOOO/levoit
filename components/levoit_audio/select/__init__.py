import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import select
from esphome.const import CONF_ID, CONF_ENTITY_CATEGORY, ENTITY_CATEGORY_CONFIG

from .. import levoit_audio_ns, LevoitAudio, LevoitAudioSelect

CONF_LEVOIT_AUDIO_ID = "levoit_audio_id"
CONF_SOUNDS = "sounds"

CONFIG_SCHEMA = select.select_schema(LevoitAudioSelect).extend(
    {
        cv.GenerateID(CONF_LEVOIT_AUDIO_ID): cv.use_id(LevoitAudio),
        cv.Optional(CONF_SOUNDS, default=[]): cv.All(
            cv.ensure_list(cv.string),
            cv.Length(min=0, max=6),
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_LEVOIT_AUDIO_ID])
    var = cg.new_Pvariable(config[CONF_ID])

    sounds = list(config[CONF_SOUNDS])

    # Set entity category default
    cfg = dict(config)
    if CONF_ENTITY_CATEGORY not in cfg:
        cfg[CONF_ENTITY_CATEGORY] = ENTITY_CATEGORY_CONFIG

    # register_select generates: var->traits.set_options({"Off", "Sound1", ...})
    # using the initializer_list<const char*> overload — static literals, no crash.
    await select.register_select(var, cfg, options=["Off"] + sounds)
    await cg.register_component(var, cfg)

    # Register sounds with the parent LevoitAudio component
    for i, name in enumerate(sounds):
        cg.add(parent.add_sound(f"/assets/10000{i + 1}.mp3", name))
