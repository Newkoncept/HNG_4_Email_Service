import pika, json
from uuid import uuid4

def populate():
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    channel.exchange_declare(exchange="hng_stage_four", exchange_type="direct", durable=True)

    # Send an example email message
    message = {
        "request_id": str(uuid4()),
        "to_email": "taiwoemmanuel15@gmail.com",
        "subject": "Test Email",
        "body": "This is a mock test email.",
        "attempt": 0
    }

    channel.basic_publish(
        exchange="hng_stage_four",
        routing_key="email",
        body=json.dumps(message),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # persistent
        )
    )

    print(" [x] Sent mock email message")
    connection.close()


if __name__ == "__main__":
    populate()