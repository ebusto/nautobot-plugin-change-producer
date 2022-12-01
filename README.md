# Introduction
This plugin provides middleware to publish Nautobot changes to a message broker.

# Configuration
```
PLUGINS.append("nautobot_change_producer")  
```

## [Kafka](https://kafka.apache.org/)
```
PLUGINS_CONFIG["nautobot_change_producer"] = {
    "client": "nautobot_change_producer.client.Kafka",
    "config": {
        "servers": [
            "kafka-prd-01:9092",
            "kafka-prd-02:9092",
            "kafka-prd-03:9092",
        ],
    },
}
```

## [NATS](https://nats.io/)
```
PLUGINS_CONFIG["nautobot_change_producer"] = {
    "client": "nautobot_change_producer.client.NATS",
    "config": {
        "url": "nats://nats-broker:4222",
    }   
}       
```
