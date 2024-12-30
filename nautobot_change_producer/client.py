import asyncio
import typing
import nats


# NATS wraps the official NATS library for Python, which requires using asyncio.
class NATS:
    def __init__(self, servers: typing.Iterable[str]=["nats://127.0.0.1:4222"],
        subject: str="nautobot", stream: typing.Optional[str]=None, **connect) -> None:

        self.servers = servers
        self.stream  = stream
        self.subject = subject
        self.connect = connect

        # Create an event loop.
        self.loop = asyncio.new_event_loop()

        # Initialize the NATS connection and JetStream context attributes.
        self.nc = None
        self.js = None

        # Connect.
        self.loop.run_until_complete(self.async_connect())

    def close(self) -> None:
        self.loop.run_until_complete(self.async_close())

    def publish(self, message: bytes) -> None:
        self.loop.run_until_complete(self.async_publish(message))

    async def async_connect(self) -> None:
        self.nc = await nats.connect(servers=self.servers, **self.connect)
        self.js = self.nc.jetstream()

        # Ensure the stream exists. This will raise an exception if it does not.
        if self.stream:
            await self.js.stream_info(self.stream)

    async def async_close(self) -> None:
        await self.nc.close()

    async def async_publish(self, message: bytes) -> None:
        # JetStream publish?
        if self.stream:
            await self.js.publish(self.subject, message)
            return

        # Core publish.
        await self.nc.publish(self.subject, message)
        await self.nc.flush()
