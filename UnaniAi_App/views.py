import re
import sqlite3
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json
import google.generativeai as genai
from datetime import datetime
import requests
import time

# Gemini API Setup
genai.configure(api_key="AIzaSyCnLkFs3-8aufez4jPpQFnahj4ropCNBfg")
model = genai.GenerativeModel("gemini-1.5-flash")

# Google Places API Key
GOOGLE_PLACES_API_KEY = "YOUR_GOOGLE_PLACES_API_KEY"

# SQLite Database Setup
def create_database():
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,  -- Changed to allow NULL
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

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

# Temporary Unani Medicine Database (unchanged)
unani_medicines = {
    "cough": {
        "symptoms": ["Dry throat", "Chest congestion", "Difficulty breathing"],
        "treatment": ["Take honey with ginger", "Drink liquorice root tea"],
        "medicine": [{"name": "Marzanjosh", "link": "https://aetmaad.co.in/product/al-marzanjosh", "price": 300}]
    },
    # Baaki data same rakha, short kar diya brevity ke liye
}

# Temporary Unani Ingredients Database (unchanged)
unani_ingredients = []

def populate_unani_ingredients():
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    for ingredient in unani_ingredients:
        cursor.execute('''
            INSERT INTO unani_ingredients (ingredient_name, benefits, usage, diseases)
            VALUES (?, ?, ?, ?)
        ''', (ingredient["ingredient_name"], ingredient["benefits"], ingredient["usage"], ingredient["diseases"]))
    conn.commit()
    conn.close()
    print("Unani ingredients database populated successfully!")
populate_unani_ingredients()

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
    return ingredients

def generate_chat_response(user_message):
    """
    Generates a crisp, table-formatted response for Unani medicine queries with inline CSS.
    Number of remedies varies based on disease severity.
    """
    user_message = user_message.lower().strip()

    # 1. Handle Pure Greetings
    greetings = ["hello", "hi", "sala", "assalam"]
    if user_message in greetings:
        return "<p style='color: white; font-style: italic;'>As-salamu alaykum! How can I assist you today?</p>"

    # 2. Check Known Diseases in unani_medicines
    words = user_message.split()
    for word in words:
        if word in unani_medicines:
            data = unani_medicines[word]
            response = f"<h3 style='color: white;'>Unani for {word.capitalize()}</h3>"
            response += f"<p style='color: white;'><strong style='color: #ffcc00;'>Symptoms:</strong> {', '.join(data['symptoms'])}</p>"
            response += f"<p style='color: white;'><strong style='color: #ffcc00;'>Treatment:</strong> {', '.join(data['treatment'])}</p>"
            if data.get("medicine"):
                response += "<h4 style='color: #ffcc00;'>Medicines:</h4>"
                response += "".join(f"<p><a href='{med['link']}'>{med['name']}</a> - ₹{med['price']}</p>" for med in data["medicine"])
            return response

    # 3. Check Unani Ingredients Table (if populated)
    ingredients = get_unani_ingredients(user_message)
    if ingredients:
        table_rows = "".join(
            f"<tr style='border: 1px solid #ddd; background-color: white;'>"
            f"<td style='padding: 8px;'>{ing[0]}</td>"
            f"<td style='padding: 8px;'>{ing[1]}</td>"
            f"<td style='padding: 8px;'>{ing[2]}</td>"
            f"</tr>" for ing in ingredients
        )
        return (f"<h3 style='color: #ffffff;'>Ingredients for {user_message.capitalize()}</h3>"
                f"<table style='width: 100%; border-collapse: collapse; margin: 10px 0;'>"
                f"<thead><tr style='background-color: white;'>"
                f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Ingredient</span></th>"
                f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Benefits</span></th>"
                f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Usage</span></th>"
                f"</tr></thead><tbody style='color: black;'>{table_rows}</tbody></table>"
                f"<p style='color: white; font-style: italic;'>Indeed, the cure is Allah's will.</p>")

    # 4. Fallback to Gemini API with Dynamic Remedy Count
    # Define disease severity levels (example)
    severity_levels = {
        "cold": "mild", "cough": "mild", "fever": "moderate", "flu": "moderate",
        "pneumonia": "severe", "tuberculosis": "severe", "cancer": "severe"
    }
    
    # Determine severity and remedy count
    remedy_count = 3  # Default for mild or unknown
    for word in words:
        if word in severity_levels:
            if severity_levels[word] == "mild":
                remedy_count = 3
            elif severity_levels[word] == "moderate":
                remedy_count = 4
            elif severity_levels[word] == "severe":
                remedy_count = 5
            break

    prompt = f"""
    You are an expert in prophetic Unani medicine. Answer in short, crisp sentences based only on Islamic Unani principles.
    User query: "{user_message}". If it’s a disease or health issue:
    - Suggest exactly {remedy_count} prophetic Unani remedies in this table format:
    | Ingredient | Dosage         | Benefits             | Precautions         |
    |------------|----------------|----------------------|---------------------|
    | [Name]     | [Dosage]       | [Short benefit]      | [Short precaution]  |
    - End with "Indeed, the cure is Allah's will."
    If it’s a random query (e.g., "how are you", "tell me a joke"), reply: "I’m here to help with Unani medicine. Ask me anything!"
    """
    gemini_response = model.generate_content(prompt).text.strip()
    lines = gemini_response.split('\n')
    table_rows = ""
    for line in lines:
        if line.startswith('|') and not line.startswith('| Ingredient') and not line.startswith('|---'):
            parts = [part.strip() for part in line.split('|')[1:-1]]
            if len(parts) == 4:
                table_rows += (f"<tr style='border: 1px solid #ddd; background-color: white;'>"
                               f"<td style='padding: 8px;'>{parts[0]}</td>"
                               f"<td style='padding: 8px;'>{parts[1]}</td>"
                               f"<td style='padding: 8px;'>{parts[2]}</td>"
                               f"<td style='padding: 8px;'>{parts[3]}</td></tr>")

    # 5. Handle Random Queries or Gemini Fallback
    if "I’m here to help" in gemini_response:
        return "<p style='color: white;'>I’m here to help with Unani medicine. Ask me anything!</p>"
    
    return (f"<h3 style='color: #ffffff;'>{user_message.capitalize()}</h3>"
            f"<table style='width: 100%; border-collapse: collapse; margin: 10px 0;'>"
            f"<thead><tr style='background-color: white;'>"
            f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Ingredient</span></th>"
            f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Dosage</span></th>"
            f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Benefits</span></th>"
            f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Precautions</span></th>"
            f"</tr></thead><tbody style='color: black;'>{table_rows}</tbody></table>"
            f"<p style='color: white; font-style: italic;'>Indeed, the cure is Allah's will.</p>")

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
                messages.error(request, 'User with this email already exists.')
                return redirect('signup')
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
            messages.success(request, 'Account created successfully! Please login.')
        except sqlite3.Error as e:
            messages.error(request, f'Database error: {str(e)}')
        finally:
            conn.close()
        return redirect('login')
    return render(request, 'signup.html')

def login(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()
            if user:
                request.session['user_id'] = user[0]
                messages.success(request, 'Welcome! You have successfully logged in.')
                return redirect('index')
            else:
                messages.error(request, 'Invalid email or password.')
        except sqlite3.Error as e:
            messages.error(request, f'Database error: {str(e)}')
        finally:
            conn.close()
    return render(request, 'login.html')

def remove_markdown_formatting(text):
    text = re.sub(r'(\*\*|\*|__|_)(.*?)\1', r'\2', text)
    text = re.sub(r'^\s*[\*\-]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\s*\n', '\n', text).strip()
    return text

def get_conversation_history(user_id):
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT message, response, timestamp
        FROM conversations
        WHERE user_id = ?
        ORDER BY timestamp ASC
    ''', (user_id,))
    history = cursor.fetchall()
    conn.close()
    return history

@csrf_exempt
def chatbot_response(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            user_id = request.session.get('user_id')  # Null ho sakta hai

            if not user_message:
                return JsonResponse({"error": "No message provided"}, status=400)

            response = generate_chat_response(user_message)

            # Database operation with retry logic
            for attempt in range(3):  # 3 retries
                try:
                    conn = sqlite3.connect('signup.db')
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO conversations (user_id, message, response)
                        VALUES (?, ?, ?)
                    ''', (user_id if user_id else None, user_message, response))
                    conn.commit()
                    conn.close()
                    break  # Success, exit loop
                except sqlite3.OperationalError as e:
                    conn.close()
                    if "database is locked" in str(e) and attempt < 2:
                        time.sleep(1)  # Wait 1 second before retry
                        continue
                    print(f"Error in chatbot_response: {e}")
                    return JsonResponse({"error": str(e)}, status=500)

            return JsonResponse({"response": response})
        except Exception as e:
            print(f"Error in chatbot_response: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request"}, status=400)

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
            facilities = [
                {"name": place.get("name"), "address": place.get("vicinity"), "rating": place.get("rating", "N/A")}
                for place in places_data.get("results", [])
            ]
            return JsonResponse({"facilities": facilities})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)

@csrf_exempt
def add_medicine_reminder(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            medicine_name = data.get("medicine_name")
            dosage = data.get("dosage")
            schedule = data.get("schedule")
            start_date = data.get("start_date")
            end_date = data.get("end_date")
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({"status": "error", "message": "User not logged in"}, status=401)

            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO medicine_reminders (user_id, medicine_name, dosage, schedule, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, medicine_name, dosage, schedule, start_date, end_date))
            conn.commit()
            conn.close()
            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

@csrf_exempt
def medicine_reminders(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({"status": "error", "message": "User not logged in"}, status=401)
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT medicine_name, dosage, schedule, start_date, end_date
        FROM medicine_reminders
        WHERE user_id = ?
    ''', (user_id,))
    reminders = cursor.fetchall()
    conn.close()
    formatted_reminders = [
        {"medicine_name": r[0], "dosage": r[1], "schedule": r[2], "start_date": r[3], "end_date": r[4]}
        for r in reminders
    ]
    return JsonResponse({"reminders": formatted_reminders})

@csrf_exempt
def send_medicine_reminders(request):
    if request.method == "POST":
        try:
            now = datetime.now().strftime("%I:%M %p")
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({"status": "error", "message": "User not logged in"}, status=401)

            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
            email = cursor.fetchone()[0]
            cursor.execute('''
                SELECT medicine_name, dosage, schedule
                FROM medicine_reminders
                WHERE user_id = ?
            ''', (user_id,))
            reminders = cursor.fetchall()
            conn.close()

            for reminder in reminders:
                medicine_name, dosage, schedule = reminder
                if now in schedule:
                    subject = f"Reminder: Take {medicine_name}"
                    message = f"Hello,\n\nIt's time to take your medicine:\n\nMedicine: {medicine_name}\nDosage: {dosage}\n\nThank you!"
                    send_mail(subject, message, 'jahirshaikh162003@gmail.com', [email], fail_silently=False)
                    return JsonResponse({
                        "status": "success",
                        "message": f"Reminder sent to {email} at {now}.",
                        "alert": "Email reminder sent successfully!"
                    })
            return JsonResponse({"status": "success", "message": "No reminders to send at this time."})
        except Exception as e:
            print(f"Error in send_medicine_reminders: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)