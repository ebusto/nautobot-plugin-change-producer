import asyncio
import atexit
import nats
import time
import typing

from .log import *


# NATS wraps the official NATS library for Python, which requires asyncio.
class NATS:
    def __init__(self,
            attempt: int=10,
            servers: typing.Iterable[str]=["nats://127.0.0.1:4222"],
            stream:  typing.Optional[str]=None,
            subject: str="nautobot", **kwargs
        ) -> None:

        self.attempt = attempt
        self.servers = servers
        self.stream  = stream
        self.subject = subject

        # All other arguments are treated as connection parameters.
        self.connect = kwargs

        # Initialize the NATS connection and JetStream context attributes.
        self.nc = None
        self.js = None

        # Create an event loop.
        self.loop = asyncio.new_event_loop()

        # Ensure a graceful disconnect.
        atexit.register(self.disconnect)

    def disconnect(self) -> None:
        self.loop.run_until_complete(self._disconnect())

    def publish(self, message: bytes) -> None:
        self.loop.run_until_complete(self._publish(message))

    async def _connect(self) -> None:
        # Connect to NATS.
        self.nc = await nats.connect(servers=self.servers, **self.connect)

        # Retrieve the JetStream context, and ensure the stream exists. This
        # will raise an exception if it does not.
        if self.stream:
            self.js = self.nc.jetstream()

            await self.js.stream_info(self.stream)

    async def _disconnect(self) -> None:
        # If necessary, disconnect from NATS.
        if self.nc:
            await self.nc.close()

        self.nc = None
        self.js = None

    # Publish the message, retrying if necessary with an increasing delay
    # between attempts.
    async def _publish(self, message: bytes) -> None:
        for n in range(self.attempt):
            try:
                # Connect if necessary.
                if not self.nc:
                    await self._connect()

                if self.stream:
                    # JetStream publish. There is no need to flush separately.
                    await self.js.publish(self.subject, message)
                else:
                    # Core publish.
                    await self.nc.publish(self.subject, message)
                    await self.nc.flush()

            except Exception as e:
                log.warning("publish [%d]: %s" % (n, e))

                # Force a reconnect.
                await self._disconnect()

                # Last attempt? Propagate the exception to the caller.
                if n+1 == self.attempt:
                    raise e

                # Trying again? Sleep for a bit.
                time.sleep(n)

            else:
                # Success!
                return
