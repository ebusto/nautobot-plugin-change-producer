import asyncio
import nats


class NATS:
    def __init__(self, servers=["nats://127.0.0.1:4222"], subject="nautobot", **kwargs):
        self.connect = kwargs
        self.servers = servers
        self.subject = subject

        # Create a client local event loop.
        self.loop = asyncio.new_event_loop()

        # Initialize the client attribute.
        self.client = None

        # Connect.
        self.loop.run_until_complete(self.async_connect())

    def close(self):
        self.loop.run_until_complete(self.async_close())

    def send(self, values):
        self.loop.run_until_complete(self.async_send(values))

    async def async_connect(self):
        self.client = await nats.connect(servers=self.servers, **self.connect)

    async def async_close(self):
        await self.client.drain()
        await self.client.close()

    async def async_send(self, values):
        for value in values:
            await self.client.publish(self.subject, value)

        await self.client.flush()

