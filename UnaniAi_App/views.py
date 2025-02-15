import re
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import google.generativeai as genai

# Gemini API Setup
genai.configure(api_key="AIzaSyCnLkFs3-8aufez4jPpQFnahj4ropCNBfg")
model = genai.GenerativeModel("gemini-1.5-flash")

# Temporary Unani Medicine Database
unani_medicines = {
    "fever": {
        "symptoms": ["High temperature", "Sweating", "Chills", "Body ache"],
        "treatment": ["Drink herbal mint tea", "Apply sandalwood paste", "Stay hydrated"],
        "medicine": [
            {"name": "Hamdard Joshina", "link": "https://www.amazon.in/dp/B08XYZ1234"},
            {"name": "Dabur Tulsi Drops", "link": "https://www.dabur.com/tulsi-drops"}
        ]
    },
    "cough": {
        "symptoms": ["Dry throat", "Chest congestion", "Difficulty breathing"],
        "treatment": ["Take honey with ginger", "Drink liquorice root tea"],
        "medicine": [
            {"name": "Hamdard Khamira Marwareed", "link": "https://www.hamdarsonlinestore.com/khamira-marwareed"},
            {"name": "Baidyanath Chyawanprash", "link": "https://www.baidyanath.com/chyawanprash"}
        ]
    }
}

def index(request):
    return render(request, 'index.html')

def chat_view(request):
    return render(request, 'chat.html')

def remove_markdown_formatting(text):
    """
    Removes any markdown-style formatting (e.g., **bold** or *italic*) from the response text.
    """
    text = re.sub(r'(\*\*|\*|__|_)(.*?)\1', r'\2', text)  # Removes **bold** or *italic*
    text = re.sub(r'\n\s*\*\s*(.*)', r'\1', text)  # Removes bullet points (list formatting)
    return text.strip()

def get_unani_remedy(disease):
    """
    Fetches Unani treatment details along with medicine links.
    """
    disease = disease.lower()
    if disease in unani_medicines:
        data = unani_medicines[disease]
        response = f"**Unani Treatment for {disease.capitalize()}**\n"
        response += f"🔹 **Symptoms:** {', '.join(data['symptoms'])}\n"
        response += f"🩺 **Treatment:** {', '.join(data['treatment'])}\n"

        if "medicine" in data and data["medicine"]:
            response += "\n🛒 **Recommended Medicines:**\n"
            for med in data["medicine"]:
                response += f"🔹 [{med['name']}]({med['link']})\n"

        return response
    else:
        return None  # Disease not found

def generate_chat_response(user_message):
    """
    Checks Unani medicine database first, then calls Gemini AI if needed.
    """
    words = user_message.lower().split()
    for word in words:
        remedy = get_unani_remedy(word)
        if remedy:
            return remedy  # Returns treatment + medicine links

    # If no disease is found in database, use Gemini AI
    prompt = f"""
    You are an expert in Unani medicine. Answer based on Unani principles.

    User: {user_message}
    Bot:
    """
    response = model.generate_content(prompt)
    return response.text

@csrf_exempt
def chatbot_response(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")

            if not user_message:
                return JsonResponse({"error": "No message provided"}, status=400)

            response = generate_chat_response(user_message)

            return JsonResponse({"response": response})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)
