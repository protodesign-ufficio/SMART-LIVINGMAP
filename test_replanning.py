"""
Script di test per inviare un messaggio di notifica simulato al topic Kafka 'notifications'.
Serve per verificare che il consumer in main.py riceva il messaggio e mostri la QMessageBox.
"""
import json
import time
from kafka import KafkaProducer

# Configuration matches the consumer
BOOTSTRAP_SERVERS = "87.26.178.190:29092"
TOPIC = "notifications"

def send_test_notification():
    try:
        producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Test message content
        message = {
            "msg_type": "replanning",
            "motivo": "LateCount > M",
            "timestamp": time.time()
        }
        
        print(f"Sending message to {TOPIC}...", flush=True)
        future = producer.send(TOPIC, message)
        result = future.get(timeout=10)
        
        print(f"Message sent successfully to partition {result.partition} at offset {result.offset}")
        producer.flush()
        producer.close()
        
    except Exception as e:
        print(f"Failed to send message: {e}")

if __name__ == "__main__":
    send_test_notification()
