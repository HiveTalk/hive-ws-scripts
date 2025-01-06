import os
import json
import asyncio
import logging
import aiohttp
import argparse
import websockets
from datetime import datetime
from dotenv import load_dotenv
from discord_webhook import DiscordWebhook, DiscordEmbed

# Global WebSocket connections store
connected_clients = set()

def setup_environment(env):
    """Setup environment variables based on staging or production"""
    prefix = "STAGING_" if env == "staging" else "PRODUCTION_"

    api_key = os.getenv(f'{prefix}HIVETALK_API_KEY')
    webhook_url = os.getenv(f'{prefix}DISCORD_WEBHOOK_URL')
    api_url = os.getenv(f'{prefix}API_URL')
    base_join_url = os.getenv(f'{prefix}BASE_JOIN_URL')
    ws_port = int(os.getenv(f'{prefix}WS_PORT', '8765' if env == 'staging' else '8766'))
    ssl_cert = os.getenv(f'{prefix}SSL_CERT')
    ssl_key = os.getenv(f'{prefix}SSL_KEY')

    if not all([api_key, webhook_url, api_url, base_join_url]):
        missing = [var for var, val in {
            f"{prefix}HIVETALK_API_KEY": api_key,
            f"{prefix}DISCORD_WEBHOOK_URL": webhook_url,
            f"{prefix}API_URL": api_url,
            f"{prefix}BASE_JOIN_URL": base_join_url
        }.items() if not val]
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return {
        'api_key': api_key,
        'webhook_url': webhook_url,
        'api_url': api_url,
        'base_join_url': base_join_url,
        'env': env,
        'ws_port': ws_port,
        'ssl_cert': ssl_cert,
        'ssl_key': ssl_key
    }

# Set up logging
logging.basicConfig(
    filename='hivetalk_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def save_to_file(data, env):
    filename = f'active_mtgs_{env}.txt'
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def load_previous_data(env):
    filename = f'active_mtgs_{env}.txt'
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"meetings": []}

def has_data_changed(old_data, new_data):
    return old_data != new_data

async def broadcast_to_clients(data, env):
    """Broadcast data to all connected WebSocket clients"""
    message = {
        'environment': env,
        'timestamp': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        'data': data
    }
    if connected_clients:
        websockets_to_remove = set()
        for websocket in connected_clients:
            try:
                await websocket.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                websockets_to_remove.add(websocket)

        # Clean up closed connections
        connected_clients.difference_update(websockets_to_remove)

async def handle_websocket_client(websocket, path):
    """Handle new WebSocket connections"""
    logging.info(f"New WebSocket client connected: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        logging.info(f"WebSocket client disconnected: {websocket.remote_address}")

async def start_websocket_server(host, port, ssl_context=None):
    """Start WebSocket server"""
    async with websockets.serve(handle_websocket_client, host, port, ssl=ssl_context):
        logging.info(f"WebSocket server started on {host}:{port} {'with SSL' if ssl_context else 'without SSL'}")
        await asyncio.Future()  # run forever

async def send_discord_update(data, config):
    webhook = DiscordWebhook(url=config['webhook_url'])
    
    current_time_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    env_name = config['env'].upper()

    embed = DiscordEmbed(
        title=f"HiveTalk {env_name} Active Meetings Update - {current_time_utc}",
        color=0x00ff00 if config['env'] == 'production' else 0xFFA500  # Green for prod, Orange for staging
    )
    
    if not data.get("meetings"):
        embed.add_embed_field(
            name="Status",
            value=f"No active meetings in {env_name} at this time",
            inline=False
        )
    else:
        for meeting in data["meetings"]:
            room_id = meeting["roomId"]
            peers = meeting["peers"]
            join_link = f"{config['base_join_url']}{room_id}"
            
            field_value = f"Bees count: {peers}\nLink: {join_link}"
            embed.add_embed_field(
                name=f"Room Name: {room_id}",
                value=field_value,
                inline=False
            )
    
    webhook.add_embed(embed)
    webhook.execute()

async def fetch_meet_info(session, config):
    headers = {
        'accept': 'application/json',
        'authorization': config['api_key']
    }

    try:
        async with session.get(config['api_url'], headers=headers) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        logging.error(f"Error fetching data from {config['env']}: {e}")
        return None

async def poll_api(config):
    env = config['env']
    logging.info(f"Starting API polling service for {env.upper()} environment...")

    async with aiohttp.ClientSession() as session:
        while True:
            logging.info(f"Fetching meet info from {env.upper()}...")
            data = await fetch_meet_info(session, config)
            
            if data:
                current_time_utc = datetime.utcnow().strftime("Time: %Y-%m-%d %H:%M:%S UTC")
                logging.info(f"{current_time_utc} - Successfully received {env.upper()} data: {data}")
                
                # Check if data has changed from previous state
                previous_data = load_previous_data(env)
                if has_data_changed(previous_data, data):
                    logging.info(f"Data changed in {env.upper()}, saving to file and sending updates...")
                    save_to_file(data, env)  # Only save when data has changed
                    await send_discord_update(data, config)
                    await broadcast_to_clients(data, env)  # Broadcast to WebSocket clients
                else:
                    logging.info(f"No changes in {env.upper()} data")
            
            # Wait for 60 seconds before next poll
            await asyncio.sleep(60)

async def run_all_environments():
    # Load environment variables
    load_dotenv()

    # Setup configurations for both environments
    configs = []
    for env in ['staging', 'production']:
        try:
            config = setup_environment(env)
            configs.append(config)
        except ValueError as e:
            logging.warning(f"Skipping {env} environment: {str(e)}")

    if not configs:
        raise ValueError("No valid environment configurations found")

    # Start WebSocket servers for each environment
    ws_servers = [start_websocket_server('localhost', config['ws_port']) for config in configs]

    # Create tasks for each environment
    polling_tasks = [poll_api(config) for config in configs]

    # Run all tasks concurrently
    await asyncio.gather(*ws_servers, *polling_tasks)

def main():
    parser = argparse.ArgumentParser(description='Start the HiveTalk WebSocket server')
    parser.add_argument('--host', default='localhost', help='Host to bind the WebSocket server to')
    parser.add_argument('--staging', action='store_true', help='Run in staging mode')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()
    
    env = "staging" if args.staging else "production"
    config = setup_environment(env)
    
    # Set up SSL context if certificates are provided
    ssl_context = None
    if config['ssl_cert'] and config['ssl_key']:
        import ssl
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(config['ssl_cert'], config['ssl_key'])
        logging.info("SSL context created with provided certificates")
    
    # Create event loop and run both the polling and WebSocket server
    loop = asyncio.get_event_loop()
    try:
        loop.create_task(poll_api(config))
        loop.run_until_complete(start_websocket_server(args.host, config['ws_port'], ssl_context))
    except KeyboardInterrupt:
        logging.info("Server shutdown requested")
    finally:
        loop.close()

if __name__ == "__main__":
    main()