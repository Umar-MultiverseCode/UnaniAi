import re
import sqlite3
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
import json
import google.generativeai as genai
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from datetime import datetime
import requests

# Gemini API Setup
genai.configure(api_key="AIzaSyCnLkFs3-8aufez4jPpQFnahj4ropCNBfg")
model = genai.GenerativeModel("gemini-1.5-flash")

# Google Places API Key (replace with your actual key)
GOOGLE_PLACES_API_KEY = "YOUR_GOOGLE_PLACES_API_KEY"

# SQLite Database Setup
def create_database():
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Medicine Reminders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicine_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            medicine_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            schedule TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Unani Ingredients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unani_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_name TEXT NOT NULL,
            benefits TEXT NOT NULL,
            usage TEXT NOT NULL,
            diseases TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()
    print("Database and tables created successfully!")
create_database()

# Temporary Unani Medicine Database
unani_medicines = {
    "cough": {
        "symptoms": ["Dry throat", "Chest congestion", "Difficulty breathing"],
        "treatment": ["Take honey with ginger", "Drink liquorice root tea"],
        "ingredients": [
            {"name": "Ginger", "dosage": "1 tsp grated", "benefits": "Clears congestion", "precautions": "Avoid on empty stomach"},
            {"name": "Honey", "dosage": "1-2 tsp", "benefits": "Soothes throat", "precautions": "Moderation needed"}
        ],
        "medicine": [{"name": "Marzanjosh", "link": "https://aetmaad.co.in/product/al-marzanjosh", "price": 300}]
    },
    "fever": {
        "symptoms": ["High temperature", "Sweating", "Chills", "Body ache"],
        "treatment": ["Drink herbal mint tea", "Apply sandalwood paste", "Stay hydrated"],
        "ingredients": [
            {"name": "Honey", "dosage": "1-2 tsp daily", "benefits": "Boosts immunity", "precautions": "Avoid excess if diabetic"},
            {"name": "Mint", "dosage": "Boil in tea", "benefits": "Reduces fever", "precautions": "Avoid if allergic"}
        ],
        "medicine": [{"name": "Tulsi Honey", "link": "https://aetmaad.co.in/product/tulsi-honey", "price": 600}]
    },
    # Add other diseases from your original list similarly with ingredients
}

# Populate Unani Ingredients Database
def populate_unani_ingredients():
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    unani_ingredients = [
        {"ingredient_name": "Ginger", "benefits": "Clears congestion", "usage": "1 tsp grated in tea", "diseases": "cough, cold"},
        {"ingredient_name": "Honey", "benefits": "Soothes throat, Boosts immunity", "usage": "1-2 tsp daily", "diseases": "cough, fever, sore throats"},
        {"ingredient_name": "Mint", "benefits": "Reduces fever", "usage": "Boil in tea", "diseases": "fever"},
        {"ingredient_name": "Turmeric", "benefits": "Anti-inflammatory", "usage": "1/2 tsp in milk", "diseases": "cold, infections"},
    ]
    for ingredient in unani_ingredients:
        cursor.execute('''
            INSERT OR IGNORE INTO unani_ingredients (ingredient_name, benefits, usage, diseases)
            VALUES (?, ?, ?, ?)
        ''', (ingredient["ingredient_name"], ingredient["benefits"], ingredient["usage"], ingredient["diseases"]))
    conn.commit()
    conn.close()
    print("Unani ingredients database populated successfully!")
populate_unani_ingredients()

# Fetch Unani Ingredients for a Disease
def get_unani_ingredients(disease):
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ingredient_name, benefits, usage
        FROM unani_ingredients
        WHERE diseases LIKE ?
    ''', (f"%{disease}%",))
    ingredients = cursor.fetchall()
    conn.close()
    return [{"name": i[0], "benefits": i[1], "usage": i[2]} for i in ingredients]

class UnaniAI:
    def __init__(self):
        self.conversation_history = []
        self.language = "hinglish"  # Default to Hinglish

    def generate_chat_response(self, user_message):
        user_message_lower = user_message.lower().strip()
        words = user_message_lower.split()
        self.conversation_history.append(user_message)

        # Language Switch
        if "talk in english" in user_message_lower:
            self.language = "english"
            return "<p style='color: #ffffff;'>Alright! English mode on. How can I help you today?</p>"
        elif "hindi mein baat kar" in user_message_lower:
            self.language = "hindi"
            return "<p style='color: #ffffff;'>ठीक है! अब हिंदी में बात करूंगा। आपको क्या तकलीफ है?</p>"
        elif "talk in hinglish" in user_message_lower:
            self.language = "hinglish"
            return "<p style='color: #ffffff;'>Arre bhai, Hinglish mode on hai! Kya scene hai, bolo?</p>"

        # Greeting Handling
        greetings = ["hello", "hi", "sala", "assalam", "as-salam", "salaam"]
        if any(user_message_lower.startswith(greet) for greet in greetings):
            if self.language == "english":
                return "<p style='font-style: italic; color: #ffffff;'>As-salamu Alaikum! I’m here to help you with care. What’s up?</p>"
            elif self.language == "hindi":
                return "<p style='font-style: italic; color: #ffffff;'>अस्सलामु अलैकुम! मैं आपकी मदद के लिए हूँ। आज क्या परेशानी है?</p>"
            else:  # Hinglish
                return "<p style='font-style: italic; color: #ffffff;'>As-salamu Alaikum bhai! Teri help ke liye ready hoon—kya chal raha hai?</p>"

        # Personal Queries
        if "who are you" in user_message_lower or "aap kaun ho" in user_message_lower:
            if self.language == "english":
                return "<p style='color: #ffffff;'>I am UnaniAI, created by a Student of AIKTC. I’m here to give you natural Unani remedies. How can I assist?</p>"
            elif self.language == "hindi":
                return "<p style='color: #ffffff;'>मैं UnaniAI हूँ, AIKTC के एक स्टूडेंट ने बनाया है। प्राकृतिक यूनानी इलाज के लिए हूँ। कैसे मदद करूँ?</p>"
            else:  # Hinglish
                return "<p style='color: #ffffff;'>Main UnaniAI hoon bhai, AIKTC ke ek student ne banaya! Natural remedies deta hoon—kya chahiye tujhe?</p>"

        # Medical Query Handling
        medical_keywords = list(unani_medicines.keys()) + ["pain", "headache", "stamina", "energy"]
        is_medical = any(keyword in user_message_lower for keyword in medical_keywords)
        context_diseases = [word for word in words if word in unani_medicines]
        wants_table = "table" in user_message_lower or "plan" in user_message_lower

        if is_medical or context_diseases or wants_table:
            diseases = context_diseases if context_diseases else self._get_last_medical_context(return_list=True)
            if not diseases and wants_table:
                last_disease = self._get_last_medical_context()
                if last_disease:
                    diseases = [last_disease]
                else:
                    return "<p style='color: #ffffff;'>Bhai, pehle koi disease batao, phir table dunga!</p>" if self.language == "hinglish" else "<p style='color: #ffffff;'>Please tell me a condition first, then I’ll give you a table!</p>"

            if diseases:
                if wants_table:
                    table_rows = ""
                    for disease in diseases[:3]:
                        if disease in unani_medicines:
                            data = unani_medicines[disease]
                            ingredients = get_unani_ingredients(disease) or data.get("ingredients", [])
                            unique_ingredients = {ing["name"]: ing for ing in ingredients}.values()  # Remove duplicates
                            for ing in unique_ingredients:
                                table_rows += f"""
                                    <tr style='border: 1px solid #ddd; background-color: #ffffff;'>
                                        <td style='padding: 10px; color: #333;'>{ing['name']} ({disease.capitalize()})</td>
                                        <td style='padding: 10px; color: #333;'>{ing.get('dosage', ing.get('usage', 'As advised'))}</td>
                                        <td style='padding: 10px; color: #333;'>{ing['benefits']}</td>
                                        <td style='padding: 10px; color: #333;'>{ing.get('precautions', 'None')}</td>
                                    </tr>
                                """
                            for med in data.get("medicine", []):
                                table_rows += f"""
                                    <tr style='border: 1px solid #ddd; background-color: #ffffff;'>
                                        <td style='padding: 10px; color: #333;'>{med['name']} ({disease.capitalize()})</td>
                                        <td style='padding: 10px; color: #333;'>As prescribed</td>
                                        <td style='padding: 10px; color: #333;'>Treats {disease}</td>
                                        <td style='padding: 10px; color: #333;'><a href='{med['link']}' style='color: #00ccff;'>Buy for ₹{med['price']}</a></td>
                                    </tr>
                                """
                    if self.language == "english":
                        return f"""
                        <h3 style='color: #ffffff; font-size: 24px;'>Unani Plan for {', '.join(diseases)}</h3>
                        <p style='color: #ffffff;'>Here’s your treatment plan in a table:</p>
                        <table style='width: 100%; border-collapse: collapse; margin: 20px 0;'>
                            <thead>
                                <tr style='background-color: #f2f2f2;'>
                                    <th style='border: 1px solid #000; padding: 10px;'>Item</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>Dosage</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>Benefits</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>Precautions/Links</th>
                                </tr>
                            </thead>
                            <tbody>{table_rows}</tbody>
                        </table>
                        <p style='font-style: italic; color: #ffffff;'>Indeed, the cure is Allah’s (SWT) will.</p>
                        """
                    elif self.language == "hindi":
                        return f"""
                        <h3 style='color: #ffffff; font-size: 24px;'>{', '.join(diseases)} के लिए यूनानी योजना</h3>
                        <p style='color: #ffffff;'>यहाँ आपकी इलाज योजना टेबल में है:</p>
                        <table style='width: 100%; border-collapse: collapse; margin: 20px 0;'>
                            <thead>
                                <tr style='background-color: #f2f2f2;'>
                                    <th style='border: 1px solid #000; padding: 10px;'>वस्तु</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>खुराक</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>लाभ</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>सावधानियाँ/लिंक</th>
                                </tr>
                            </thead>
                            <tbody>{table_rows}</tbody>
                        </table>
                        <p style='font-style: italic; color: #ffffff;'>निश्चित रूप से, इलाज अल्लाह (SWT) की मर्जी से है।</p>
                        """
                    else:  # Hinglish
                        return f"""
                        <h3 style='color: #ffffff; font-size: 24px;'>{', '.join(diseases)} ka Unani Plan</h3>
                        <p style='color: #ffffff;'>Bhai, yeh lo tera treatment plan table mein:</p>
                        <table style='width: 100%; border-collapse: collapse; margin: 20px 0;'>
                            <thead>
                                <tr style='background-color: #f2f2f2;'>
                                    <th style='border: 1px solid #000; padding: 10px;'>Item</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>Dosage</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>Fayda</th>
                                    <th style='border: 1px solid #000; padding: 10px;'>Dhyaan/Link</th>
                                </tr>
                            </thead>
                            <tbody>{table_rows}</tbody>
                        </table>
                        <p style='font-style: italic; color: #ffffff;'>Indeed, the cure is Allah’s (SWT) will.</p>
                        """

                # Single Disease Response (Non-Table)
                disease = diseases[0]
                data = unani_medicines.get(disease, {})
                ingredients = get_unani_ingredients(disease) or data.get("ingredients", [])
                unique_ingredients = {ing["name"]: ing for ing in ingredients}.values()  # Remove duplicates
                if self.language == "english":
                    return f"""
                    <h3 style='color: #ffffff; font-size: 24px;'>Unani Treatment for {disease.capitalize()}</h3>
                    <p style='color: #ffffff;'>Sorry to hear about your {disease}. Here’s how Unani can help:</p>
                    <p style='color: #ffffff;'><strong style='color: #ffcc00;'>Symptoms:</strong> {', '.join(data.get('symptoms', ['Unknown']))}</p>
                    <p style='color: #ffffff;'><strong style='color: #ffcc00;'>Treatment:</strong> {', '.join(data.get('treatment', ['Rest and consult a doctor']))}</p>
                    <h4 style='color: #ffcc00;'>Recommended Ingredients:</h4>
                    {"".join([f"<p style='color: #ffffff;'>{ing['name']} - {ing.get('dosage', ing.get('usage', 'As advised'))} ({ing['benefits']})</p>" for ing in unique_ingredients])}
                    <h4 style='color: #ffcc00;'>Recommended Medicines:</h4>
                    {"".join([f"<p style='color: #ffffff;'><a href='{med['link']}' style='color: #00ccff;'>{med['name']}</a> - ₹{med['price']}</p>" for med in data.get('medicine', [])])}
                    <p style='font-style: italic; color: #ffffff;'>Indeed, the cure is Allah’s (SWT) will.</p>
                    """
                elif self.language == "hindi":
                    return f"""
                    <h3 style='color: #ffffff; font-size: 24px;'>{disease.capitalize()} के लिए यूनानी इलाज</h3>
                    <p style='color: #ffffff;'>{disease} सुनके दुख हुआ। यूनानी से ये मदद मिलेगी:</p>
                    <p style='color: #ffffff;'><strong style='color: #ffcc00;'>लक्षण:</strong> {', '.join(data.get('symptoms', ['अज्ञात']))}</p>
                    <p style='color: #ffffff;'><strong style='color: #ffcc00;'>इलाज:</strong> {', '.join(data.get('treatment', ['आराम करें और डॉक्टर से सलाह लें']))}</p>
                    <h4 style='color: #ffcc00;'>सुझाई गई सामग्री:</h4>
                    {"".join([f"<p style='color: #ffffff;'>{ing['name']} - {ing.get('dosage', ing.get('usage', 'जैसा सलाह दी जाए'))} ({ing['benefits']})</p>" for ing in unique_ingredients])}
                    <h4 style='color: #ffcc00;'>सुझाई गई दवाएँ:</h4>
                    {"".join([f"<p style='color: #ffffff;'><a href='{med['link']}' style='color: #00ccff;'>{med['name']}</a> - ₹{med['price']}</p>" for med in data.get('medicine', [])])}
                    <p style='font-style: italic; color: #ffffff;'>निश्चित रूप से, इलाज अल्लाह (SWT) की मर्जी से है।</p>
                    """
                else:  # Hinglish
                    return f"""
                    <h3 style='color: #ffffff; font-size: 24px;'>{disease.capitalize()} ka Unani Ilaaj</h3>
                    <p style='color: #ffffff;'>Bhai, {disease} sunke thoda dil baith gaya! Unani se yeh help milegi:</p>
                    <p style='color: #ffffff;'><strong style='color: #ffcc00;'>Symptoms:</strong> {', '.join(data.get('symptoms', ['Pata nahi']))}</p>
                    <p style='color: #ffffff;'><strong style='color: #ffcc00;'>Treatment:</strong> {', '.join(data.get('treatment', ['Aaram karo, doctor se milo']))}</p>
                    <h4 style='color: #ffcc00;'>Recommended Ingredients:</h4>
                    {"".join([f"<p style='color: #ffffff;'>{ing['name']} - {ing.get('dosage', ing.get('usage', 'Jaisa bola jaye'))} ({ing['benefits']})</p>" for ing in unique_ingredients])}
                    <h4 style='color: #ffcc00;'>Recommended Medicines:</h4>
                    {"".join([f"<p style='color: #ffffff;'><a href='{med['link']}' style='color: #00ccff;'>{med['name']}</a> - ₹{med['price']}</p>" for med in data.get('medicine', [])])}
                    <p style='font-style: italic; color: #ffffff;'>Indeed, the cure is Allah’s (SWT) will.</p>
                    """

        # Fallback for Table Request without Context
        if wants_table:
            last_disease = self._get_last_medical_context()
            if last_disease:
                return self.generate_chat_response(f"table for {last_disease}")
            return "<p style='color: #ffffff;'>Bhai, kis cheez ka table chahiye? Pehle disease bata!</p>" if self.language == "hinglish" else "<p style='color: #ffffff;'>Which condition’s table do you want? Tell me first!</p>"

        # Generic Fallback
        last_medical = self._get_last_medical_context()
        if last_medical:
            return f"<p style='color: #ffffff;'>Bhai, {last_medical.capitalize()} ke baare mein baat kar raha hai ya kuch aur?</p>" if self.language == "hinglish" else f"<p style='color: #ffffff;'>Are you talking about {last_medical.capitalize()} or something else?</p>"
        return "<p style='color: #ffffff;'>Bhai, thodi aur detail de na, taki sahi help kar sakoon!</p>" if self.language == "hinglish" else "<p style='color: #ffffff;'>Please give me more details so I can help you better!</p>"

    def _get_last_medical_context(self, return_list=False):
        diseases = []
        for past_msg in reversed(self.conversation_history[:-1]):
            for word in past_msg.lower().split():
                if word in unani_medicines:
                    diseases.append(word)
            if diseases and not return_list:
                return diseases[0]
        return diseases if return_list else None

# Global UnaniAI instance
unani_ai = UnaniAI()

# Views
def index(request):
    return render(request, 'index.html')

def logout(request):
    request.session.flush()
    return redirect('index')

def chat_view(request):
    if 'user_id' not in request.session:
        return redirect('login')
    user_id = request.session['user_id']
    history = get_conversation_history(user_id)
    return render(request, 'chat.html', {'history': history})

def signup(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                messages.error(request, 'Email already exists!')
                return redirect('signup')
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
            messages.success(request, 'Signup successful! Please login.')
            return redirect('login')
        except sqlite3.Error as e:
            messages.error(request, f'Database error: {str(e)}')
        finally:
            conn.close()
    return render(request, 'signup.html')

def login(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()
            if user:
                request.session['user_id'] = user[0]
                messages.success(request, 'Logged in successfully!')
                return redirect('index')
            messages.error(request, 'Invalid credentials!')
        except sqlite3.Error as e:
            messages.error(request, f'Database error: {str(e)}')
        finally:
            conn.close()
    return render(request, 'login.html')

def get_conversation_history(user_id):
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message, response, timestamp FROM conversations WHERE user_id = ? ORDER BY timestamp ASC', (user_id,))
    history = [{"message": row[0], "response": row[1], "timestamp": row[2]} for row in cursor.fetchall()]
    conn.close()
    return history

@csrf_exempt
def chatbot_response(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({"error": "Please login first!"}, status=401)
            if not user_message:
                return JsonResponse({"error": "No message provided!"}, status=400)

            response = unani_ai.generate_chat_response(user_message)
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO conversations (user_id, message, response) VALUES (?, ?, ?)', (user_id, user_message, response))
            conn.commit()
            conn.close()
            return JsonResponse({"response": response})
        except Exception as e:
            print(f"Error in chatbot_response: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request!"}, status=400)

@csrf_exempt
def emergency_assistance(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_lat = data.get("latitude")
            user_lon = data.get("longitude")
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={user_lat},{user_lon}&radius=5000&type=hospital&keyword=Unani&key={GOOGLE_PLACES_API_KEY}"
            response = requests.get(url)
            places_data = response.json()
            facilities = [{"name": place.get("name"), "address": place.get("vicinity"), "rating": place.get("rating", "N/A")} for place in places_data.get("results", [])]
            return JsonResponse({"facilities": facilities})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request!"}, status=400)

@csrf_exempt
def add_medicine_reminder(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({"status": "error", "message": "Please login!"}, status=401)
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO medicine_reminders (user_id, medicine_name, dosage, schedule, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, data["medicine_name"], data["dosage"], data["schedule"], data["start_date"], data["end_date"]))
            conn.commit()
            conn.close()
            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Invalid request!"}, status=400)

@csrf_exempt
def medicine_reminders(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({"status": "error", "message": "Please login!"}, status=401)
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    cursor.execute('SELECT medicine_name, dosage, schedule, start_date, end_date FROM medicine_reminders WHERE user_id = ?', (user_id,))
    reminders = [{"medicine_name": r[0], "dosage": r[1], "schedule": r[2], "start_date": r[3], "end_date": r[4]} for r in cursor.fetchall()]
    conn.close()
    return JsonResponse({"reminders": reminders})

@csrf_exempt
def send_medicine_reminders(request):
    if request.method == "POST":
        try:
            now = datetime.now().strftime("%I:%M %p")
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({"status": "error", "message": "Please login!"}, status=401)

            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
            email = cursor.fetchone()[0]
            cursor.execute('SELECT medicine_name, dosage, schedule FROM medicine_reminders WHERE user_id = ?', (user_id,))
            reminders = cursor.fetchall()
            conn.close()

            for reminder in reminders:
                medicine_name, dosage, schedule = reminder
                if now in schedule.split(", "):
                    subject = f"Reminder: Take {medicine_name}"
                    message = f"Time to take your medicine!\n\nMedicine: {medicine_name}\nDosage: {dosage}"
                    send_mail(subject, message, 'jahirshaikh162003@gmail.com', [email], fail_silently=False)
                    return JsonResponse({"status": "success", "message": f"Reminder sent to {email} for {medicine_name}!"})
            return JsonResponse({"status": "success", "message": "No reminders due now."})
        except Exception as e:
            print(f"Error in send_medicine_reminders: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Invalid request!"}, status=400)