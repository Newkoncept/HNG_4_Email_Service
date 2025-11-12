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

        # events = (payload.get("events") or [])
        # if not events:
        #     return HttpResponse("ok")  # nothing to process

        # evt = events[0]
        # custom = evt.get("custom_variables") or {}
        # request_id = custom.get("request_id")
        # event = (evt.get("event") or "").lower()

        events = payload.get("events", "")[0]

        if events:
            event = events.get("event")
            request_id = events.get("custom_variables").get("request_id")

            if event == "delivery":
                pass #logic to update the DB with current status
            elif event == "bounce":
                pass #logic to update the DB with current status
            elif event == "soft bounce":
                pass #logic to update the DB with current status



        print(f"Completed this webhook process by {datetime.now(timezone.utc)}")

        print("Received payload:", payload)
    
    return HttpResponse("webhook")
    


