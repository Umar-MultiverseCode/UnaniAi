from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import google.generativeai as genai

# Gemini API Setup
genai.configure(api_key="AIzaSyCnLkFs3-8aufez4jPpQFnahj4ropCNBfg")
model = genai.GenerativeModel("gemini-1.5-flash")

def index(request):
    return render(request, 'index.html')

def chat_view(request):
    # This view is now for rendering the initial page
    return render(request, 'chat.html')

@csrf_exempt
def chatbot_response(request):
    if request.method == "POST":
        try:
            # Parsing the message from the request body
            data = json.loads(request.body)
            user_message = data.get("message", "")

            if not user_message:
                return JsonResponse({"error": "No message provided"}, status=400)

            # Call Gemini API to get a response
            response = model.generate_content(user_message)

            # Send back the response as a JSON
            return JsonResponse({"response": response.text})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)
