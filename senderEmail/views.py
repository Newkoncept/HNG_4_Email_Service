from django.shortcuts import render
from django.http import HttpResponse
from django.core.mail import send_mail
import os
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests

@api_view(http_method_names=['GET'])
def health_checker(api_view):
    data =  {
        "service": "email",
        "rabbitmq_connected": True,
        "smtp_reachable": True,
        "breaker_state": "off"
    }
    return Response(data, status=200)


def home(request):
    return HttpResponse("Welcome home")


@csrf_exempt
def webHook(request):

    if request.method != "POST":
        return HttpResponse("method_not_allowed", status=405)

    if request.method == "POST":
        payload = json.loads(request.body.decode("utf-8"))

        events = payload.get("events", "")[0]

        if events:
            event = events.get("event")
            request_id = events.get("custom_variables").get("request_id")

            url = "https://gateway-production-2b55.up.railway.app/api/v1/email/status"
            headers = {
                "x-api-key": "abcdef"
            }

            

            


            if event == "delivery":
                payload = {
                    "notification_id": request_id,
                    "status": "delivered",
                    "timestamp": str(datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"))

                }
                response = requests.post(url, json=payload, headers=headers)
            else:
                payload = {
                    "notification_id": request_id,
                    "status": "bounce",
                    "timestamp": str(datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"))
                }
                response = requests.post(url, json=payload, headers=headers)


        print(f"Completed this webhook process by {datetime.now(timezone.utc)}")

        print("Received payload:", payload)
    
    return HttpResponse("webhook")
    


