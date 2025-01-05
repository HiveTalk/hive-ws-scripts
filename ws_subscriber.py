import asyncio
import websockets
import json
import argparse
import ssl
import os
from datetime import datetime
from dotenv import load_dotenv

def create_ssl_context():
    """Create SSL context for secure WebSocket client"""
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False  # Disable hostname verification
    ssl_context.verify_mode = ssl.CERT_NONE  # Don't verify certificate
    return ssl_context

async def subscribe_to_updates(port, use_ssl=False, host="localhost"):
    """Subscribe to WebSocket updates from the specified port"""
    protocol = "wss" if use_ssl else "ws"
    uri = f"{protocol}://{host}:{port}"
    
    print(f"Connecting to WebSocket server at {uri}...")
    print(f"SSL enabled: {use_ssl}")

    ssl_context = create_ssl_context() if use_ssl else None

    while True:
        try:
            print(f"Attempting connection to {host}:{port}...")
            # Wrap the connection attempt in wait_for to add a timeout
            connection = websockets.connect(
                uri,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
                max_size=10_000_000,  # 10MB max message size
                open_timeout=30,  # 30 second timeout for opening connection
            )
            
            print("Initiating WebSocket handshake...")
            async with await asyncio.wait_for(connection, timeout=30) as websocket:
                print("WebSocket connection established successfully!")
                
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)  # 30 second timeout
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

                    except asyncio.TimeoutError:
                        print("No message received for 30 seconds, checking connection...")
                        try:
                            pong = await websocket.ping()
                            await asyncio.wait_for(pong, timeout=10)
                            print("Connection still alive")
                        except:
                            print("Ping failed, reconnecting...")
                            break

        except asyncio.TimeoutError as e:
            print(f"Connection timed out after 30 seconds. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed (code={e.code}, reason={e.reason}). Attempting to reconnect in 5 seconds...")
            await asyncio.sleep(5)
        except (OSError, websockets.exceptions.WebSocketException) as e:
            print(f"Connection error ({e.__class__.__name__}): {str(e)}. Attempting to reconnect in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Unexpected error ({e.__class__.__name__}): {str(e)}. Attempting to reconnect in 5 seconds...")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)

async def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description='HiveTalk WebSocket Subscriber')
    parser.add_argument('--env', choices=['staging', 'production', 'both'], default='both',
                      help='Environment to monitor (staging, production, or both)')
    parser.add_argument('--ssl', action='store_true', help='Use SSL/WSS connection')
    parser.add_argument('--host', default='localhost', help='WebSocket server hostname')
    args = parser.parse_args()
    
    if args.env == 'both':
        # Connect to both staging and production
        staging_task = subscribe_to_updates(8765, args.ssl, args.host)  # Staging port
        production_task = subscribe_to_updates(8766, args.ssl, args.host)  # Production port
        await asyncio.gather(staging_task, production_task)
    else:
        # Connect to specific environment
        port = 8765 if args.env == 'staging' else 8766
        await subscribe_to_updates(port, args.ssl, args.host)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Fatal error: {e}")
