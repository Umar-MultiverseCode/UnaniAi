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

def generate_chat_response(user_message):
    """
    Generates a response from the Gemini AI using a custom prompt related to Unani Medicine.
    """
    # Custom prompt for Unani Medicine
    prompt = f"""
    You are an expert in Unani medicine. Your responses should be based on traditional Unani practices and remedies. 
    You can answer questions about diseases, remedies, treatments, and symptoms. Here are some examples:

    User: What is the remedy for fever in Unani medicine?
    Bot: In Unani medicine, fever can be treated using a combination of cooling herbs like Mint (Mentha), and herbal teas. Rest and hydration are also important.

    User: {user_message}
    Bot:
    """
    
    # Call the Gemini model with the custom prompt
    response = model.generate_content(prompt)
    return response.text.strip()

@csrf_exempt
def chatbot_response(request):
    if request.method == "POST":
        try:
            # Parsing the message from the request body
            data = json.loads(request.body)
            user_message = data.get("message", "")

            if not user_message:
                return JsonResponse({"error": "No message provided"}, status=400)

            # Get the response from the customized model (Unani Medicine focus)
            response = generate_chat_response(user_message)

            # Send the response back as JSON
            return JsonResponse({"response": response})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)
