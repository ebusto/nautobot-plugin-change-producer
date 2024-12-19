import asyncio
import nats


class NATS:
    def __init__(self, servers=["nats://127.0.0.1:4222"], stream=None, subject="nautobot", **kwargs):
        self.connect = kwargs
        self.servers = servers
        self.stream  = stream
        self.subject = subject

        # Create a client local event loop.
        self.loop = asyncio.new_event_loop()

        # Initialize the client attribute.
        self.client = None

        # Connect.
        self.loop.run_until_complete(self.async_connect())

    def close(self):
        self.loop.run_until_complete(self.async_close())

    def send(self, messages):
        if self.stream:
            self.loop.run_until_complete(self.async_send_stream(messages))
        else:
            self.loop.run_until_complete(self.async_send_direct(messages))

    async def async_connect(self):
        self.client = await nats.connect(servers=self.servers, **self.connect)

    async def async_close(self):
        await self.client.drain()
        await self.client.close()

    async def async_send_direct(self, messages):
        for message in messages:
            await self.client.publish(self.subject, message)

        # Ensure all published messages are sent.
        await self.client.flush()

    async def async_send_stream(self, messages):
        # The stream must already exist.
        js = self.client.jetstream()

        for message in messages:
            # JetStream publishing is synchronous, with no need to flush.
            await js.publish(self.subject, message)

