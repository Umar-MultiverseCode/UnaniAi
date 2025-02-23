import re
import sqlite3
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import google.generativeai as genai
from django.contrib import messages
from datetime import datetime

# Gemini API Setup
genai.configure(api_key="AIzaSyCnLkFs3-8aufez4jPpQFnahj4ropCNBfg")
model = genai.GenerativeModel("gemini-1.5-flash")

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

    conn.commit()
    conn.close()
    print("Database and tables created successfully!")  # Debugging ke liye
create_database()

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
    Removes any markdown-style formatting (e.g., **bold** or *italic*) from the response text.
    """
    text = re.sub(r'(\*\*|\*|__|_)(.*?)\1', r'\2', text)  # Removes **bold** or *italic*
    text = re.sub(r'\n\s*\*\s*(.*)', r'\1', text)  # Removes bullet points (list formatting)
    return text.strip()

# Fetch Unani Remedy
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

# Generate Chatbot Response
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
    You are an expert in Unani medicine. Answer based on Unani principles.when user starts conversation with greetings answer As-salamu alaykum wa rahmatullahi wa barakatuh.Peace be upon you, and the mercy and blessings of Allah be upon you.How can I assist you today?.



    User: {user_message}
    Bot:
    """
    response = model.generate_content(prompt)
    return response.text

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