# 📧 Email Service — HNG Stage 4 Distributed Notification System

This microservice is part of the **HNG Stage 4 Distributed Notification System**.  
It is responsible for **processing email notifications** asynchronously via **RabbitMQ**, using **SMTP (Mailtrap)** for message delivery.

---

## 🧭 Overview

The Email Service consumes messages from the RabbitMQ exchange `notifications.direct`.  
It:
- Reads from `email.queue`
- Fills and sends templated emails via SMTP (Mailtrap)
- Retries failed sends with exponential backoff
- Moves permanently failed messages to a dead-letter queue (`failed.queue`)
- Exposes a webhook endpoint to receive delivery/bounce updates from the SMTP provider
- Supports horizontal scaling (multiple consumers)
- Includes a `/health` endpoint for monitoring

---

## 🏗️ System Architecture

```
          ┌──────────────────┐
          │  API Gateway     │
          │  (Publishes)     │
          └──────┬───────────┘
                 │
         Exchange: notifications.direct
                 │
    ┌────────────┼─────────────┐
    │                            │
┌──────────────┐          ┌────────────────┐
│ email.queue  │          │ push.queue     │
│ (Email Svc)  │          │ (Push Svc)     │
└──────┬───────┘          └────────────────┘
       │
       ▼
┌────────────────────────────────────────┐
│ Email Service                          │
│ - Consumes from email.queue             │
│ - Retries w/ backoff                    │
│ - Sends via SMTP (Mailtrap)             │
│ - Dead letters → failed.queue           │
└────────────────────────────────────────┘
```

---

## ⚙️ Features

✅  Reads messages from RabbitMQ (`email.queue`)  
✅  Sends emails using SMTP (Mailtrap sandbox)  
✅  Retries with exponential backoff (2ⁿ seconds)  
✅  Moves permanently failed messages to `failed.queue`  
✅  Competing consumers for horizontal scaling  
✅  Durable queues & persistent messages  
✅  Webhook endpoint for delivery/bounce updates  
✅  `/health` route for service monitoring  

---

## 🧩 Tech Stack

| Component | Technology |
|------------|-------------|
| Language | Python 3.11 + Django |
| Queue Broker | RabbitMQ (via pika) |
| Mail Provider | Mailtrap SMTP |
| Container | Docker |
| CI/CD | GitHub Actions |
| Template Engine | Django Templates |

---

## 🚀 Getting Started

### 1️⃣ Clone the repository
```bash
git clone https://github.com/<your-org>/emailservice.git
cd emailservice
```

### 2️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Environment variables
Create a `.env` file in the root directory:

```env
# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2f
RABBIT_EXCHANGE=notifications.direct
EMAIL_QUEUE=email.queue
FAILED_QUEUE=failed.queue
EMAIL_ROUTING_KEY=email
FAILED_ROUTING_KEY=failed
MAX_RETRIES=5

# SMTP (Mailtrap)
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=<your-mailtrap-username>
SMTP_PASS=<your-mailtrap-password>
SMTP_FROM=no-reply@example.com
ENABLE_EMAIL_SENDING=true

# Django
DEFAULT_FROM_EMAIL=no-reply@example.com
```

### 4️⃣ Start RabbitMQ
```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

### 5️⃣ Run the Email Service
```bash
python senderEmail/consume.py
```

Multiple instances can run concurrently for horizontal scaling.

---

## 🧪 Testing

Publish a sample message to the exchange:

```bash
rabbitmqadmin publish exchange=notifications.direct routing_key=email payload='{
  "notification_id": "test-123",
  "to_email": "user@example.com",
  "subject": "Welcome!",
  "body": "This is a test email.",
  "attempt": 0
}'
```

Expected behaviour:
- Email sent successfully via Mailtrap
- Retries handled automatically on SMTP failure
- Permanently failed messages routed to `failed.queue`

---

## 🌐 Webhook Endpoint

Mailtrap (or another provider) posts delivery/bounce events to:
```
POST /senderEmail/webhook
```

**Sample incoming event (Mailtrap format):**
```json
{
  "events": [
    {
      "event": "delivery",
      "message_id": "a3cb4980-bfb5-11f0-0040-f1bdef5ba970",
      "email": "user@example.com",
      "timestamp": 1762944731
    }
  ]
}
```

**Normalized output sent to Gateway:**
```json
{
  "notification_id": "uuid-of-notification",
  "status": "delivered",
  "provider_message_id": "a3cb4980-bfb5-11f0-0040-f1bdef5ba970",
  "timestamp": "2025-11-12T10:52:22Z"
}
```

---

## ❤️ Health Check
```
GET /health
→ 200 OK
{
  "service": "email",
  "status": "ok"
}
```


---

## 🧠 Key Concepts Implemented

- **Microservices Architecture:** independent email, push, gateway, template, and user services  
- **Asynchronous Messaging:** RabbitMQ direct exchange with durable queues  
- **Retry + Backoff:** exponential backoff and DLQ on permanent failure  
- **Idempotency:** handled by Gateway (`request_id` → `notification_id`)  
- **Health Monitoring:** simple HTTP /health endpoint  
- **Horizontal Scaling:** multiple workers consuming concurrently  

---

## 🧾 License

MIT License © 2025 HNG Stage 4 Team 37

---

## 👥 Authors

| Name | Role | GitHub |
|------|------|--------|
| Emmanuel Taiwo | Email Service Developer | [@taiwoemmanuel15](https://github.com/taiwoemmanuel15) |
| Team 37 Members | Gateway / Push / Template / User Services | — |

---
