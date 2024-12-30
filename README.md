# Introduction
This plugin provides middleware to publish Nautobot changes to [NATS](https://nats.io).

# Configuration
```
connect = {}

# Optional path to a credentials file.
if "NATS_CRED" in os.environ:
    connect["user_credentials"] = os.environ["NATS_CRED"]

# Including the stream name ensures a JetStream publish.
PLUGINS_CONFIG["nautobot_change_producer"] = {
    "client": "nautobot_change_producer.client.NATS",
    "config": {
        "servers": os.environ["NATS_HOST"], **connect,
        "stream": "nautobot",
    },
}

PLUGINS.append("nautobot_change_producer")
```
