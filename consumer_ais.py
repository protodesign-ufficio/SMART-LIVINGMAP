"""
Utility per il consumo dei messaggi AIS da Kafka in background.

Espone la classe `ConsumerAIS` che può essere avviata in un thread
e pubblica i messaggi su una `queue.Queue` passata dal chiamante.

Gli item messi in coda sono i dizionari già deserializzati (`msg.value`).
"""
import os
import json
import threading
import time
import traceback
from queue import Queue

from kafka import KafkaConsumer


class ConsumerAIS(threading.Thread):
    def __init__(self, out_queue: Queue, topic: str = "ais_decoded.raw", bootstrap: str = None, group_id: str = None):
        super().__init__(daemon=True)
        self.topic = topic
        self.out_queue = out_queue
        self._stop = threading.Event()
        self.bootstrap = bootstrap or os.getenv("KAFKA_BOOTSTRAP", "87.26.178.190:29092")
        self.group_id = group_id or os.getenv("KAFKA_GROUP", "navalviewer_ais")
        print(f"[ConsumerAIS] Initialized for topic '{self.topic}' on bootstrap '{self.bootstrap}' with group_id '{self.group_id}'", flush=True)

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap,
                group_id=self.group_id,
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")) if v else None,
                auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET", "latest"),
                consumer_timeout_ms=1000,
            )
            # connected
        except Exception:
            # failed to create consumer
            return

        try:
            while not self._stop.is_set():
                try:
                    for msg in consumer:
                        if self._stop.is_set():
                            break
                        try:
                            if msg is None:
                                continue
                            value = msg.value
                            # push to queue for main thread processing
                            try:
                                self.out_queue.put_nowait(value)
                            except Exception:
                                # fallback blocking put
                                self.out_queue.put(value)
                        except Exception:
                            # error processing message
                            pass
                    # small sleep to avoid tight loop on timeout
                    time.sleep(0.01)
                except Exception:
                    # consumer loop error
                    time.sleep(1)
        finally:
            try:
                consumer.close()
            except Exception:
                pass


if __name__ == '__main__':
    # run standalone for debug: print incoming values
    q = Queue()
    c = ConsumerAIS(q)
    c.start()
    try:
        while True:
            try:
                item = q.get(timeout=1)
                logging.info("Received AIS (standalone): %s", item)
            except Exception:
                pass
    except KeyboardInterrupt:
        c.stop()
        c.join()

