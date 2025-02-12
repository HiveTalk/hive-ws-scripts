# hive ws scripts

A collection of utility scripts to help facilitate monitoring of hivetalk activity

## relay_listener

The Relay listener listens for hivetalk event kind 30311, when created on the dashboard and pushes the data to discord. This is primarily for QC purposes but can be extended in the future for prettified display so that discord users can see event creation, update and deletion. 

To run the relay listener, you can use the following command:

```python
python relay_listener.py
```

## smart_hive_ws

A few websocket scripts to listen to activity on hivetalk and post to discord webhoooks for monitoring. Can also be subscribed to by other scripts via websocket.


## listening to hivetalk api and posting to discord and websocket

```python
python smart_hive_ws.py
```

```python
python smart_hive_ws.py --env staging
```

```python
python smart_hive_ws.py --env production
```


## Listen to both environments using websockets

```python
python ws_subscriber.py
```

## Listen to staging only
```python
python ws_subscriber.py --env staging
```

## Listen to production only
```python
python ws_subscriber.py --env production
```
