import os
import json
import asyncio
import logging
import aiohttp
from datetime import datetime
from dotenv import load_dotenv
from discord_webhook import DiscordWebhook, DiscordEmbed

# Set up logging
logging.basicConfig(
    filename='hivetalk_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# Load environment variables from .env file
load_dotenv()

# Get API key and Discord webhook from environment variables
API_KEY = os.getenv('STAGING_HIVETALK_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('STAGING_DISCORD_WEBHOOK_URL')

# API endpoint
API_URL = os.getenv('STAGING_API_URL')
BASE_JOIN_URL = os.getenv('STAGING_BASE_JOIN_URL')

if not API_KEY:
    raise ValueError("STAGING_HIVETALK_API_KEY not found in .env file")
if not DISCORD_WEBHOOK_URL:
    raise ValueError("STAGING_DISCORD_WEBHOOK_URL not found in .env file")


# Headers for the request
headers = {
    'accept': 'application/json',
    'authorization': API_KEY
}

def save_to_file(data):
    with open('active_mtgs.txt', 'w') as f:
        json.dump(data, f, indent=2)

def load_previous_data():
    try:
        with open('active_mtgs.txt', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"meetings": []}

def has_data_changed(old_data, new_data):
    return old_data != new_data

async def send_discord_update(data):
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL)
    
    current_time_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    embed = DiscordEmbed(
        title=f"HiveTalk Active Meetings Update - {current_time_utc}",
        color=0x00ff00
    )
    
    if not data.get("meetings"):
        embed.add_embed_field(
            name="Status",
            value="No active meetings at this time",
            inline=False
        )
    else:
        for meeting in data["meetings"]:
            room_id = meeting["roomId"]
            peers = meeting["peers"]
            join_link = f"{BASE_JOIN_URL}{room_id}"
            
            field_value = f"Bees count: {peers}\nLink: {join_link}"
            embed.add_embed_field(
                name=f"Room Name: {room_id}",
                value=field_value,
                inline=False
            )
    
    webhook.add_embed(embed)
    webhook.execute()

async def fetch_meet_info(session):
    try:
        async with session.get(API_URL, headers=headers) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        logging.error(f"Error fetching data: {e}")
        return None

async def poll_api():
    logging.info("Starting API polling service...")
    async with aiohttp.ClientSession() as session:
        while True:
            logging.info("Fetching meet info...")
            data = await fetch_meet_info(session)
            
            if data:
                current_time_utc = datetime.utcnow().strftime("Time: %Y-%m-%d %H:%M:%S UTC")
                logging.info(f"{current_time_utc} - Successfully received data: {data}")
                
                # Check if data has changed from previous state
                previous_data = load_previous_data()
                if has_data_changed(previous_data, data):
                    logging.info("Data changed, saving to file and sending Discord update...")
                    save_to_file(data)  # Only save when data has changed
                    await send_discord_update(data)
                else:
                    logging.info("No changes in data")
            
            # Wait for 60 seconds before next poll
            await asyncio.sleep(60)

def main():
    asyncio.run(poll_api())

if __name__ == "__main__":
    main()