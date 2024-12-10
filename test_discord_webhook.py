import asyncio
import os
from relay_listener import DiscordWebhook

async def test_send_message():
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')  # Replace with your actual Discord webhook URL
    async with DiscordWebhook(webhook_url) as webhook:
        success = await webhook.send_message("Hello, world!")
        if success:
            print("Message sent successfully!")
        else:
            print("Failed to send message.")

if __name__ == "__main__":
    asyncio.run(test_send_message())
