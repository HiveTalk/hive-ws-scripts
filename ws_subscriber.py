import asyncio
import websockets
import json
import argparse
from datetime import datetime

async def subscribe_to_updates(port):
    """Subscribe to WebSocket updates from the specified port"""
    uri = f"ws://localhost:{port}"
    
    print(f"Connecting to WebSocket server at {uri}...")
    async with websockets.connect(uri) as websocket:
        print("Connected! Waiting for updates...")
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Pretty print the received data
                print("\n" + "="*50)
                print(f"Environment: {data['environment'].upper()}")
                print(f"Timestamp: {data['timestamp']}")
                print("\nMeetings Data:")
                if not data['data'].get('meetings'):
                    print("No active meetings")
                else:
                    for meeting in data['data']['meetings']:
                        print(f"\nRoom: {meeting['roomId']}")
                        print(f"Bees: {meeting['peers']}")
                print("="*50 + "\n")
                
            except websockets.exceptions.ConnectionClosed:
                print("Connection lost. Attempting to reconnect...")
                break
            except Exception as e:
                print(f"Error: {e}")
                break

async def main():
    parser = argparse.ArgumentParser(description='HiveTalk WebSocket Subscriber')
    parser.add_argument('--env', choices=['staging', 'production', 'both'], default='both',
                      help='Environment to monitor (staging, production, or both)')
    args = parser.parse_args()
    
    if args.env == 'both':
        # Connect to both staging and production
        staging_task = subscribe_to_updates(8765)  # Staging port
        production_task = subscribe_to_updates(8766)  # Production port
        await asyncio.gather(staging_task, production_task)
    else:
        # Connect to specific environment
        port = 8765 if args.env == 'staging' else 8766
        await subscribe_to_updates(port)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSubscriber stopped by user")
