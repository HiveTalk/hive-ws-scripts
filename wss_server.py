#!/usr/bin/env python3
import asyncio
import ssl
import websockets
import logging

logging.basicConfig(
    format='%(asctime)s %(levelname)s:%(message)s',
    level=logging.INFO
)

async def handler(websocket):
    try:
        async for message in websocket:
            logging.info(f"Received message: {message}")
            # Echo the message back
            await websocket.send(f"Server received: {message}")
    except websockets.exceptions.ConnectionClosed:
        logging.info("Client connection closed")
    except Exception as e:
        logging.error(f"Error handling connection: {e}")

async def main():
    # Create SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Replace these paths with your actual certificate paths
    ssl_context.load_cert_chain(
        '/etc/letsencrypt/live/your-domain.com/fullchain.pem',
        '/etc/letsencrypt/live/your-domain.com/privkey.pem'
    )

    async with websockets.serve(
        handler,
        "0.0.0.0",  # Listen on all available interfaces
        8765,       # Port number
        ssl=ssl_context
    ):
        logging.info("WSS Server started on wss://0.0.0.0:8765")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
