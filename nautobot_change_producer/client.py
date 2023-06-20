import asyncio
import nats


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