# hive ws scripts

A few websocket scripts to listen to activity on hivetalk and post to discord webhoooks for monitoring 



## listening to hivetalk api and posting to discord and websocket
python smart_hive_ws.py

python smart_hive_ws.py --env staging

python smart_hive_ws.py --env production


## Listen to both environments
python ws_subscriber.py

## Listen to staging only
python ws_subscriber.py --env staging

## Listen to production only
python ws_subscriber.py --env production
