import kafka
import pynats


class Kafka:
    def __init__(self, acks=1, servers="localhost:9092", topic="nautobot"):
        self.topic  = topic
        self.client = kafka.KafkaProducer(
            acks              = acks,
            bootstrap_servers = servers,
        )

    def close(self):
        self.client.close()

    def flush(self):
        self.client.flush()

    def send(self, message):
        self.client.send(self.topic, value=message)


class NATS:
    def __init__(self, url="nats://127.0.0.1:4222", subject="nautobot"):
        self.subject = subject

        self.client = pynats.NATSClient(url)
        self.client.connect()

    def close(self):
        self.client.close()

    def flush(self):
        pass

    def send(self, message):
        self.client.publish(self.subject, payload=message)
