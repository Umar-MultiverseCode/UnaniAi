import re
import sqlite3
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
import json
import google.generativeai as genai
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from datetime import datetime
import json
import requests  # Google Places API ke liye

# Gemini API Setup
genai.configure(api_key="AIzaSyCnLkFs3-8aufez4jPpQFnahj4ropCNBfg")
model = genai.GenerativeModel("gemini-1.5-flash")

# Google Places API Key
GOOGLE_PLACES_API_KEY = "YOUR_GOOGLE_PLACES_API_KEY"  # Apna API key daalein

# SQLite Database Setup
def create_database():
    """
    SQLite database aur tables create karta hai (if not exists).
    """
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
    print("Database and tables created successfully!")  # Debugging ke liye
create_database()

# Temporary Unani Medicine Database
unani_medicines = {
    "cough": {
        "symptoms": ["Dry throat", "Chest congestion", "Difficulty breathing"],
        "treatment": ["Take honey with ginger", "Drink liquorice root tea"],
        "medicine": [
            {"name": "Marzanjosh", "link": "https://aetmaad.co.in/product/al-marzanjosh", "price": 300}
        ]
    },
    "malaria": {
        "symptoms": ["High fever", "Chills", "Headache", "Fatigue"],
        "treatment": ["Stay hydrated", "Rest", "Use mosquito nets"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "constipation": {
        "symptoms": ["Difficulty passing stool", "Bloating", "Abdominal pain"],
        "treatment": ["Increase fiber intake", "Drink plenty of water"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "peristalsis": {
        "symptoms": ["Irregular bowel movements", "Abdominal discomfort"],
        "treatment": ["Eat fiber-rich foods", "Exercise regularly"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "piles": {
        "symptoms": ["Pain during bowel movements", "Itching around the anus"],
        "treatment": ["Use warm sitz baths", "Apply aloe vera gel"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "dysentery": {
        "symptoms": ["Diarrhea", "Abdominal cramps", "Fever"],
        "treatment": ["Stay hydrated", "Avoid spicy food"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "hepatomegaly": {
        "symptoms": ["Abdominal swelling", "Fatigue", "Jaundice"],
        "treatment": ["Avoid alcohol", "Eat a balanced diet"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "spleenomegaly": {
        "symptoms": ["Abdominal pain", "Feeling full quickly"],
        "treatment": ["Avoid heavy meals", "Rest"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "jaundice": {
        "symptoms": ["Yellowing of skin", "Dark urine", "Fatigue"],
        "treatment": ["Drink plenty of fluids", "Avoid fatty foods"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "gouts": {
        "symptoms": ["Joint pain", "Swelling", "Redness"],
        "treatment": ["Avoid purine-rich foods", "Stay hydrated"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "rheumatism": {
        "symptoms": ["Joint pain", "Stiffness", "Swelling"],
        "treatment": ["Apply warm compresses", "Exercise regularly"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "anaemia": {
        "symptoms": ["Fatigue", "Pale skin", "Shortness of breath"],
        "treatment": ["Eat iron-rich foods", "Take vitamin C supplements"],
        "medicine": [
            {"name": "Sanna Makki", "link": "https://aetmaad.co.in/product/sanna-makki", "price": 70}
        ]
    },
    "blood pressure": {
        "symptoms": ["Headache", "Dizziness", "Blurred vision"],
        "treatment": ["Reduce salt intake", "Exercise regularly"],
        "medicine": [
            {"name": "Qalbi Nuska", "link": "https://aetmaad.co.in/product/qalbi-nuska", "price": 600}
        ]
    },
    "joint pain": {
        "symptoms": ["Pain in joints", "Swelling", "Stiffness"],
        "treatment": ["Apply warm oil", "Massage gently"],
        "medicine": [
            {"name": "Rumabil", "link": "https://aetmaad.co.in/product/rumabil", "price": 300}
        ]
    },
    "ulcers": {
        "symptoms": ["Burning stomach pain", "Nausea", "Bloating"],
        "treatment": ["Avoid spicy food", "Eat small meals"],
        "medicine": [
            {"name": "Al-Rehan", "link": "https://aetmaad.co.in/product/al-rehan", "price": 300}
        ]
    },
    "sore throats": {
        "symptoms": ["Pain while swallowing", "Dry throat", "Swollen glands"],
        "treatment": ["Gargle with salt water", "Drink warm fluids"],
        "medicine": [
            {"name": "Multi Flora Honey", "link": "https://aetmaad.co.in/product/multi-flora-honey", "price": 600}
        ]
    },
    "skin irritations": {
        "symptoms": ["Redness", "Itching", "Rashes"],
        "treatment": ["Apply aloe vera gel", "Avoid harsh soaps"],
        "medicine": [
            {"name": "Multi Flora Honey", "link": "https://aetmaad.co.in/product/multi-flora-honey", "price": 600}
        ]
    },
    "hair loss": {
        "symptoms": ["Thinning hair", "Bald patches", "Excessive shedding"],
        "treatment": ["Massage scalp with oil", "Eat protein-rich foods"],
        "medicine": [
            {"name": "Tulsi Honey", "link": "https://aetmaad.co.in/product/tulsi-honey", "price": 600}
        ]
    },
    "infections": {
        "symptoms": ["Fever", "Fatigue", "Swelling"],
        "treatment": ["Maintain hygiene", "Take prescribed antibiotics"],
        "medicine": [
            {"name": "Tulsi Honey", "link": "https://aetmaad.co.in/product/tulsi-honey", "price": 600}
        ]
    },
    "fever": {
        "symptoms": ["High temperature", "Sweating", "Chills", "Body ache"],
        "treatment": ["Drink herbal mint tea", "Apply sandalwood paste", "Stay hydrated"],
        "medicine": [
            {"name": "Tulsi Honey", "link": "https://aetmaad.co.in/product/tulsi-honey", "price": 600}
        ]
    }
}

# Temporary Unani Ingredients Database
unani_ingredients = []

# Populate Unani Ingredients Database
def populate_unani_ingredients():
    """
    Populates the unani_ingredients table with sample data.
    """
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

# Fetch Unani Ingredients for a Disease
def get_unani_ingredients(disease):
    """
    Fetches Unani ingredients for a specific disease.
    """
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
    Generates a clean, table-formatted response for Unani medicine queries with inline CSS.
    """
    words = user_message.lower().split()
    for word in words:
        if word in unani_medicines:
            data = unani_medicines[word]
            response = f"<h3 style='color: white; font-family: Arial, sans-serif; font-size: 24px; margin-bottom: 10px;'>Unani Treatment for {word.capitalize()}</h3>"
            response += f"<p style='color: white; font-family: Arial, sans-serif; font-size: 16px; margin-bottom: 8px;'><strong style='color: #ffcc00;'>Symptoms:</strong> {', '.join(data['symptoms'])}</p>"
            response += f"<p style='color: white; font-family: Arial, sans-serif; font-size: 16px; margin-bottom: 8px;'><strong style='color: #ffcc00;'>Treatment:</strong> {', '.join(data['treatment'])}</p>"           
            if "medicine" in data and data["medicine"]:
                response += "<h4 style='color: #ffcc00; font-family: Arial, sans-serif; font-size: 16px; margin-bottom: 8px;'>Recommended Medicines:</h4>"
                for med in data["medicine"]:
                    response += f"<p><a href='{med['link']}'>{med['name']}</a> - ₹{med['price']}</p>"
            return response

    # Check Unani ingredients table
    ingredients = get_unani_ingredients(user_message.lower())
    if ingredients:
        table_rows = ""
        for ingredient in ingredients:
            table_rows += f"""
               <tr style='border: 1px solid #ddd; background-color: white;'>
                        <td style='padding: 8px;'>{parts[0]}</td>
                        <td style='padding: 8px;'>{parts[1]}</td>
                        <td style='padding: 8px;'>{parts[2]}</td>
                        <td style='padding: 8px;'>{parts[3]}</td>
                    </tr>
            """
        response = f"""
        <h3 style='color: #ffffff;'>Unani Ingredients for {user_message.capitalize()}</h3>
        <table style='width: 100%; border-collapse: collapse; margin: 20px 0;'>
        <thead>
            <tr style='background-color: white;'>
                <th style='border: 1px solid #000000; padding: 8px;'><span style='color: black;'>Ingredient</span></th>
                <th style='border: 1px solid #000000; padding: 8px;'><span style='color: black;'>Dosage</span></th>
                <th style='border: 1px solid #000000; padding: 8px;'><span style='color: black;'>Benefits</span></th>
                <th style='border: 1px solid #000000; padding: 8px;'><span style='color: black;'>Precautions</span></th>
            </tr>
        </thead>
        <tbody style='color: black;'>
        {table_rows}
        </tbody>
        </table>
        <p style='font-style: italic;'>Indeed, the cure is Allah's will.</p>
        """
        return response

    # Fallback to Gemini API
    prompt = f"""
    You are an expert in Unani medicine. Answer based on only prophetic Unani principles. 
    When the user starts the conversation with greetings, respond with: 
    "As-salamu alaykum wa rahmatullahi wa barakatuh. Peace be upon you, and the mercy and blessings of Allah be upon you. How can I assist you today?"
    
    The user is asking about: {user_message}. Since this disease is not in our database, 
    suggest only prophetic Unani ingredients or remedies to manage or treat this condition.and explain these ingredeints according to islamic view in one paragraph. 
    Provide the response in this exact table format:

    | Ingredient            | Dosage                   | Benefits                                                                    | Precautions                              |
    |-----------------------|--------------------------|-----------------------------------------------------------------------------|------------------------------------------|
    | [Name of ingredient]  | [Recommended dosage]     | [Benefits of the ingredient]                                                | [Precautions or side effects]            |

    At the end, write "Indeed, the cure is Allah's will."
    """

    gemini_response = model.generate_content(prompt).text
    cleaned_response = remove_markdown_formatting(gemini_response)

    # Parse Gemini response into a table
    lines = cleaned_response.split('\n')
    table_rows = ""
    in_table = False
    for line in lines:
        if line.startswith('| Ingredient'):
            in_table = True  # Table header detected
            continue
        if in_table and line.startswith('|'):
            if line.strip() == '|---':  # Skip separator line
                continue
            parts = [part.strip() for part in line.split('|')[1:-1]]  # Extract columns
            if len(parts) == 4:
                table_rows += f"""
                    <tr style='border: 1px solid #ddd; background-color: white;'>
                        <td style='padding: 8px;'>{parts[0]}</td>
                        <td style='padding: 8px;'>{parts[1]}</td>
                        <td style='padding: 8px;'>{parts[2]}</td>
                        <td style='padding: 8px;'>{parts[3]}</td>
                    </tr>
                """

    # Handle greetings
    if user_message.lower().startswith(("hello", "hi", "sala", "assalam")):
        response = """
        <p style='font-style: italic;'>As-salamu alaykum wa rahmatullahi wa barakatuh. Peace be upon you, and the mercy and blessings of Allah be upon you. How can I assist you today?</p>
        """
        return response

    response = f"""
    <h3 style='color: #ffffff;'>Unani Ingredients for {user_message.capitalize()}</h3>
   <table style='width: 100%; border-collapse: collapse; margin: 20px 0;'>
    <thead>
        <tr style='background-color: white;'>
            <th style='border: 1px solid #000000; padding: 8px;'><span style='color: black;'>Ingredient</span></th>
            <th style='border: 1px solid #000000; padding: 8px;'><span style='color: black;'>Dosage</span></th>
            <th style='border: 1px solid #000000; padding: 8px;'><span style='color: black;'>Benefits</span></th>
            <th style='border: 1px solid #000000; padding: 8px;'><span style='color: black;'>Precautions</span></th>
        </tr>
    </thead>
    <tbody style='color: black;'>
    {table_rows}
    </tbody>
</table>
    <p style='font-style: italic;'>Indeed, the cure is Allah's will.</p>
    """
    return response


# Home Page
def index(request):
    """
    Home page render karta hai.
    """
    return render(request, 'index.html')

def logout(request):
    """
    Logout functionality handle karta hai aur session clear karta hai.
    """
    request.session.flush()  # Session clear karo
    return redirect('index')  # Home page par redirect karo

# Chat Page
def chat_view(request):
    """
    Chat page render karta hai aur user ki conversation history fetch karta hai.
    """
    if 'user_id' not in request.session:
        return redirect('login')  # Agar user login nahi hai to login page par redirect karo

    user_id = request.session['user_id']
    history = get_conversation_history(user_id)  # User ki conversation history fetch karo
    return render(request, 'chat.html', {'history': history})

# Signup Functionality
def signup(request):
    """
    Signup functionality handle karta hai.
    """
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Database mein user ko store karo
        try:
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()

            # Check karo ki email pehle se exist karta hai ya nahi
            cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                messages.error(request, 'User with this email already exists.')
                return redirect('signup')

            # Naya user add karo
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
            messages.success(request, 'Account created successfully! Please login.')
        except sqlite3.Error as e:
            messages.error(request, f'Database error: {str(e)}')
        finally:
            conn.close()

        return redirect('login')
    
    return render(request, 'signup.html')

# Login Functionality
def login(request):
    """
    Login functionality handle karta hai aur session mein user_id store karta hai.
    """
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Database se user ko verify karo
        try:
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()

            if user:
                # User login successful
                request.session['user_id'] = user[0]  # Session mein user_id store karo
                messages.success(request, 'Welcome! You have successfully logged in.')
                return redirect('index')  # Chat page par redirect karo
            else:
                messages.error(request, 'Invalid email or password.')
        except sqlite3.Error as e:
            messages.error(request, f'Database error: {str(e)}')
        finally:
            conn.close()

    return render(request, 'login.html')

# Remove Markdown Formatting
def remove_markdown_formatting(text):
    """
    Removes Markdown formatting like **bold**, *italic*, and bullet points from text.
    """
    text = re.sub(r'(\*\*|\*|__|_)(.*?)\1', r'\2', text)
    text = re.sub(r'^\s*[\*\-]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\s*\n', '\n', text).strip()
    return text

# Fetch Conversation History
def get_conversation_history(user_id):
    """
    Fetches conversation history for a specific user.
    """
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

# Chatbot Response Handler
@csrf_exempt
def chatbot_response(request):
    """
    Handles chatbot responses via AJAX and stores conversations.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            user_id = request.session.get('user_id')  # Session se user_id fetch karo

            if not user_message:
                return JsonResponse({"error": "No message provided"}, status=400)

            # Generate chatbot response
            response = generate_chat_response(user_message)

            # Store conversation in database
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversations (user_id, message, response)
                VALUES (?, ?, ?)
            ''', (user_id, user_message, response))
            conn.commit()
            conn.close()

            return JsonResponse({"response": response})
        except Exception as e:
            print(f"Error in chatbot_response: {e}")  # Debugging ke liye
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)

# Emergency Assistance Functionality
@csrf_exempt
def emergency_assistance(request):
    if request.method == "POST":
        try:
            # Parse the request body
            data = json.loads(request.body)
            user_lat = data.get("latitude")
            user_lon = data.get("longitude")

            # Call Google Places API to find nearby hospitals/clinics
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={user_lat},{user_lon}&radius=5000&type=hospital&keyword=Unani&key={GOOGLE_PLACES_API_KEY}"
            response = requests.get(url)
            places_data = response.json()

            # Format the response
            facilities = []
            for place in places_data.get("results", []):
                facilities.append({
                    "name": place.get("name"),
                    "address": place.get("vicinity"),
                    "rating": place.get("rating", "N/A"),
                })

            # Return the response
            return JsonResponse({"facilities": facilities})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)

# Temporary storage for medicine reminders (replace with database in production)
# Global list to store medicine reminders
medicine_reminders_list = []

@csrf_exempt
def add_medicine_reminder(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            medicine_name = data.get("medicine_name")
            dosage = data.get("dosage")
            schedule = data.get("schedule")  # e.g., "08:00 AM, 02:00 PM, 08:00 PM"
            start_date = data.get("start_date")
            end_date = data.get("end_date")

            # Fetch user_id from session
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({"status": "error", "message": "User not logged in"}, status=401)

            # Save the reminder in the database
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
    """
    Fetches reminders for the logged-in user.
    """
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({"status": "error", "message": "User not logged in"}, status=401)

    # Fetch reminders from the database
    conn = sqlite3.connect('signup.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT medicine_name, dosage, schedule, start_date, end_date
        FROM medicine_reminders
        WHERE user_id = ?
    ''', (user_id,))
    reminders = cursor.fetchall()
    conn.close()

    # Format the reminders
    formatted_reminders = []
    for reminder in reminders:
        formatted_reminders.append({
            "medicine_name": reminder[0],
            "dosage": reminder[1],
            "schedule": reminder[2],
            "start_date": reminder[3],
            "end_date": reminder[4],
        })

    return JsonResponse({"reminders": formatted_reminders})

@csrf_exempt
def send_medicine_reminders(request):
    """
    Sends email reminders for medicine schedules to the logged-in user's email.
    All emails are sent FROM jahirshaikh162003@gmail.com.
    """
    if request.method == "POST":
        try:
            now = datetime.now().strftime("%I:%M %p")  # Current time in 12-hour format
            print(f"Current time: {now}")  # Debugging log

            # Fetch the logged-in user's email
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({"status": "error", "message": "User not logged in"}, status=401)

            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
            email = cursor.fetchone()[0]  # Fetch the logged-in user's email
            conn.close()

            print(f"Logged-in user's email: {email}")  # Debugging log

            # Fetch reminders for the logged-in user from the database
            conn = sqlite3.connect('signup.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT medicine_name, dosage, schedule
                FROM medicine_reminders
                WHERE user_id = ?
            ''', (user_id,))
            reminders = cursor.fetchall()
            conn.close()

            print(f"Fetched reminders: {reminders}")  # Debugging log

            # Iterate through all reminders
            for reminder in reminders:
                medicine_name = reminder[0]
                dosage = reminder[1]
                schedule = reminder[2]

                print(f"Checking reminder for {email}: {medicine_name} at {schedule}")  # Debugging log

                # Check if the current time matches any of the scheduled times
                if now in schedule:
                    print(f"Time match found for {email}")  # Debugging log

                    # Send the reminder email
                    print(f"Sending email to: {email}")  # Debugging log
                    subject = f"Reminder: Take {medicine_name}"
                    message = f"Hello,\n\nIt's time to take your medicine:\n\nMedicine: {medicine_name}\nDosage: {dosage}\n\nThank you!"
                    try:
                        send_mail(
                            subject,  # Email subject
                            message,  # Email message
                            'jahirshaikh162003@gmail.com',  # FROM email address
                            [email],  # TO email address (logged-in user's email)
                            fail_silently=False,
                        )
                        print(f"Email sent to {email}")  # Debugging log
                    except Exception as e:
                        print(f"Error sending email to {email}: {e}")  # Debugging log

                    # Return a success message with an alert
                    return JsonResponse({
                        "status": "success",
                        "message": f"Reminder sent to {email} at {now}.",
                        "alert": "Email reminder sent successfully!"
                    })

            print("No reminders to send at this time.")  # Debugging log
            return JsonResponse({
                "status": "success",
                "message": "No reminders to send at this time."
            })
        except Exception as e:
            print(f"Error in send_medicine_reminders: {e}")  # Debugging log
            return JsonResponse({
                "status": "error",
                "message": str(e)
            }, status=500)
    return JsonResponse({
        "status": "error",
        "message": "Invalid request method"
    }, status=400)