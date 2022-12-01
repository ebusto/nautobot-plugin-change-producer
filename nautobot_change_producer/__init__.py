from importlib               import metadata
from nautobot.extras.plugins import NautobotAppConfig


class NautobotChangeProducerConfig(NautobotAppConfig):
    name         = "nautobot_change_producer"
    verbose_name = "Change Producer"

    base_url = "nautobot-change-producer"
    version  = metadata.version(__name__)

    description = "Change Producer"

    author       = "Eric Busto"
    author_email = "ebusto@nvidia.com"

    middleware = ["nautobot_change_producer.middleware.Middleware"]

    default_settings  = {}
    required_settings = []


config = NautobotChangeProducerConfig  # pylint:disable=invalid-name
