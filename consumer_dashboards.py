import json
import threading
from kafka import KafkaConsumer
from flask import Flask
from flask_socketio import SocketIO
import time

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------
# NOTE: bootstrap servers must be host:port (no http scheme)
BOOTSTRAP_SERVERS = "87.26.178.190:29092"
ANALYTICS_TOPIC = "analytics_ais.raw"
DELTA_ETA_SIM_TTL_SEC = 60

# ----------------------------------------------------
# APP
# ----------------------------------------------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

def log(msg):
    print(f"[ConsumerDashboard] {msg}", flush=True)

# ----------------------------------------------------
# STATE (CACHE IN MEMORIA)
# ----------------------------------------------------
STATE = {
    "delta_eta": {},        # mmsi -> last delta_eta msg
    "berth_incoming": {},   # destination -> last berth msg
    "component_usage": {}   # mmsi -> component -> last usage msg
}


def _is_simulation_msg(data: dict) -> bool:
    source = str(data.get("source", "")).strip().lower()
    if source == "simulation":
        return True
    return data.get("is_simulation") is True


def purge_stale_delta_eta() -> None:
    now = time.time()
    to_delete = []

    for mmsi, entry in STATE["delta_eta"].items():
        if isinstance(entry, dict) and "data" in entry:
            data = entry.get("data") or {}
            received_at = float(entry.get("received_at") or 0)
        else:
            # Backward compatibility with old cache shape: mmsi -> msg
            data = entry or {}
            received_at = 0

        if _is_simulation_msg(data):
            if received_at <= 0 or (now - received_at) > DELTA_ETA_SIM_TTL_SEC:
                to_delete.append(mmsi)

    for mmsi in to_delete:
        STATE["delta_eta"].pop(mmsi, None)

# ----------------------------------------------------
# KAFKA LOOP
# ----------------------------------------------------
def kafka_loop():
    log(f"Connecting to Kafka at {BOOTSTRAP_SERVERS}...")

    consumer = KafkaConsumer(
        ANALYTICS_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        auto_offset_reset="latest",
        # group_id="analytics_dashboard_consumer_2",
    )

    log("Kafka connected, streaming analytics...")

    for msg in consumer:
        data = msg.value
        msg_type = data.get("type")

        # -------------------------
        # UPDATE STATE
        # -------------------------
        if msg_type == "delta_eta":
            mmsi = data.get("mmsi")
            if mmsi:
                STATE["delta_eta"][mmsi] = {
                    "data": data,
                    "received_at": time.time(),
                }
                purge_stale_delta_eta()

        elif msg_type == "berth_incoming":
            dest = data.get("destination")
            if dest:
                STATE["berth_incoming"][dest] = data

        elif msg_type == "component_usage":
            mmsi = data.get("mmsi")
            comp = data.get("component")
            if mmsi and comp:
                STATE["component_usage"].setdefault(mmsi, {})[comp] = data

        # -------------------------
        # LIVE PUSH
        # -------------------------
        socketio.emit("analytics_update", data)
        # log(f"sent → {data}")

# ----------------------------------------------------
# SOCKET.IO: SNAPSHOT ON CONNECT
# ----------------------------------------------------
@socketio.on("connect")
def on_connect():
    log("Client connected → replaying state as analytics_update")

    purge_stale_delta_eta()

    # delta_eta
    for entry in STATE["delta_eta"].values():
        msg = entry.get("data") if isinstance(entry, dict) and "data" in entry else entry
        socketio.emit("analytics_update", msg)

    # berth_incoming
    for msg in STATE["berth_incoming"].values():
        socketio.emit("analytics_update", msg)

    # component_usage
    for comps in STATE["component_usage"].values():
        for msg in comps.values():
            socketio.emit("analytics_update", msg)


# ----------------------------------------------------
# RUN
# ----------------------------------------------------

def start_dashboard(host="0.0.0.0", port=5000):
    """Start kafka consumer and socketio server in background threads.

    This function is non-blocking and returns after threads are started.
    """
    # start kafka loop in a daemon thread
    threading.Thread(target=kafka_loop, daemon=True).start()

    # run socketio server in a separate daemon thread
    def _run_socketio():
        log(f"Dashboard WebSocket server ready on :{port}")
        socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)

    t = threading.Thread(target=_run_socketio, daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    start_dashboard()