import asyncio
import json
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import aiohttp
import websockets
from dotenv import load_dotenv
import argparse
from datetime import datetime, timedelta

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

@dataclass
class Config:
    """Configuration class for the application"""
    relay_url: str
    discord_webhook_url: str
    subscription_filters: List[Dict[str, Any]]
    max_retries: int = 5
    retry_delay: int = 5
    message_queue_size: int = 1000
    time_range: Optional[int] = None  # Time range in hours, None means only new events

    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables"""
        load_dotenv()

        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Nostr relay listener with time-based filtering')
        parser.add_argument('--time-range', type=int, help='Get events from the last N hours (e.g., 24 for last day)')
        args = parser.parse_args()

        relay_url = os.getenv('WEBSOCKET_URL')
        discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

        if not relay_url or not discord_webhook_url:
            raise ValueError("Required environment variables WEBSOCKET_URL and DISCORD_WEBHOOK_URL must be set")

        # Calculate the since timestamp if time range is specified
        subscription_filters = []
        if args.time_range:
            since_timestamp = int((datetime.now() - timedelta(hours=args.time_range)).timestamp())
            subscription_filters = [{"kinds": [kind.value for kind in NostrKind], "since": since_timestamp}]
        else:
            # Default subscription filter for only new events
            subscription_filters = [{"kinds": [kind.value for kind in NostrKind]}]

        return cls(
            relay_url=relay_url,
            discord_webhook_url=discord_webhook_url,
            subscription_filters=subscription_filters,
            max_retries=int(os.getenv('MAX_RETRIES', '5')),
            retry_delay=int(os.getenv('RETRY_DELAY', '5')),
            message_queue_size=int(os.getenv('MESSAGE_QUEUE_SIZE', '1000')),
            time_range=args.time_range
        )

class NostrEvent:
    """Class representing a Nostr event"""
    def __init__(self, event_data: Dict[str, Any]):
        self.id = event_data.get('id')
        self.pubkey = event_data.get('pubkey')
        self.created_at = event_data.get('created_at')
        self.kind = event_data.get('kind')
        self.tags = event_data.get('tags', [])
        self.content = event_data.get('content')
        self.sig = event_data.get('sig')

    @property
    def kind_name(self) -> str:
        """Get the human-readable name of the event kind"""
        try:
            return NostrKind(self.kind).name
        except ValueError:
            return f"UNKNOWN_KIND_{self.kind}"

    def format_for_discord(self) -> str:
        """Format the event for Discord display"""
        event_time = datetime.fromtimestamp(self.created_at)
        return (
            f"\n"
            f"Event Type: {self.kind_name}\n"
            f"Time: {event_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Author: {self.pubkey[:8]}...\n"
            f"Content: {self.content}\n"
            f"Tags: {json.dumps(self.tags, indent=2)}\n"
            f""
        )

class DiscordWebhook:
    """Handles sending messages to Discord via webhooks"""
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def send_message(self, content: str) -> bool:
        """Send a message to Discord webhook with rate limit handling"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")

        try:
            payload = {'content': content}
            logger.info(f"Sending to Discord webhook: {self.webhook_url}")
            async with self.session.post(self.webhook_url, json=payload) as response:
                response_text = await response.text()
                logger.info(f"Discord response status: {response.status}, body: {response_text}")

                if response.status == 429:  # Rate limited
                    retry_after = float(response.headers.get('Retry-After', '5'))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    return False
                return 200 <= response.status < 300
        except Exception as e:
            logger.error(f"Error sending to Discord: {str(e)}")
            return False

class NostrRelayClient:
    """Nostr relay client implementation"""
    def __init__(self, config: Config):
        self.config = config
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=config.message_queue_size)
        self.subscription_id = "main"  # You might want to make this configurable

    async def subscribe(self, websocket):
        """Send subscription message to the relay"""
        for filter_set in self.config.subscription_filters:
            subscribe_message = ["REQ", self.subscription_id, filter_set]
            await websocket.send(json.dumps(subscribe_message))
            logger.info(f"Subscribed with filter: {filter_set}")

    async def process_event(self, event_data: Dict[str, Any]) -> Optional[str]:
        """Process a Nostr event and format it for Discord"""
        try:
            event = NostrEvent(event_data)
            logger.info(f"Processing event kind {event.kind_name} from timestamp {event.created_at}")

            # Time-based filtering is handled by the subscription filter
            # but we'll add a safety check here
            if self.config.time_range is not None:
                since_timestamp = int((datetime.now() - timedelta(hours=self.config.time_range)).timestamp())
                if event.created_at < since_timestamp:
                    logger.info(f"Skipping event: too old (created at {event.created_at}, cutoff is {since_timestamp})")
                    return None

            formatted = event.format_for_discord()
            logger.info(f"Formatted event for Discord: {formatted[:100]}...")
            return formatted
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
            return None

    async def message_consumer(self, webhook: DiscordWebhook):
        """Consume messages from the queue and send them to Discord"""
        while True:
            message = await self.message_queue.get()
            logger.info(f"Attempting to send message to Discord: {message[:100]}...")
            success = await webhook.send_message(message)
            if not success:
                logger.error("Failed to send message to Discord")
                try:
                    self.message_queue.put_nowait(message)
                except asyncio.QueueFull:
                    logger.error("Message queue full, dropping message")
            else:
                logger.info("Successfully sent message to Discord")
            self.message_queue.task_done()

    async def run(self):
        """Main execution loop"""
        retry_count = 0

        async with DiscordWebhook(self.config.discord_webhook_url) as webhook:
            consumer_task = asyncio.create_task(self.message_consumer(webhook))

            while retry_count < self.config.max_retries:
                try:
                    async with websockets.connect(self.config.relay_url) as websocket:
                        logger.info(f"Connected to Nostr relay at {self.config.relay_url}")
                        await self.subscribe(websocket)
                        retry_count = 0

                        while True:
                            try:
                                message = await websocket.recv()
                                data = json.loads(message)
                                if not isinstance(data, list):
                                    continue

                                message_type = data[0]
                                if message_type == "EVENT" and len(data) >= 3:
                                    event_data = data[2]
                                    logger.info(f"Received event: {json.dumps(event_data, indent=2)}")
                                    formatted_message = await self.process_event(event_data)
                                    if formatted_message:
                                        await self.message_queue.put(formatted_message)
                                        logger.info(f"Queued {NostrKind(event_data.get('kind', -1)).name} event")
                                elif message_type == "EOSE":
                                    logger.info("End of stored events")
                                elif message_type == "NOTICE":
                                    logger.info(f"Relay notice: {data[1]}")

                            except websockets.ConnectionClosed:
                                logger.warning("WebSocket connection closed")
                                break
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON received: {e}")
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")

                except Exception as e:
                    retry_count += 1
                    wait_time = self.config.retry_delay * retry_count
                    logger.error(f"Connection error: {str(e)}")
                    logger.info(f"Retrying in {wait_time} seconds... (Attempt {retry_count}/{self.config.max_retries})")
                    await asyncio.sleep(wait_time)

            logger.error("Max retries reached. Exiting.")
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

def main():
    """Entry point of the script"""
    try:
        config = Config.from_env()
        client = NostrRelayClient(config)
        asyncio.run(client.run())
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    main()