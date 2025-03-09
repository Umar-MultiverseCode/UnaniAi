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

# UnaniAI Class for Chatbot Logic
class UnaniAI:
    def __init__(self):
        self.conversation_history = []
        self.language = "mixed"  # Default: Hindi-English mix

    def generate_chat_response(self, user_message):
        user_message_lower = user_message.lower().strip()
        words = user_message_lower.split()
        self.conversation_history.append(user_message)

        # Language Switch (Priority over everything)
        if "talk in english" in user_message_lower:
            self.language = "english"
            return """
            <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Alright, bro! I'll stick to English from now on. How can I help you today?</p>
            """
        elif "hindi mein baat kar" in user_message_lower:
            self.language = "hindi"
            return """
            <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Theek hai, bhai! Ab Hindi mein baat karunga. Kya baat hai?</p>
            """

        # Greeting Handling
        greetings = ["hello", "hi", "sala", "assalam", "as-salam", "salaam"]
        if any(user_message_lower.startswith(greet) for greet in greetings):
            if self.language == "english":
                return """
                <p style='font-style: italic; color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>As-salamu alaykum, bro! Thanks for reaching out. How can I assist you?</p>
                """
            else:
                return """
                <p style='font-style: italic; color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>As-salamu alaykum, bhai! Shukran for reaching out. Kya baat hai, kaise madad karoon?</p>
                """

        # Personal Queries
        if "aap kon" in user_message_lower or "who are you" in user_message_lower:
            if self.language == "english":
                return """
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>I’m UnaniAI, bro—your guide to prophetic Unani wisdom. Here to help with natural healing. What’s up?</p>
                """
            else:
                return """
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, main UnaniAI hoon—tera prophetic Unani wisdom wala dost. Natural tareekon se sehat theek karta hoon. Tu bol, kya chahiye?</p>
                """
        elif "apka naam kya" in user_message_lower:
            if self.language == "english":
                return """
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>My name’s UnaniAI, bro! Your buddy for Unani remedies. What’s going on?</p>
                """
            else:
                return """
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Naam hai UnaniAI, bhai! Tera Unani ilaaj ka saathi hoon. Kya chal raha hai tere saath?</p>
                """
        elif "who made you" in user_message_lower or "tujhe kisne develop kiya" in user_message_lower or "tujhe kisne banaya" in user_message_lower:
            if self.language == "english":
                return """
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>I was made by the xAI team, bro. They mixed AI with Unani knowledge to create me. What’s on your mind?</p>
                """
            else:
                return """
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Mujhe xAI ke logon ne banaya, bhai. Unani knowledge ke saath AI mix karke tera bhai taiyar hua. Ab bol, kya problem hai?</p>
                """

        # Casual Talk with Context
        casual_phrases = ["kuch nahi", "sab mast", "kya haal", "what’s up", "chill marao"]
        if any(phrase in user_message_lower for phrase in casual_phrases):
            last_medical = None
            for past_msg in reversed(self.conversation_history[:-1]):
                for word in past_msg.lower().split():
                    if word in unani_medicines:
                        last_medical = word
                        break
                if last_medical:
                    break
            if last_medical:
                if self.language == "english":
                    return f"""
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Cool, bro! You said you had {last_medical} earlier—everything okay now, or you just chilling?</p>
                    """
                else:
                    return f"""
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Mast hai, bhai! Tune bola tha {last_medical} hai—ab sab theek hai ya bas aise hi chill karna hai?</p>
                    """
            else:
                if self.language == "english":
                    return """
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Alright, bro! Good to know everything’s fine. Anything you want to talk about?</p>
                    """
                else:
                    return """
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Haan bhai, sab mast hai toh shukar! Koi baat karna hai ya aise hi chill karna hai?</p>
                    """

        # Medical Query Handling
        medical_keywords = ["fever", "cough", "pain", "problem", "joint", "sex", "cold", "headache", "stamina", "energy"]
        is_medical = any(keyword in user_message_lower for keyword in medical_keywords)
        context_diseases = [word for word in words if word in unani_medicines]

        if is_medical:
            # Table Request
            if "table" in user_message_lower or "ingredient" in user_message_lower:
                diseases = context_diseases if context_diseases else [word for past_msg in self.conversation_history[:-1] for word in past_msg.lower().split() if word in unani_medicines]
                if diseases:
                    table_rows = ""
                    for disease in diseases[:3]:  # Limit to 3 conditions
                        if disease in unani_medicines:
                            ingredients = unani_medicines[disease].get("ingredients", [
                                {"name": "Generic", "dosage": "As advised", "benefits": "Supports healing", "precautions": "Consult a healer"}
                            ])
                            for ing in ingredients:
                                table_rows += f"""
                                    <tr style='border: 1px solid #ddd; background-color: #ffffff;'>
                                        <td style='padding: 10px; color: #333;'>{ing['name']} ({disease.capitalize()})</td>
                                        <td style='padding: 10px; color: #333;'>{ing['dosage']}</td>
                                        <td style='padding: 10px; color: #333;'>{ing['benefits']}</td>
                                        <td style='padding: 10px; color: #333;'>{ing['precautions']}</td>
                                    </tr>
                                """
                    if table_rows:
                        if self.language == "english":
                            return f"""
                            <h3 style='color: #ffffff; font-family: Arial, sans-serif; font-size: 24px; margin-bottom: 15px;'>Ingredients for Your Conditions</h3>
                            <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Here’s the table with ingredients for {', '.join(diseases)}, bro:</p>
                            <table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-family: Arial, sans-serif;'>
                                <thead>
                                    <tr style='background-color: #f2f2f2;'>
                                        <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Ingredient</th>
                                        <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Dosage</th>
                                        <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Benefits</th>
                                        <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Precautions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {table_rows}
                                </tbody>
                            </table>
                            <p style='font-style: italic; color: #ffffff; font-family: Arial, sans-serif; font-size: 14px;'>Indeed, the cure is Allah's will.</p>
                            """
                        else:
                            return f"""
                            <h3 style='color: #ffffff; font-family: Arial, sans-serif; font-size: 24px; margin-bottom: 15px;'>{', '.join(diseases)} ke liye Ingredients</h3>
                            <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Yeh lo bhai, {', '.join(diseases)} ke liye ingredients table mein:</p>
                            <table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-family: Arial, sans-serif;'>
                                <thead>
                                    <tr style='background-color: #f2f2f2;'>
                                        <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Ingredient</th>
                                        <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Dosage</th>
                                        <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Benefits</th>
                                        <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Precautions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {table_rows}
                                </tbody>
                            </table>
                            <p style='font-style: italic; color: #ffffff; font-family: Arial, sans-serif; font-size: 14px;'>Indeed, the cure is Allah's will.</p>
                            """
                else:
                    if self.language == "english":
                        return """
                        <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bro, I need some clarity—which conditions do you want the table for? Tell me more!</p>
                        """
                    else:
                        return """
                        <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, thodi si detail aur de—kaunsi bimari ke liye table chahiye? Bata na!</p>
                        """

            # Standard Medical Response (Prioritize current message)
            if context_diseases:
                disease = context_diseases[0]  # Pick first detected disease from current message
                data = unani_medicines[disease]
                if self.language == "english":
                    response = f"""
                    <h3 style='color: #ffffff; font-family: Arial, sans-serif; font-size: 24px; margin-bottom: 15px;'>Unani Treatment for {disease.capitalize()}</h3>
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Here’s the treatment for {disease}, bro:</p>
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px; margin-bottom: 10px;'><strong style='color: #ffcc00;'>Symptoms:</strong> {', '.join(data['symptoms'])}</p>
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px; margin-bottom: 10px;'><strong style='color: #ffcc00;'>Treatment:</strong> {', '.join(data['treatment'])}</p>
                    """
                else:
                    response = f"""
                    <h3 style='color: #ffffff; font-family: Arial, sans-serif; font-size: 24px; margin-bottom: 15px;'>Unani Treatment for {disease.capitalize()}</h3>
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, {disease} ke liye yeh raha ilaaj:</p>
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px; margin-bottom: 10px;'><strong style='color: #ffcc00;'>Symptoms:</strong> {', '.join(data['symptoms'])}</p>
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px; margin-bottom: 10px;'><strong style='color: #ffcc00;'>Treatment:</strong> {', '.join(data['treatment'])}</p>
                    """
                if "medicine" in data and data["medicine"]:
                    response += "<h4 style='color: #ffcc00; font-family: Arial, sans-serif; font-size: 18px; margin-bottom: 10px;'>Recommended Medicines:</h4>"
                    for med in data["medicine"]:
                        response += f"<p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'><a href='{med['link']}' style='color: #00ccff; text-decoration: none;'>{med['name']}</a> - ₹{med['price']}</p>"
                return response

            # Sensitive Topics (Sex Issues)
            if "sex" in user_message_lower or "stamina" in user_message_lower or "energy" in user_message_lower:
                if any("detail" in past.lower() or "issue" in past.lower() for past in self.conversation_history[:-1]):
                    if self.language == "english":
                        return """
                        <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Got it, bro! You’re facing stamina issues during sex. Here’s some Unani help based on prophetic wisdom:</p>
                        <h3 style='color: #ffffff; font-family: Arial, sans-serif; font-size: 24px; margin-bottom: 15px;'>Unani Boost for Stamina</h3>
                        <table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-family: Arial, sans-serif;'>
                            <thead>
                                <tr style='background-color: #f2f2f2;'>
                                    <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Ingredient</th>
                                    <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Dosage</th>
                                    <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Benefits</th>
                                    <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Precautions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr style='border: 1px solid #ddd; background-color: #ffffff;'>
                                    <td style='padding: 10px; color: #333;'>Dates (Ajwa)</td>
                                    <td style='padding: 10px; color: #333;'>3-7 daily</td>
                                    <td style='padding: 10px; color: #333;'>Boosts energy, strengthens body</td>
                                    <td style='padding: 10px; color: #333;'>Avoid if diabetic</td>
                                </tr>
                                <tr style='border: 1px solid #ddd; background-color: #ffffff;'>
                                    <td style='padding: 10px; color: #333;'>Honey</td>
                                    <td style='padding: 10px; color: #333;'>1-2 tbsp daily</td>
                                    <td style='padding: 10px; color: #333;'>Natural stamina enhancer</td>
                                    <td style='padding: 10px; color: #333;'>Moderation needed</td>
                                </tr>
                            </tbody>
                        </table>
                        <p style='font-style: italic; color: #ffffff; font-family: Arial, sans-serif; font-size: 14px;'>Indeed, the cure is Allah's will.</p>
                        """
                    else:
                        return """
                        <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Samajh gaya, bhai! Sex ke waqt stamina kam ho raha hai. Unani mein iske liye natural ilaaj hai:</p>
                        <h3 style='color: #ffffff; font-family: Arial, sans-serif; font-size: 24px; margin-bottom: 15px;'>Unani Boost for Stamina</h3>
                        <table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-family: Arial, sans-serif;'>
                            <thead>
                                <tr style='background-color: #f2f2f2;'>
                                    <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Ingredient</th>
                                    <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Dosage</th>
                                    <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Benefits</th>
                                    <th style='border: 1px solid #000000; padding: 10px; color: #333;'>Precautions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr style='border: 1px solid #ddd; background-color: #ffffff;'>
                                    <td style='padding: 10px; color: #333;'>Dates (Ajwa)</td>
                                    <td style='padding: 10px; color: #333;'>3-7 daily</td>
                                    <td style='padding: 10px; color: #333;'>Boosts energy, strengthens body</td>
                                    <td style='padding: 10px; color: #333;'>Avoid if diabetic</td>
                                </tr>
                                <tr style='border: 1px solid #ddd; background-color: #ffffff;'>
                                    <td style='padding: 10px; color: #333;'>Honey</td>
                                    <td style='padding: 10px; color: #333;'>1-2 tbsp daily</td>
                                    <td style='padding: 10px; color: #333;'>Natural stamina enhancer</td>
                                    <td style='padding: 10px; color: #333;'>Moderation needed</td>
                                </tr>
                            </tbody>
                        </table>
                        <p style='font-style: italic; color: #ffffff; font-family: Arial, sans-serif; font-size: 14px;'>Indeed, the cure is Allah's will.</p>
                        """
                else:
                    if self.language == "english":
                        return """
                        <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Alright, bro! Sex issues can be sensitive—can you tell me a bit more? Like is it energy, stamina, or something else?</p>
                        """
                    else:
                        return """
                        <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, sex ki dikkat hai—samajh gaya. Thodi detail de sakta hai? Energy kam lagti hai ya stamina ka masla hai?</p>
                        """

        # Fallback with Better Context Handling
        if "sun" in user_message_lower or "listen" in user_message_lower or "baat" in user_message_lower:
            last_medical = None
            for past_msg in reversed(self.conversation_history[:-1]):
                for word in past_msg.lower().split():
                    if word in unani_medicines:
                        last_medical = word
                        break
                if last_medical:
                    break
            if last_medical:
                if self.language == "english":
                    return f"""
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bro, I’m listening! You mentioned {last_medical} before—still about that, or something else? Tell me!</p>
                    """
                else:
                    return f"""
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, sun raha hoon! Tune {last_medical} ka zikr kiya tha—usi ke baare mein baat karna hai ya kuch aur? Bol na!</p>
                    """
            else:
                if self.language == "english":
                    return """
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bro, I’m all ears! What’s on your mind? Tell me more!</p>
                    """
                else:
                    return """
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, main sun raha hoon! Kya baat hai, thodi detail de na!</p>
                    """

        # Gemini API Fallback for Out-of-Context but Relevant Questions
        relevant_keywords = ["unani", "medicine", "health", "treatment", "ai", "develop", "banaya", "kisne", "natural", "cure"]
        if any(keyword in user_message_lower for keyword in relevant_keywords) and not context_diseases and not is_medical:
            try:
                # Prompt for Gemini to keep tone and domain consistent
                prompt = f"""
                You are UnaniAI, a friendly AI built by xAI to assist with Unani medicine and natural healing. Respond to the user in a casual, 'bhai'-style tone. Keep it relevant to Unani, health, or AI development. Use {self.language} language. Here's the user message: "{user_message}". Previous conversation: {self.conversation_history[-2:] if len(self.conversation_history) > 1 else "None"}.
                Format your response in HTML like this:
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>[Your response]</p>
                """
                gemini_response = model.generate_content(prompt).text
                return gemini_response
            except Exception as e:
                if self.language == "english":
                    return """
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bro, something went wrong with my brain! Let me fix it—try asking again.</p>
                    """
                else:
                    return """
                    <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, mera dimaag thodi gadbad kar raha hai! Dobara pooch na, main theek kar dunga.</p>
                    """

        # Generic Fallback
        last_medical = None
        for past_msg in reversed(self.conversation_history[:-1]):
            for word in past_msg.lower().split():
                if word in unani_medicines:
                    last_medical = word
                    break
            if last_medical:
                break
        if last_medical:
            if self.language == "english":
                return f"""
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bro, I’m not sure what you mean. You mentioned {last_medical} earlier—still about that, or something new?</p>
                """
            else:
                return f"""
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, yeh samajh nahi aaya. Tune {last_medical} ka zikr kiya tha—usi ke baare mein hai ya kuch aur?</p>
                """
        else:
            if self.language == "english":
                return """
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bro, I’m a bit lost here. Can you give me more details so I can help you out?</p>
                """
            else:
                return """
                <p style='color: #ffffff; font-family: Arial, sans-serif; font-size: 16px;'>Bhai, yeh thoda confuse kar raha hai. Thodi aur detail de na taaki main sahi se madad kar sakoon?</p>
                """

# Global UnaniAI instance
unani_ai = UnaniAI()

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

            # Generate chatbot response using UnaniAI instance
            response = unani_ai.generate_chat_response(user_message)

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