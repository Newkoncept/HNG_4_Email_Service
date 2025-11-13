import pika, json
from uuid import uuid4

def populate():
    # connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    connection = pika.BlockingConnection(pika.URLParameters("amqps://nqdlzpvs:Tj5-G0boaSyrS1nZFM4aL9ElaiSeKTmW@chameleon.lmq.cloudamqp.com/nqdlzpvs/"))
    channel = connection.channel()

    channel.exchange_declare(exchange="notification", exchange_type="direct", durable=True)

    message = {
  "notification_type": "email",
  "user_id": "8e84e565-36af-4c1f-9f1b-9016c3a08acc",
  "template_code": "reminder",
  "variables": {
    "name": "Alex Smith",
    "link": "https://example.com/activate",
    "meta": {},
    "event_name": "Birthday ",
    "event_date": "15th Nov"
  },
  "request_id": "req-email-12345",
  "priority": 3,
  "metadata": {}
}
    
    channel.basic_publish(
        # exchange="hng_stage_four",
        exchange="notification",
        routing_key="email",
        body=json.dumps(message),
        # body=message,
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # persistent
        )
    )

    print(" [x] Sent mock email message")
    connection.close()


populate()