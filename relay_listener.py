import asyncio
import json
import logging
import os
from typing import Dict, Any
from enum import Enum
import aiohttp
import websockets
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NostrKind(Enum):
    """Nostr event kinds"""
    SET_METADATA = 0
    TEXT_NOTE = 1
    RECOMMEND_RELAY = 2
    CONTACTS = 3
    ENCRYPTED_DM = 4
    DELETE = 5
    REACTION = 7
    CHANNEL_CREATE = 40
    CHANNEL_METADATA = 41
    CHANNEL_MESSAGE = 42
    CHANNEL_HIDE = 43
    CHANNEL_MUTE = 44
    ZAPS = 9735
    LIVE_EVENT = 30311

class DiscordWebhook:
    """Handles sending messages to Discord via webhooks"""
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.session: aiohttp.ClientSession = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def send_message(self, content: str) -> bool:
        """Send a message to Discord webhook"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")

        try:
            payload = {'content': content}
            async with self.session.post(self.webhook_url, json=payload) as response:
                return 200 <= response.status < 300
        except Exception as e:
            logger.error(f"Error sending to Discord: {str(e)}")
            return False

async def format_nostr_event(event_data: Dict[str, Any]) -> str:
    """Format a Nostr event for Discord display"""
    kind = event_data.get('kind')
    try:
        kind_name = NostrKind(kind).name
    except ValueError:
        kind_name = f"UNKNOWN_KIND_{kind}"

    pretty_date = str(datetime.now())

    return (
        f"\n"
        f"Date:{pretty_date}\n"
        f"Event Type: {kind_name}\n"
        f"Author: {event_data.get('pubkey', 'unknown')[:8]}...\n"
        f"Content: {event_data.get('tags')}\n"
    )

async def listen_and_relay():
    """Main function to listen to Nostr relay and send events to Discord"""
    load_dotenv()
    
    relay_url = os.getenv('WEBSOCKET_URL')
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

    if not relay_url or not discord_webhook_url:
        logger.error("Required environment variables WEBSOCKET_URL and DISCORD_WEBHOOK_URL must be set")
        return

    # Get current timestamp for filtering
    current_time = int(datetime.now().timestamp())

    async with DiscordWebhook(discord_webhook_url) as webhook:
        while True:
            try:
                async with websockets.connect(relay_url) as websocket:
                    logger.info(f"Connected to Nostr relay at {relay_url}")

                    # Subscribe to all event kinds but only new messages
                    subscribe_message = ["REQ", "main", {
                        "kinds": [kind.value for kind in NostrKind],
                        "since": current_time  # Only get messages from now onwards
                    }]
                    await websocket.send(json.dumps(subscribe_message))

                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)

                        if isinstance(data, list) and len(data) >= 2 and data[0] == "EVENT":
                            event_data = data[2]
                            formatted_message = await format_nostr_event(event_data)
                            print("Sending to Discord:", formatted_message)
                            await webhook.send_message(formatted_message)

            except Exception as e:
                logger.error(f"Connection error: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    asyncio.run(listen_and_relay())