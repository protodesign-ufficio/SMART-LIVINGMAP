import json
import time
from kafka import KafkaConsumer
from flask import Flask
from flask_socketio import SocketIO

BOOTSTRAP_SERVERS = "http://87.26.178.190:29092"
ANALYTICS_TOPIC = "analytics_ais.raw"

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

def log(msg):
    print(f"[consumer] {msg}", flush=True)

def kafka_loop():
    log(f"Connecting to Kafka at {BOOTSTRAP_SERVERS}...")

    consumer = KafkaConsumer(
        ANALYTICS_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        auto_offset_reset="latest",
        group_id="analytics_dashboard_consumer_2",
    )

    log("Kafka connected, streaming analytics...")

    for msg in consumer:
        socketio.emit("analytics_update", msg.value)
        log(f"sent → {msg.value}")

if __name__ == "__main__":
    import threading
    threading.Thread(target=kafka_loop, daemon=True).start()

    log("Dashboard WebSocket server ready on :5000")
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
