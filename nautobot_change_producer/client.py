import asyncio
import kafka
import nats


class Kafka:
    def __init__(self, acks=1, servers="localhost:9092", topic="nautobot"):
        self.acks    = acks
        self.servers = servers
        self.topic   = topic

    def send(self, values):
        client = kafka.KafkaProducer(
            acks              = self.acks,
            bootstrap_servers = self.servers,
        )

        for value in values:
            client.send(self.topic, value = value)

        client.flush()
        client.close()


class NATS:
    def __init__(self, servers=["nats://127.0.0.1:4222"], subject="nautobot", **kwargs):
        self.servers = servers
        self.subject = subject
        self.connect = kwargs

    def send(self, values):
        return asyncio.run(self._send(values))

    async def _send(self, values):
        nc = await nats.connect(servers=self.servers, **self.connect)

        for value in values:
            await nc.publish(self.subject, value)

        await nc.flush()
        await nc.close()