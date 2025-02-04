import pyttsx3  # Import pyttsx3 for text-to-speech
from django.shortcuts import render
from django.http import JsonResponse
from .models import UserChat  # Import the UserChat model
import threading  # For running speech and text concurrently
import joblib  # ML model ke liye
import numpy as np  # ML prediction ke liye

# ✅ Load trained ML model
model = joblib.load("UnaniAi_App/trained_model.pkl")

# ✅ Disease encoding mapping (ML model ke liye)
disease_mapping = {'cough': 0, 'malaria': 1, 'constipation': 2}
medicine_mapping = {0: 'Marzanjosh', 1: 'Sanna Makki'}

# ✅ Disease-medication mapping
diseases_medications = {
    "cough": ("Marzanjosh", "https://aetmaad.co.in/product/al-marzanjosh", 300),
    "malaria": ("Sanna Makki", "https://aetmaad.co.in/product/sanna-makki", 70),
    "constipation": ("Sanna Makki", "https://aetmaad.co.in/product/sanna-makki", 70),
}

# ✅ Base questions for each illness (Yahi miss ho gaya tha 🤦‍♂️)
base_questions = {
    "cough": [
        "How long have you been experiencing this issue?",
        "Are you currently taking any medication? (Yes/No)",
        "If yes, which medication are you taking?",
        "Do you have any allergies? (Yes/No)",
        "If yes, what are you allergic to?",
    ],
    "malaria": [
        "How long have you been experiencing this issue?",
        "Are you currently taking any medication? (Yes/No)",
        "If yes, which medication are you taking?",
        "Do you have any allergies? (Yes/No)",
        "If yes, what are you allergic to?",
    ],
    "constipation": [
        "How long have you been experiencing this issue?",
        "Are you currently taking any medication? (Yes/No)",
        "If yes, which medication are you taking?",
        "Do you have any allergies? (Yes/No)",
        "If yes, what are you allergic to?",
    ],
}

# ✅ ML Prediction Function
def predict_medicine(disease, dosage):
    if disease not in disease_mapping:
        return "Unknown Disease"

    disease_code = disease_mapping[disease]
    input_data = np.array([[disease_code, dosage]])
    predicted_code = model.predict(input_data)[0]
    
    return medicine_mapping.get(predicted_code, "Unknown Medicine")

# Function to make bot speak while generating response in background
def speak_response(response_text):
    def speak():
        engine = pyttsx3.init()  # Initialize the TTS engine
        voices = engine.getProperty('voices')  # Get available voices
        engine.setProperty('voice', voices[0].id)  # Set male voice (usually index 0 for male)
        engine.say(response_text)  # Pass the response to the engine
        engine.runAndWait()  # Play the speech
    
    # Run the speaking function in a separate thread
    threading.Thread(target=speak).start()

# Chat Views
def index(request):
    return render(request, 'index.html')

def chat_view(request):
    return render(request, 'chat.html')

# Get response based on user input
def get_response(request):
    if request.method == 'POST':
        # Get user message safely
        user_message = request.POST.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'response': "Please provide a message."})

        # Greeting logic
        if "hi" in user_message.lower() or "hello" in user_message.lower():
            bot_response = "Hello! How can I assist you today?"
            speak_response(bot_response)  # Speak the response and return the text
            UserChat.objects.create(user_message=user_message, bot_response=bot_response)
            return JsonResponse({'response': bot_response})

        # Illness detection logic
        detected_illness = next((illness for illness in base_questions.keys() if illness in user_message.lower()), None)

        # If illness detected, start asking questions
        if detected_illness:
            request.session['current_illness'] = detected_illness
            request.session['current_question_index'] = 0
            request.session['user_responses'] = {}

            bot_response = base_questions[detected_illness][0]
            speak_response(bot_response)  # Speak the response and return the text
            UserChat.objects.create(user_message=user_message, bot_response=bot_response)
            return JsonResponse({'response': bot_response})

        # Proceed with question flow if illness is already being tracked
        current_illness = request.session.get('current_illness', None)
        current_question_index = request.session.get('current_question_index', 0)
        user_responses = request.session.get('user_responses', {})

        if current_illness:
            current_question = base_questions[current_illness][current_question_index]
            
            # Condition: Ensure duration is in days/weeks/years
            if current_question == "How long have you been experiencing this issue?" and not any(
                unit in user_message.lower() for unit in ["days", "weeks", "years"]
            ):
                bot_response = "Please specify the duration in days, weeks, or years."
                speak_response(bot_response)  # Speak the response and return the text
                return JsonResponse({'response': bot_response})

            user_responses[current_question] = user_message.lower()
            request.session['user_responses'] = user_responses

            # Determine next question based on response
            if current_question.startswith("Are you currently taking any medication?") and user_message.lower() == "no":
                current_question_index += 2  
            elif current_question.startswith("Do you have any allergies?") and user_message.lower() == "no":
                current_question_index += 1  
            else:
                current_question_index += 1

            if current_question_index < len(base_questions[current_illness]):
                request.session['current_question_index'] = current_question_index
                bot_response = base_questions[current_illness][current_question_index]
            else:
                # ✅ Final medication recommendation using ML Model
                dosage = 100  # Default dosage (Aap isse modify kar sakte ho)
                predicted_medicine = predict_medicine(current_illness, dosage)

                bot_response = f"For {current_illness}, you can try {predicted_medicine}."
                
                del request.session['current_illness']
                del request.session['current_question_index']
                del request.session['user_responses']

            speak_response(bot_response)  # Speak the response and return the text
            UserChat.objects.create(user_message=user_message, bot_response=bot_response)
            return JsonResponse({'response': bot_response})

        # Response for "thanks" or other unrecognized inputs
        elif "thanks" in user_message.lower():
            bot_response = "You're welcome! Let me know if you need further assistance."
            speak_response(bot_response)  # Speak the response and return the text
            UserChat.objects.create(user_message=user_message, bot_response=bot_response)
            return JsonResponse({'response': bot_response})

        # Default response if no logic is matched
        else:
            bot_response = "I’m sorry, I didn’t understand that. Can you please clarify?"
            speak_response(bot_response)  # Speak the response and return the text
            UserChat.objects.create(user_message=user_message, bot_response=bot_response)
            return JsonResponse({'response': bot_response})

    return JsonResponse({'error': 'Invalid request method'}, status=400)

def fetch_history(request):
    chats = UserChat.objects.all().values("user_message", "bot_response")  # सभी conversation को DB से लाओ
    return JsonResponse({"history": list(chats)})  # JSON format में response दो
