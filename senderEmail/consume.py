import logging
import os
import sys
import json
import time
import smtplib
from pathlib import Path
import requests

import pika # type: ignore
import django
import environ # type: ignore
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
import pybreaker



BASE_DIR = Path(__file__).resolve().parent.parent 
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

env = environ.Env()
environ.Env.read_env()


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "emailservice.settings")
django.setup()

# --- RabbitMQ / queue config
RABBITMQ_URL            = env("RABBITMQ_URL")
EXCHANGE_NAME           = env("EXCHANGE_NAME")
EMAIL_QUEUE             = env("EMAIL_QUEUE")
EMAIL_ROUTING_KEY       = env("EMAIL_ROUTING_KEY")
FAILED_QUEUE            = env("FAILED_QUEUE")
FAILED_ROUTING_KEY      = env("FAILED_ROUTING_KEY")
EXCHANGE_TYPE           = env("EXCHANGE_TYPE")
RETRY_QUEUE             = env("RETRY_QUEUE")
PREFETCH_COUNT          = 1

# title = None
# body = None
logger = logging.getLogger(__name__)


MAX_RETRIES = 3  # max send attempts per notification

smtp_breaker = pybreaker.CircuitBreaker(
    fail_max=5,               # trip after 5 consecutive failures
    reset_timeout=60,         # cooldown (seconds)
    name="smtp_breaker"
)

http_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    name="user_service_breaker"
)


data = {
    "reminder": {
        "title": "Hey {{user_name}}, don’t forget!",
        "body": "Your {{event_name}} is coming up on {{event_date}}. Tap to view details.",
        "image_url": "{{event_banner_url}}",
        "icon_url": "{{reminder_icon_url}}"
    },
    "welcome": {
        "title": "Welcome to {{app_name}} :wave:",
        "body": "Hi {{user_name}}, we’re excited to have you on board! Explore your dashboard to get started.",
        "image_url": "{{welcome_banner_url}}",
        "icon_url": "{{app_icon_url}}"
    }
}

def channel_publisher(channel, exchanger_name, routing_key, payload):

    channel.basic_publish(
        exchange=exchanger_name,
        routing_key=routing_key,
        body=json.dumps(payload),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # persistent
        ),
    )

def get_connection():
    """Create a blocking connection to RabbitMQ."""

    params = pika.URLParameters(RABBITMQ_URL)
    return pika.BlockingConnection(params)


def channel_connector(connection, worker_load_per_time):
    channel = connection.channel()

    # Ensure exchange & queues exist (idempotent)
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type=EXCHANGE_TYPE,
        durable=True,
    )

    channel.queue_declare(queue=EMAIL_QUEUE, durable=True)
    channel.queue_declare(queue=FAILED_QUEUE, durable=True)
    channel.queue_declare(
    queue=RETRY_QUEUE,
    durable=True,
    arguments={
        "x-dead-letter-exchange": EXCHANGE_NAME,
        "x-dead-letter-routing-key": EMAIL_ROUTING_KEY,
    },
)

    channel.queue_bind(queue=EMAIL_QUEUE, exchange=EXCHANGE_NAME, routing_key=EMAIL_ROUTING_KEY)
    channel.queue_bind(queue=FAILED_QUEUE, exchange=EXCHANGE_NAME, routing_key=FAILED_ROUTING_KEY)

    # Fair dispatch: one unacked message per worker at a time
    channel.basic_qos(prefetch_count=worker_load_per_time)


    return channel

def publish_failed(channel, payload: dict, reason: str):
    """
    Send permanently failed notifications to failed.queue.
    Gateway (or whoever) can consume this and update status.
    """
    failed_payload = {
        **payload,
        "status": "failed",
        "reason": reason,
    }

    channel_publisher(channel, EXCHANGE_NAME, FAILED_ROUTING_KEY, failed_payload)
    logger.error("routed to failed.queue: reason=%s", reason)


def republish_with_retry(channel, payload: dict, attempt: int):
    """
    Schedule a retry by publishing to RETRY_QUEUE with per-message TTL (exponential backoff).
    After TTL, RabbitMQ DLX routes it back to the main exchange/routing key.
    """
    next_attempt = attempt + 1
    delay = min(2 ** next_attempt * 1000, 120000)  # 2, 4, 8, ... seconds

    request_id =payload.get("request_id")
          


    # Update the payload for next attempt
    retry_payload = {**payload, "attempt": next_attempt}
    headers = {"x-retry-count": next_attempt}


    # Publish to RETRY_QUEUE with per-message TTL.
    # RabbitMQ will dead-letter it back to EXCHANGE_NAME → EMAIL_ROUTING_KEY
    # after the delay expires.
    channel.basic_publish(
        exchange="",
        routing_key=RETRY_QUEUE,  # send to retry queue, not main
        body=json.dumps(retry_payload),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # persistent
            headers=headers,
            expiration=str(delay),  # must be string, in milliseconds
        ),
    )

    logger.info("scheduled retry %s in %sms", next_attempt, delay)


@smtp_breaker
def send_email_with_id(payload: dict):
    """
    Send an email with an X-Notification-ID header so you can match it later in the webhook.
    """
    request_id = payload.get("request_id", "")
    to_email = payload.get("email", "")
    subject = payload.get("subject", "") 
    body = payload.get("body", "")
    # html_message = payload.get("rendered_content", "") 

    # html_message = render_to_string('senderEmail/welcome.html', {
    #     'user_email': to_email,
    #     'site_name': 'HNG 13 Stage 4 Group 37'
    # })
    # html_body = strip_tags(html_message)

    headers = {
        # Mailtrap's SMTP custom-variables header (JSON, <= 1000 bytes)
        "X-MT-Custom-Variables": json.dumps({"request_id": request_id}),
    }

    email = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=os.getenv("DEFAULT_FROM_EMAIL"),
        to=[to_email],
        headers=headers
    )

    # HTML alternative
    # email.attach_alternative(html_message, "text/html")


    email.send(fail_silently=False)
    print(f"✅ Sent email with X-Notification-ID={request_id}")


@http_breaker
def get_online_data(url):   
        response = requests.get(url, timeout=(5))
        response.raise_for_status()

        return response.json()
    # except Exception as e:
    #     return [None, str(e)]
    

def callback(channel, method, properties, body):
    """
    Main worker callback:
      - parses message
      - gets user details
      - gets requested template
      - sends email
      - handles retries
      - pushes to failed.queue on final failure
    """
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        raw_body = body.decode("utf-8", errors="replace")
        print("❌ Invalid JSON, discarding message")

        failed_pay_load = {
            "raw_body" : raw_body
        }

        publish_failed(channel, failed_pay_load, f"invalid_json: {e}")
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return
    
    if not isinstance(payload, dict):
        failed_pay_load = {
            "raw_body" : body.decode("utf-8", errors="replace")
        }

        publish_failed(channel, failed_pay_load, f"Payload is not a valid JSON object")
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return


    request_id = payload.get("request_id", None)
    user_id = payload.get("user_id", "")
    template_code = payload.get("template_code", "")
    variables = payload.get("variables", {})
    meta = payload.get("meta", {})
    attempt = int(payload.get("attempt", 0))

    print(f"\n📨 Received message: request_id={request_id} user_id={user_id}")

    if not isinstance(user_id, str) or not user_id.strip():
        publish_failed(channel, payload, "invalid_user_id")
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return
    
    try:
        try:
            user_detail = get_online_data(
                f"https://server-production-5772.up.railway.app/api/v1/users/{payload.get('user_id')}"
            )
        except pybreaker.CircuitBreakerError:
            if attempt + 1 < MAX_RETRIES:
                # User service breaker OPEN → don't hammer, defer
                republish_with_retry(channel, payload, attempt)
                channel.basic_ack(delivery_tag=method.delivery_tag)
                return

        print(user_detail)
        if user_detail.get("success", ""):
            

            if template_code == "reminder":
                title = f"Hey {user_detail.get("data").get("name")}, don't forget"
                body = f"Your {payload.get("variables", "").get("event_name", "")} is coming up on {payload.get("variables", "").get("event_date", "")}"
            elif template_code == "welcome":
                title= f"Welcome to {payload.get("variables", "").get("app_name", "")}"
                body= f"Hi {{user_name}}, we’re excited to have you on board! Explore your dashboard to get started."
            elif template_code == "update":
                title = "New Update Available :rocket:"
                body =  "We've rolled out new features and improvements. Update your app to enjoy the latest experience."
            else:
                publish_failed(channel, payload, f"Requested Template not found")
                channel.basic_ack(delivery_tag=method.delivery_tag)
                return

            
            # try:
            #     # notification_template = get_online_data(f"template_url")
            #     notification_template = get_online_data(
            #     f"https://server-production-5772.up.railway.app/api/v1/users/{payload.get('user_id')}"
            # )
            # except pybreaker.CircuitBreakerError:
            #     if attempt + 1 < MAX_RETRIES:
            #         # Template service breaker OPEN → don't hammer, defer
            #         republish_with_retry(channel, payload, attempt)
            #         channel.basic_ack(delivery_tag=method.delivery_tag)
            #         return


            
            # if notification_template.get("success", ""):
            #     # Get required template

                email_payload = {
                    "request_id" : request_id,
                    "email": (user_detail.get("data") or {}).get("email"),
                    "subject" : title,
                    "body" : body,
                    # "rendered_content" : notification_template.get("body"),
                }


                # --- SMTP SEND (breaker-aware) ---
                try:
                    send_email_with_id(email_payload)   # enable when ready to send for real
                    print(f"✅ Email sent for request_id={request_id}")
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                except pybreaker.CircuitBreakerError:
                    # smtp breaker OPEN → schedule retry
                    republish_with_retry(channel, payload, attempt)
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                    return
            # else:
            #     publish_failed(channel, payload, f"Requested Template not found")
            #     channel.basic_ack(delivery_tag=method.delivery_tag)
            #     return
        else:
            publish_failed(channel, payload, f"User Detail not found")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

    except (smtplib.SMTPException, OSError) as exc:
        # Transient / network / SMTP failure → retry or fail
        print(f"⚠️ Error sending email for request_id={request_id}: {exc}")

        if attempt + 1 < MAX_RETRIES:
            # Schedule retry by republishing with incremented attempt
            republish_with_retry(channel, payload, attempt)
            # Ack the current message (we've moved responsibility to the new one)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Max retries reached → send to failed.queue
            print(f"💣 Max retries reached for request_id={request_id}, moving to failed.queue")
            publish_failed(channel, payload, f"Max-retries reached: {str(exc)}")
            channel.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        # Unknown / fatal error → send straight to failed.queue
        print(f"🔥 Unexpected error for request_id={request_id}: {exc}")
        publish_failed(channel, payload, f"unexpected_error: {exc}")
        channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    connection = get_connection()
    channel = channel_connector(connection, PREFETCH_COUNT)

    channel.basic_consume(queue=EMAIL_QUEUE, on_message_callback=callback, auto_ack=False)
    logger.info("listening on %s (prefetch=%s)", EMAIL_QUEUE, PREFETCH_COUNT)


    try:
        channel.start_consuming()
        logger.info("connected to rabbitmq")
    except KeyboardInterrupt:
        logger.warning("rabbitmq connection closed …")
        channel.stop_consuming()
    finally:
        connection.close()
        logger.warning("rabbitmq connection closed …")



if __name__ == "__main__":
    main()
