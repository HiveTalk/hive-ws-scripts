import asyncio
import os
from relay_listener import DiscordWebhook
from dotenv import load_dotenv

async def test_send_message():
    # Load environment variables
    load_dotenv()

    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL environment variable is not set")
        return

    print(f"Using webhook URL: {webhook_url[:20]}...") # Print first 20 chars for verification

    async with DiscordWebhook(webhook_url) as webhook:
        success = await webhook.send_message("Hello, world!")
        if success:
            print("Message sent successfully!")
        else:
            print("Failed to send message.")

if __name__ == "__main__":
    asyncio.run(test_send_message())
