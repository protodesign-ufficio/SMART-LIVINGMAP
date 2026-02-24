"""
Consumer per la gestione delle notifiche da Kafka.
Ascolta il topic 'notifications' e emette un segnale PyQt quando riceve un messaggio
per mostrare una QMessageBox nel thread principale.
"""
import os
import json
import threading
import time
import traceback
from PyQt5.QtCore import QObject, pyqtSignal
from kafka import KafkaConsumer

# Configuration
BOOTSTRAP_SERVERS = "87.26.178.190:29092"
NOTIFICATIONS_TOPIC = "notifications"

class ConsumerNotification(QObject):
    """
    Consumer Kafka che gira in un thread separato e emette segnali
    quando arrivano notifiche.
    """
    # Segnale emesso quando arriva un messaggio: dizionario del messaggio
    notificationReceived = pyqtSignal(dict)

    def __init__(self, bootstrap: str = None, topic: str = NOTIFICATIONS_TOPIC):
        super().__init__()
        self.topic = topic
        self.bootstrap = bootstrap or os.getenv("KAFKA_BOOTSTRAP", BOOTSTRAP_SERVERS)
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Avvia il thread di ascolto."""
        if self._thread is None:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Ferma il thread di ascolto."""
        if self._thread:
            self._stop_event.set()
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run_loop(self):
        """Loop principale del consumer."""
        consumer = None
        current_retry = 0
        max_retries = 5

        try:
            # Configurazione senza group_id per ricevere tutti i messaggi come broadcast/stateless
            # o semplicemente per non committare offset in gruppo.
            consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap,
                group_id=None,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")) if v else None,
                auto_offset_reset='latest', # Ascolta solo nuovi messaggi all'avvio
                consumer_timeout_ms=1000
            )
            print(f"[ConsumerNotification] Connected to Kafka at {self.bootstrap} for topic '{self.topic}'", flush=True)

            while not self._stop_event.is_set():
                try:
                    # Poll for messages
                    msg_dict = consumer.poll(timeout_ms=1000)
                    
                    if not msg_dict:
                        continue

                    for topic_partition, messages in msg_dict.items():
                        for msg in messages:
                            if self._stop_event.is_set():
                                break
                            
                            try:
                                value = msg.value
                                # Emetti il segnale con il dizionario del messaggio
                                if isinstance(value, dict):
                                    self.notificationReceived.emit(value)
                                else:
                                    # Fallback per messaggi non strutturati
                                    self.notificationReceived.emit({"msg_type": "notification_base", "message": str(value)})
                            except Exception as e:
                                print(f"[ConsumerNotification] Error processing message: {e}", flush=True)

                except Exception as e:
                    print(f"[ConsumerNotification] Error in poll loop: {e}", flush=True)
                    time.sleep(1)

        except Exception as e:
            print(f"[ConsumerNotification] Connection error: {e}", flush=True)
        finally:
            if consumer:
                try:
                    consumer.close()
                except:
                    pass
            print("[ConsumerNotification] Stopped.", flush=True)
