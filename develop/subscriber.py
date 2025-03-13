import asyncio
import nats

async def main():
    # Connect to NATS server
    nc = await nats.connect("localhost:4222")

    # Subscribe to a queue group
    sub = await nc.subscribe("nautobot", queue="workers")

    # Process messages asynchronously
    async for msg in sub.messages:
        print(f"Received message: {msg.data.decode()}")

if __name__ == '__main__':
    asyncio.run(main())