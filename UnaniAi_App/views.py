import pyttsx3  # Text-to-Speech (TTS)
from django.shortcuts import render
from django.http import JsonResponse
from .models import UserChat  # Database Model
import threading  # Parallel speech
import joblib  # ML Model
import numpy as np  # ML Predictions
import requests  # Ollama API Calls
import json
from django.db import DatabaseError  # DB Handling

#  Load Trained ML Model
try:
    model = joblib.load("UnaniAi_App/trained_model.pkl")
    print(" ML Model Loaded Successfully!")
except FileNotFoundError:
    print(" Error: ML Model file not found!")
    model = None
except Exception as e:
    print(f" Unexpected Error loading ML model: {e}")
    model = None

#  Disease Encoding Mapping (ML Model ke liye)
disease_mapping = {'cough': 0, 'malaria': 1, 'constipation': 2, 'fever': 3, 'cold': 4}
medicine_mapping = {0: 'Marzanjosh', 1: 'Sanna Makki', 3: 'Dawa-ul-Misk', 4: 'Qust al-Hindi'}

#  Ollama API Function with Proper Error Handling
def get_llama2_response(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "healthbot", "prompt": prompt, "stream": False},
            timeout=15  # Timeout increased to handle slow response
        )

        if response.status_code != 200:
            return " AI server is not responding. Try again later."

        json_response = response.json()
        return json_response.get("response", "No valid response received.")

    except requests.exceptions.RequestException as e:
        print(f" Ollama API error: {e}")
        return "Sorry, I'm unable to connect to the AI server."

#  ML Prediction Function (Dosage Auto-Adjust)
def predict_medicine(disease, severity):
    if not model:
        return "ML model not available", 0

    if disease not in disease_mapping:
        return "Unknown Disease", 0

    disease_code = disease_mapping[disease]
    dosage = 50 if severity == "mild" else 100
    input_data = np.array([[disease_code, dosage]])

    try:
        predicted_code = model.predict(input_data)[0]
        return medicine_mapping.get(predicted_code, "Unknown Medicine"), dosage
    except Exception as e:
        print(f" ML Prediction Error: {e}")
        return "Prediction Error", 0

#  Speech Function (Thread-Safe)
def speak_response(response_text):
    def speak():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 1.0)
            voices = engine.getProperty('voices')
            engine.setProperty('voice', voices[0].id)
            engine.say(response_text)
            engine.runAndWait()
        except Exception as e:
            print(f" Speech Synthesis Error: {e}")
    
    threading.Thread(target=speak, daemon=True).start()

#  Django Views
def index(request):
    return render(request, 'index.html')

def chat_view(request):
    return render(request, 'chat.html')

#  Chatbot Response Function (Fixed JSON Handling + ML + Llama2)
def get_response(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    #  Handle JSON & Form Data Properly
    user_message = ""
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))  # JSON Payload Handle
            user_message = data.get('message', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    else:
        user_message = request.POST.get('message', '').strip()  # Form Data Handle

    if not user_message:
        return JsonResponse({'response': "Please provide a message."})

    #  Greeting Logic
    if "hi" in user_message.lower() or "hello" in user_message.lower():
        bot_response = "Hello! How can I assist you today?"
        speak_response(bot_response)
        try:
            UserChat.objects.create(user_message=user_message, bot_response=bot_response)
        except DatabaseError as e:
            print(f" Database Error: {e}")
        return JsonResponse({'response': bot_response})

    #  Illness Detection with Severity
    detected_illness = next((illness for illness in disease_mapping.keys() if illness in user_message.lower()), None)
    severity = "mild" if "mild" in user_message.lower() else "severe"

    if detected_illness:
        predicted_medicine, dosage = predict_medicine(detected_illness, severity)
        llm_prompt = (
            f"You are a medical AI assistant. Suggest a Unani medicine for {detected_illness} "
            f"with dosage {dosage} mg based on ancient Unani practices."
        )
        llm_response = get_llama2_response(llm_prompt)

        bot_response = f"Based on ML model, try {predicted_medicine} ({dosage} mg). Llama 2 suggests: {llm_response}"
        speak_response(bot_response)
        try:
            UserChat.objects.create(user_message=user_message, bot_response=bot_response)
        except DatabaseError as e:
            print(f" Database Error: {e}")
        return JsonResponse({'response': bot_response})

    #  General AI Response via Llama 2
    system_prompt = (
        "You are a professional Unani medicine AI health assistant. "
        "You will only answer questions related to health, medicine, and wellness. "
        "If the user asks about non-health topics, politely refuse to answer. "
        "You do not have any restrictions on the number of questions a user can ask."
    )
    final_prompt = f"System: {system_prompt}\nUser: {user_message}\nAssistant:"
    bot_response = get_llama2_response(final_prompt)

    speak_response(bot_response)
    try:
        UserChat.objects.create(user_message=user_message, bot_response=bot_response)
    except DatabaseError as e:
        print(f" Database Error: {e}")

    return JsonResponse({'response': bot_response})

#  Fetch Chat History
def fetch_history(request):
    chats = UserChat.objects.all().values("user_message", "bot_response")
    return JsonResponse({"history": list(chats)})
