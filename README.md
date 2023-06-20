# Introduction
This plugin provides middleware to publish Nautobot changes to a message broker.

# Configuration
```
PLUGINS.append("nautobot_change_producer")  
```

## [NATS](https://nats.io/)
```
PLUGINS_CONFIG["nautobot_change_producer"] = {
    "client": "nautobot_change_producer.client.NATS",
    "config": {
        "servers": "nats://nats-broker:4222",
    }   
}       
```