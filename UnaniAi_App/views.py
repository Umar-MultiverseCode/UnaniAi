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
import random

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
    
    # Return only unique ingredients to prevent duplication
    seen = set()
    unique_ingredients = []
    for ingredient in ingredients:
        # Create a unique key based on ingredient name
        key = ingredient[0].lower().strip()
        if key not in seen:
            seen.add(key)
            unique_ingredients.append(ingredient)
    
    return unique_ingredients

def generate_chat_response(user_message):
    """
    Generates a crisp, table-formatted response for Unani medicine queries with inline CSS.
    Number of remedies varies based on disease severity.
    """
    user_message = user_message.lower().strip()

    # Extract actual condition/topic from the message
    condition = extract_condition(user_message)
    
    # Generate a unique header for this condition
    response_header = generate_dynamic_header(condition)
    
    # 1. Handle Pure Greetings
    greetings = ["hello", "hi", "sala", "assalam"]
    if user_message in greetings:
        return "<p style='color: white; font-style: italic;'>As-salamu alaykum! How can I assist you today?</p>"

    # 2. Check Known Diseases in unani_medicines
    words = user_message.split()
    for word in words:
        if word in unani_medicines:
            data = unani_medicines[word]
            response = f"<h3 style='color: white;'>{response_header}</h3>"
            response += f"<p style='color: white;'><strong style='color: #ffcc00;'>Symptoms:</strong> {', '.join(data['symptoms'])}</p>"
            response += f"<p style='color: white;'><strong style='color: #ffcc00;'>Treatment:</strong> {', '.join(data['treatment'])}</p>"
            if data.get("medicine"):
                response += "<h4 style='color: #ffcc00;'>Medicines:</h4>"
                response += "".join(f"<p><a href='{med['link']}'>{med['name']}</a> - ₹{med['price']}</p>" for med in data["medicine"])
            return response

    # 3. Check Unani Ingredients Table (if populated)
    ingredients = get_unani_ingredients(condition)
    if ingredients:
        # Add a brief description about the condition before the table
        description = get_condition_description(condition)
        
        table_rows = "".join(
            f"<tr style='border: 1px solid #ddd; background-color: white;'>"
            f"<td style='padding: 8px;'>{ing[0]}</td>"
            f"<td style='padding: 8px;'>{ing[1]}</td>"
            f"<td style='padding: 8px;'>{ing[2]}</td>"
            f"</tr>" for ing in ingredients
        )
        return (f"<h3 style='color: #ffffff;'>{response_header}</h3>"
                f"<p style='color: white;'>{description}</p>"
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
    You are an expert in prophetic Unani medicine. Provide a response about '{condition}' in this exact format:

    First, write a brief 2-3 sentence explanation about the condition from a Unani medicine perspective. Don't use any markdown formatting, asterisks, or special characters. Write in plain text.

    Then, provide exactly {remedy_count} DIFFERENT Unani remedies (do not repeat the same ingredient) in this table format:
    | Ingredient | Dosage | Benefits | Precautions |
    |------------|--------|----------|-------------|
    | [ingredient name] | [dosage] | [benefits] | [precautions] |

    Make sure each remedy uses a UNIQUE ingredient - do not repeat any ingredients.
    End with "Indeed, the cure is Allah's will."

    If it's not a health query, reply: "I'm here to help with Unani medicine. Ask me about health conditions or treatments."
    Do not include numbered lists, bullet points, or any special formatting. Keep it clean and simple.
    """
    
    gemini_response = model.generate_content(prompt).text.strip()
    
    # Clean up response
    gemini_response = clean_response_text(gemini_response)
    
    # Extract the description and table parts
    description = ""
    table_content = ""
    table_start_index = -1
    
    # Look for the table marker
    table_markers = ["| Ingredient |", "Ingredient\tDosage"]
    lines = gemini_response.split('\n')
    
    for i, line in enumerate(lines):
        for marker in table_markers:
            if marker in line:
                table_start_index = i
                break
        if table_start_index >= 0:
            break
    
    # If we found a table, separate description and table
    if table_start_index > 0:
        description = '\n'.join(lines[:table_start_index]).strip()
        table_content = '\n'.join(lines[table_start_index:]).strip()
    else:
        description = gemini_response
    
    # Remove any remaining numbered list formatting or table headers from description
    description = re.sub(r'^\d+\.\s+', '', description, flags=re.MULTILINE)  # Remove "1. " style numbering
    description = re.sub(r'\|.*?\|.*?\|.*?\|.*?\|', '', description)  # Remove any table header in description
    
    # Parse table rows
    table_rows = ""
    in_table = False
    header_found = False
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
            
        # Check if we're entering the table section
        if any(marker in line for marker in table_markers):
            in_table = True
            header_found = True
            continue
        
        # Skip the divider line
        if in_table and "|--" in line:
            continue
            
        # Process table rows
        if in_table and "|" in line and header_found:
            # Process proper table format
            parts = [part.strip() for part in line.split('|')[1:-1]]
            if len(parts) == 4:
                table_rows += (f"<tr style='border: 1px solid #ddd; background-color: white;'>"
                              f"<td style='padding: 8px;'>{parts[0]}</td>"
                              f"<td style='padding: 8px;'>{parts[1]}</td>"
                              f"<td style='padding: 8px;'>{parts[2]}</td>"
                              f"<td style='padding: 8px;'>{parts[3]}</td></tr>")
        
        # Handle tab-separated format as fallback
        elif in_table and "\t" in line and header_found:
            parts = [part.strip() for part in line.split('\t')]
            if len(parts) >= 4:
                table_rows += (f"<tr style='border: 1px solid #ddd; background-color: white;'>"
                              f"<td style='padding: 8px;'>{parts[0]}</td>"
                              f"<td style='padding: 8px;'>{parts[1]}</td>"
                              f"<td style='padding: 8px;'>{parts[2]}</td>"
                              f"<td style='padding: 8px;'>{parts[3]}</td></tr>")

    # 5. Handle Random Queries or Gemini Fallback
    if "I'm here to help" in gemini_response:
        return "<p style='color: white;'>I'm here to help with Unani medicine. Ask me about health conditions or treatments.</p>"
    
    # Final cleanup of description
    description = description.replace("1.", "").replace("2.", "").strip()
    description = re.sub(r'\s+', ' ', description)  # Replace multiple spaces with a single space
    
    return (f"<h3 style='color: #ffffff;'>{response_header}</h3>"
            f"<p style='color: white;'>{description}</p>"
            f"<table style='width: 100%; border-collapse: collapse; margin: 10px 0;'>"
            f"<thead><tr style='background-color: white;'>"
            f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Ingredient</span></th>"
            f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Dosage</span></th>"
            f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Benefits</span></th>"
            f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Precautions</span></th>"
            f"</tr></thead><tbody style='color: black;'>{table_rows}</tbody></table>"
            f"<p style='color: white; font-style: italic;'>Indeed, the cure is Allah's will.</p>")

def generate_dynamic_header(condition):
    """Generate varied and unique headers for each condition"""
    # Use current timestamp to create variation even for the same condition
    seed = int(time.time()) % 100
    random.seed(seed)
    
    # Create a list of template headers
    templates = [
        f"Unani Remedies for {condition.capitalize()}",
        f"Natural Treatment: {condition.capitalize()}",
        f"Tibb-e-Nabawi: Healing {condition.capitalize()}",
        f"Traditional Cures for {condition.capitalize()}",
        f"Healing {condition.capitalize()} with Unani Medicine",
        f"Ancient Wisdom for {condition.capitalize()}",
        f"Prophetic Medicine for {condition.capitalize()}",
        f"{condition.capitalize()}: Unani Solutions",
        f"Treating {condition.capitalize()} Naturally",
        f"Holistic Approach to {condition.capitalize()}",
        f"{condition.capitalize()}: Balancing the Humors",
        f"Unani Perspective on {condition.capitalize()}",
        f"Addressing {condition.capitalize()} with Tibb",
        f"{condition.capitalize()}: Nature's Pharmacy",
        f"Time-Tested Remedies for {condition.capitalize()}"
    ]
    
    # Choose a random template
    return random.choice(templates)

def extract_condition(user_message):
    """Extract the actual health condition from the user message"""
    # Common prefixes to remove
    prefixes = [
        "i have", "i am suffering from", "i am experiencing", "i feel", 
        "what about", "how to treat", "how to cure", "how to handle",
        "treatment for", "cure for", "remedy for", "what is", "tell me about"
    ]
    
    # Convert to lowercase and strip
    message = user_message.lower().strip()
    
    # Remove common prefixes
    for prefix in prefixes:
        if message.startswith(prefix):
            message = message[len(prefix):].strip()
            break
    
    # Check for common suffixes to remove
    suffixes = [" problem", " issues", " symptoms", " condition", " disease", " disorder"]
    for suffix in suffixes:
        if message.endswith(suffix):
            message = message[:-len(suffix)].strip()
    
    # Handle specific conditions or variations
    condition_map = {
        "gas": "gas",
        "acidity": "acidity",
        "gastric": "gastric problem",
        "pain in stomach": "stomach pain",
        "pain in head": "headache",
        "throat pain": "sore throat"
    }
    
    # Check if our cleaned message maps to a known condition
    for key, value in condition_map.items():
        if key in message:
            return value
    
    return message  # Return the cleaned message

def clean_response_text(text):
    """Clean up the response text to remove markdown and formatting."""
    # Remove markdown formatting and special characters
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove italic
    text = re.sub(r'_(.*?)_', r'\1', text)        # Remove underline
    text = re.sub(r'`(.*?)`', r'\1', text)        # Remove code
    
    # Remove list markers
    text = re.sub(r'^\s*[\*\-\+]\s+', '', text, flags=re.MULTILINE)
    
    # Clean up extra spaces and newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

def remove_markdown_formatting(text):
    """Remove markdown formatting from text."""
    text = re.sub(r'(\*\*|\*|__|_|`)(.*?)\1', r'\2', text)
    text = re.sub(r'^\s*[\*\-\+]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\s*\n', '\n', text).strip()
    return text

def get_condition_description(condition):
    """Get a brief description for common health conditions"""
    descriptions = {
        "fever": "According to Unani medicine, fever (Humma) is an increase in innate heat that spreads throughout the body through the heart, arteries and blood. It is often associated with an imbalance in the phlegmatic or bilious humors and can be treated with cooling herbs and dietary adjustments.",
        "cough": "In Unani medicine, cough (Sual) is considered a symptom of disruption in the respiratory system, often due to accumulation of phlegm or irritation in the airways. Traditional treatments focus on balancing the body's moisture and removing excess phlegm.",
        "headache": "Headaches (Suda) in Unani medicine are attributed to imbalances in blood, phlegm, or bile affecting the head region. Treatment typically involves restoring humoral balance through herbs, dietary changes, and sometimes cupping therapy.",
        "cold": "The common cold (Nazla) in Unani medicine is viewed as an accumulation of cold humors in the respiratory system. Treatment aims to restore warmth and eliminate excess phlegm through warming herbs and proper dietary regimen.",
        "piles": "Piles (Bawaseer) in Unani medicine are attributed to an excess of black bile or blood in the rectal veins. Traditional treatments focus on cooling the blood, improving bowel movements, and reducing inflammation through herbs and dietary modifications.",
        "constipation": "Constipation (Qabz) in Unani medicine is considered a result of dryness in the intestines or weakness in the expulsive faculty. Treatment includes moistening herbs, dietary adjustments, and sometimes gentle laxatives to restore normal bowel function."
    }
    
    # Check for exact matches first
    if condition in descriptions:
        return descriptions[condition]
    
    # Check for partial matches
    for key, desc in descriptions.items():
        if key in condition or condition in key:
            return desc
    
    # Default description for unknown conditions
    return f"In Unani medicine, health conditions like {condition} are typically approached by understanding the imbalance in bodily humors (Akhlaat) and temperament (Mizaj). Treatment focuses on restoring balance through natural remedies, dietary adjustments, and lifestyle modifications."

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