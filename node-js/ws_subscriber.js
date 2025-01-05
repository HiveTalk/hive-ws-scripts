const WebSocket = require('ws');

function subscribeToUpdates(port) {
    const uri = `ws://localhost:${port}`;
    console.log(`Connecting to WebSocket server at ${uri}...`);

    const ws = new WebSocket(uri);

    ws.on('open', () => {
        console.log('Connected! Waiting for updates...');
    });

    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);

            // Pretty print the received data
            console.log('\n' + '='.repeat(50));
            console.log(`Environment: ${data.environment.toUpperCase()}`);
            console.log(`Timestamp: ${data.timestamp}`);
            console.log('\nMeetings Data:');
            
            if (!data.data?.meetings) {
                console.log('No active meetings');
            } else {
                data.data.meetings.forEach(meeting => {
                    console.log(`\nRoom: ${meeting.roomId}`);
                    console.log(`Bees: ${meeting.peers}`);
                });
            }
            console.log('='.repeat(50) + '\n');
        } catch (error) {
            console.error(`Error: ${error.message}`);
        }
    });

    ws.on('close', () => {
        console.log('Connection lost. Attempting to reconnect...');
        setTimeout(() => subscribeToUpdates(port), 5000); // Reconnect after 5 seconds
    });

    ws.on('error', (error) => {
        console.error(`WebSocket error: ${error.message}`);
    });
}

function main() {
    const args = process.argv.slice(2);
    const envFlag = args.find(arg => arg.startsWith('--env='));
    const env = envFlag ? envFlag.split('=')[1] : 'both';

    if (!['staging', 'production', 'both'].includes(env)) {
        console.error('Error: --env must be staging, production, or both');
        process.exit(1);
    }

    if (env === 'both') {
        // Connect to both staging and production
        subscribeToUpdates(8765); // Staging port
        subscribeToUpdates(8766); // Production port
    } else {
        // Connect to specific environment
        const port = env === 'staging' ? 8765 : 8766;
        subscribeToUpdates(port);
    }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
    console.log('\nSubscriber stopped by user');
    process.exit(0);
});

main();
