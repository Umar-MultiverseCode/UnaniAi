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

# Temporary Tib Medicine Database (unchanged)
unani_medicines = {
    "cough": {
        "symptoms": ["Dry throat", "Chest congestion", "Difficulty breathing"],
        "treatment": ["Take honey with ginger", "Drink liquorice root tea"],
        "medicine": [{"name": "Marzanjosh", "link": "https://aetmaad.co.in/product/al-marzanjosh", "price": 300}]
    },
    # Baaki data same rakha, short kar diya brevity ke liye
}

# Temporary Tib Ingredients Database (unchanged)
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
    print("Tib ingredients database populated successfully!")
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
    
    # Determine severity level and appropriate ingredient count
    ingredient_count = determine_severity_and_count(disease)
    
    # If we have fewer than required ingredients, call Gemini to generate more
    if len(unique_ingredients) < ingredient_count:
        # Generate additional ingredients using Gemini API
        additional_ingredients = generate_additional_ingredients(disease, ingredient_count - len(unique_ingredients))
        for ing in additional_ingredients:
            unique_ingredients.append(ing)
    
    return unique_ingredients[:ingredient_count]  # Limit to the appropriate count

def determine_severity_and_count(condition):
    """Determine the severity of a condition and the appropriate number of remedies"""
    # Map condition keywords to severity levels
    severity_mapping = {
        # Mild conditions - 3 remedies
        "cold": 3, "cough": 3, "headache": 3, "indigestion": 3, "acidity": 3,
        "gas": 3, "constipation": 3, "diarrhea": 3, "minor": 3, "mild": 3,
        
        # Moderate conditions - 4 remedies
        "fever": 4, "flu": 4, "infection": 4, "asthma": 4, "bronchitis": 4,
        "allergy": 4, "arthritis": 4, "pain": 4, "moderate": 4, "joint pain": 4,
        
        # Severe conditions - 5 remedies
        "pneumonia": 5, "tuberculosis": 5, "cancer": 5, "diabetes": 5, "heart": 5,
        "liver": 5, "kidney": 5, "chronic": 5, "severe": 5, "serious": 5,
        
        # Very severe conditions - 6 remedies
        "terminal": 6, "critical": 6, "emergency": 6, "life-threatening": 6
    }
    
    # Check if condition contains any keywords
    condition_terms = condition.lower().split()
    max_count = 3  # Default to mild (3 remedies)
    
    for term in condition_terms:
        if term in severity_mapping and severity_mapping[term] > max_count:
            max_count = severity_mapping[term]
    
    return max_count

def generate_additional_ingredients(condition, count):
    """Generate additional ingredients for a condition when database has insufficient entries"""
    prompt = f"""
    You are an expert in Tib medicine (Unani). I need exactly {count} more unique ingredients/remedies for treating '{condition}'.
    For each ingredient, provide:
    1. The ingredient name (use common traditional Unani ingredients)
    2. The benefits (2-3 specific benefits directly related to treating {condition})
    3. How to use it (specific dosage and usage instructions)
    
    Format your response strictly as follows (one ingredient per line, with pipe separators, no numbering):
    Ingredient Name | Specific benefits for {condition} | Detailed usage instructions with dosage
    
    For example:
    Black Seed | Reduces inflammation, boosts immunity | Take 1/2 teaspoon with honey twice daily
    
    Do not include any explanations, bullet points, or other text. Just provide exactly {count} ingredients in the format shown.
    """
    
    try:
        gemini_response = model.generate_content(prompt).text.strip()
        
        # Process the response into the right format
        ingredients = []
        lines = gemini_response.split('\n')
        
        for line in lines:
            # Skip empty lines and headers
            if not line.strip() or "Ingredient" in line and "Benefits" in line and "Usage" in line:
                continue
                
            # Handle pipe-separated format (preferred)
            if "|" in line:
                parts = [part.strip() for part in line.split('|')]
                if len(parts) >= 3:
                    ingredients.append((parts[0], parts[1], parts[2]))
            
            # Alternative format handling
            elif ":" in line:
                # Try to parse formats like "Ingredient: Benefits - Usage"
                try:
                    ingredient = line.split(':', 1)[0].strip()
                    rest = line.split(':', 1)[1].strip()
                    
                    # Check for dash separator
                    if '-' in rest:
                        benefits, usage = rest.split('-', 1)
                        ingredients.append((ingredient, benefits.strip(), usage.strip()))
                    # If no dash, try to split by sentence
                    else:
                        sentences = re.split(r'(?<=[.!?])\s+', rest)
                        if len(sentences) >= 2:
                            benefits = sentences[0]
                            usage = ' '.join(sentences[1:])
                            ingredients.append((ingredient, benefits, usage))
                except:
                    # Skip if parsing fails
                    continue
        
        # If we still don't have enough ingredients, fill with defaults
        if len(ingredients) < count:
            default_ingredients = [
                ("Honey", "Natural antibiotic, soothes inflammation, alleviates symptoms", "Take 1 teaspoon with warm water thrice daily"),
                ("Ginger", "Anti-inflammatory, improves circulation, reduces congestion", "Steep sliced ginger in hot water for 10 minutes, drink 3 cups daily"),
                ("Black Seed", "Boosts immunity, reduces inflammation, relieves symptoms", "Take 1/2 teaspoon with honey twice daily"),
                ("Olive Oil", "Soothes irritation, anti-inflammatory, lubricates throat", "Take 1 teaspoon with a pinch of turmeric twice daily"),
                ("Licorice Root", "Soothes throat, reduces inflammation, expectorant", "Prepare as tea using 1-2 grams of root, drink twice daily")
            ]
            
            # Add only the needed number of default ingredients
            needed = count - len(ingredients)
            for i in range(min(needed, len(default_ingredients))):
                if default_ingredients[i][0].lower() not in [ing[0].lower() for ing in ingredients]:
                    ingredients.append(default_ingredients[i])
        
        # Return only the number we need
        return ingredients[:count]
    except Exception as e:
        print(f"Error generating additional ingredients: {e}")
        # Fallback default ingredients if API fails
        default_ingredients = [
            ("Honey", "Natural antibiotic, soothes inflammation, alleviates symptoms", "Take 1 teaspoon with warm water thrice daily"),
            ("Ginger", "Anti-inflammatory, improves circulation, reduces congestion", "Steep sliced ginger in hot water for 10 minutes, drink 3 cups daily"),
            ("Black Seed", "Boosts immunity, reduces inflammation, relieves symptoms", "Take 1/2 teaspoon with honey twice daily"),
            ("Olive Oil", "Soothes irritation, anti-inflammatory, lubricates throat", "Take 1 teaspoon with a pinch of turmeric twice daily"),
            ("Licorice Root", "Soothes throat, reduces inflammation, expectorant", "Prepare as tea using 1-2 grams of root, drink twice daily")
        ]
        return default_ingredients[:count]

def generate_chat_response(user_message):
    """
    Generates a crisp, table-formatted response for Tib medicine queries with inline CSS.
    Ensures a minimum of 3 remedies for all conditions.
    """
    user_message = user_message.lower().strip()

    # Extract actual condition/topic from the message
    condition = extract_condition(user_message)
    
    # List of valid health conditions in Unani/Tibb medicine (expanded to include more conditions)
    valid_health_conditions = [
        # Common conditions
        "fever", "cough", "cold", "headache", "migraine", "sore throat", 
        "stomach pain", "gas", "acidity", "heartburn", "constipation", "diarrhea", 
        "nausea", "vomiting", "insomnia", "anxiety", "depression", "stress",
        "joint pain", "arthritis", "backache", "skin rash", "eczema", "psoriasis",
        "hair loss", "dandruff", "eye infection", "fatigue", "weakness", "anemia",
        "hypertension", "asthma", "diabetes", "obesity", "ulcer", "kidney stone",
        "piles", "jaundice", "alzheimer", "pneumonia", "tuberculosis", "malaria",
        "dengue", "allergy", "influenza", "indigestion", "bloating", "bronchitis",
        "sinusitis", "tonsillitis", "thyroid", "gastritis", "menstrual pain",
        "erectile dysfunction", "high cholesterol", "low blood pressure", "gout",
        "sciatica", "cystitis", "urinary tract infection", "prostate", "vertigo",
        
        # Weight issues
        "underweight", "weight loss", "malnutrition", "thin", "skinny", "lean", 
        "overweight", "weight gain", "obesity", "fat",
        
        # Dental conditions
        "pyria", "pyorrhea", "gingivitis", "periodontitis", "gum disease", "gum bleeding",
        "tooth decay", "dental caries", "tooth pain", "toothache", "oral ulcer",
        
        # Cancer types
        "cancer", "carcinoma", "tumor", "leukemia", "lymphoma", "sarcoma",
        "breast cancer", "lung cancer", "lungs cancer", "stomach cancer", "liver cancer",
        "colon cancer", "prostate cancer", "skin cancer", "cervical cancer",
        
        # Other common health issues
        "acne", "pimples", "boil", "abscess", "wound", "burn", "sprain", "fracture",
        "dislocation", "paralysis", "stroke", "epilepsy", "seizure", "parkinson",
        "dementia", "memory loss", "forgetfulness", "hearing loss", "deafness",
        "vision loss", "blindness", "cataracts", "glaucoma", "digestive problem",
        "food poisoning", "addiction", "alcoholism"
    ]
    
    # Common medical terms that might indicate a valid condition
    medical_terms = [
        "pain", "ache", "inflammation", "swelling", "infection", "disorder", 
        "disease", "syndrome", "condition", "ailment", "illness", "virus", 
        "bacterial", "chronic", "acute", "symptoms", "treatment", "remedy", 
        "cancer", "tumor", "cyst", "lesion", "wound", "injury", "fracture", 
        "sprain", "strain", "rupture", "bleeding", "discharge", "itis",
        "deficiency", "excess", "imbalance", "dysfunction", "weak", "weak",
        "problem", "issue", "sick", "unwell", "health", "healthy"
    ]
    
    # Common non-medical terms that might indicate a person or non-medical query
    non_medical_indicators = [
        "name", "person", "place", "country", "city", "food", "movie", "song", 
        "game", "sport", "weather", "price", "cost", "buy", "sell", "purchase",
        "download", "website", "how to make", "recipe", "cook", "bake", "address",
        "location", "directions", "age", "birthday", "email", "phone", "number",
        "contact", "friend", "family", "brother", "sister", "father", "mother"
    ]
    
    # Check if the condition is a valid health condition or contains medical terminology
    is_known_condition = any(health_condition in condition for health_condition in valid_health_conditions)
    has_medical_term = any(term in condition for term in medical_terms)
    is_likely_non_medical = any(indicator in condition for indicator in non_medical_indicators) or len(condition.split()) > 6
    
    # Special handling for common health concerns - added check for single-word health issues
    is_direct_health_concern = condition in ["underweight", "overweight", "obese", "thin", "fatigue"] or "weight" in condition
    
    # Determine if this is likely a valid medical query
    is_valid_condition = is_known_condition or has_medical_term or is_direct_health_concern and not is_likely_non_medical
    
    # Generate a unique header for this condition
    response_header = generate_dynamic_header(condition) if is_valid_condition else "Health Information"
    
    # 1. Handle Pure Greetings
    greetings = ["hello", "hi", "sala", "assalam"]
    if user_message in greetings:
        return "<p style='color: white; font-style: italic;'>As-salamu alaykum! How can I assist you today?</p>"
        
    # 2. Handle identity questions
    identity_questions = ["what is your name", "who are you", "what are you", "your name", "tell me about yourself", "introduce yourself"]
    if any(question in user_message for question in identity_questions):
        return "<p style='color: white;'>I am TibAI, your personal Tibb medicine assistant. I'm designed to provide information about traditional Unani medicine, remedies, and treatments based on centuries of healing wisdom. How can I assist you with your health today?</p>"
    
    # 3. Handle general medicine requests
    general_medicine_requests = ["list of medicines", "give me medicines", "show me medicines", "medicine list", "common medicines", "popular medicines", "unani medicines", "tibb medicines"]
    if any(request in user_message for request in general_medicine_requests):
        return (f"<h3 style='color: #ffffff;'>Common Unani Medicines</h3>"
                f"<p style='color: white;'>Here are some widely used medicines in Unani (Tibb) practice:</p>"
                f"<table style='width: 100%; border-collapse: collapse; margin: 10px 0;'>"
                f"<thead><tr style='background-color: white;'>"
                f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Medicine</span></th>"
                f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Primary Uses</span></th>"
                f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Form</span></th>"
                f"<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Properties</span></th>"
                f"</tr></thead><tbody style='color: black;'>"
                f"<tr style='border: 1px solid #ddd; background-color: white;'><td style='padding: 8px;'>Majoon Falasfa</td><td style='padding: 8px;'>Brain and nerve tonic, memory enhancer</td><td style='padding: 8px;'>Herbal jam</td><td style='padding: 8px;'>Improves cognitive functions, relieves stress</td></tr>"
                f"<tr style='border: 1px solid #ddd; background-color: white;'><td style='padding: 8px;'>Sharbat Unnab</td><td style='padding: 8px;'>Respiratory conditions, fever</td><td style='padding: 8px;'>Syrup</td><td style='padding: 8px;'>Anti-inflammatory, expectorant</td></tr>"
                f"<tr style='border: 1px solid #ddd; background-color: white;'><td style='padding: 8px;'>Khamira Abresham</td><td style='padding: 8px;'>Heart tonic, anxiety, depression</td><td style='padding: 8px;'>Semi-solid preparation</td><td style='padding: 8px;'>Cardioprotective, calming</td></tr>"
                f"<tr style='border: 1px solid #ddd; background-color: white;'><td style='padding: 8px;'>Kushta Marwareed</td><td style='padding: 8px;'>General weakness, calcium deficiency</td><td style='padding: 8px;'>Calcined powder</td><td style='padding: 8px;'>Strengthening, immune-boosting</td></tr>"
                f"</tbody></table>"
                f"<p style='color: white; font-style: italic;'>These medicines should be taken under the guidance of a qualified Unani practitioner. Indeed, the cure is Allah's will.</p>")

    # Check if the input is not a valid health condition
    if not is_valid_condition:
        return "<p style='color: white;'>I'm trained to provide information about health conditions and traditional Unani remedies. It seems you've entered something that may not be a health condition. Please ask about specific health issues or symptoms for which you'd like Unani medicine information.</p>"

    # 4. Check Known Diseases in unani_medicines
    words = user_message.split()
    for word in words:
        if word in unani_medicines:
            data = unani_medicines[word]
            # Ensure we have a minimum of 3 medicines/treatments
            if len(data.get('treatment', [])) < 3:
                # Generate additional treatments if needed
                additional_treatments = generate_additional_ingredients(word, 3 - len(data.get('treatment', [])))
                for treatment in additional_treatments:
                    data['treatment'].append(f"Use {treatment[0]}: {treatment[2]}")
                
            response = f"<h3 style='color: white;'>{response_header}</h3>"
            response += f"<p style='color: white;'><strong style='color: #ffcc00;'>Symptoms:</strong> {', '.join(data['symptoms'])}</p>"
            response += f"<p style='color: white;'><strong style='color: #ffcc00;'>Treatment:</strong> {', '.join(data['treatment'])}</p>"
            
            # Build medicine table if available
            if data.get("medicine"):
                response += "<table style='width: 100%; border-collapse: collapse; margin: 10px 0;'>"
                response += "<thead><tr style='background-color: white;'>"
                response += "<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Medicine</span></th>"
                response += "<th style='border: 1px solid #000; padding: 8px;'><span style='color: black;'>Price</span></th>"
                response += "</tr></thead><tbody style='color: black;'>"
                
                for med in data["medicine"]:
                    response += f"<tr style='border: 1px solid #ddd; background-color: white;'>"
                    response += f"<td style='padding: 8px;'><a href='{med['link']}'>{med['name']}</a></td>"
                    response += f"<td style='padding: 8px;'>₹{med['price']}</td></tr>"
                
                response += "</tbody></table>"
            
            response += "<p style='color: white; font-style: italic;'>Indeed, the cure is Allah's will.</p>"
            return response

    # 5. Check Tib Ingredients Table (if populated)
    ingredients = get_unani_ingredients(condition)
    if ingredients:
        # Add a brief description about the condition before the table
        description = get_condition_description(condition)
        
        table_rows = "".join(
            f"<tr style='border: 1px solid #ddd; background-color: white;'>"
            f"<td style='padding: 8px; color: black;'>{ing[0]}</td>"
            f"<td style='padding: 8px; color: black;'>{ing[1]}</td>"
            f"<td style='padding: 8px; color: black;'>{ing[2]}</td>"
            f"</tr>" for ing in ingredients
        )
        return (f"<h3 style='color: #ffffff;'>{response_header}</h3>"
                f"<p style='color: white;'>{description}</p>"
                f"<table style='width: 100%; border-collapse: collapse; margin: 10px 0;'>"
                f"<thead><tr style='background-color: white;'>"
                f"<th style='border: 1px solid #000; padding: 8px; color: black;'>Ingredient</th>"
                f"<th style='border: 1px solid #000; padding: 8px; color: black;'>Benefits</th>"
                f"<th style='border: 1px solid #000; padding: 8px; color: black;'>Usage</th>"
                f"</tr></thead><tbody>{table_rows}</tbody></table>"
                f"<p style='color: white; font-style: italic;'>Indeed, the cure is Allah's will.</p>")

    # 6. Fallback to Gemini API with Dynamic Remedy Count
    # Determine severity and remedy count using our new function
    remedy_count = determine_severity_and_count(condition)

    prompt = f"""
    You are an expert in Tib medicine (Unani medicine). Provide a response about '{condition}' in this exact format:

    First, write a brief 2-3 sentence explanation about the condition from a Tib medicine perspective. Don't use any markdown formatting, asterisks, or special characters. Write in plain text.

    Then, provide exactly {remedy_count} DIFFERENT Tib remedies (do not repeat the same ingredient) in this table format:
    | Ingredient | Dosage | Benefits | Precautions |
    |------------|--------|----------|-------------|
    | [ingredient name] | [dosage] | [benefits] | [precautions] |

    Make sure each remedy uses a UNIQUE ingredient - do not repeat any ingredients.
    End with "Indeed, the cure is Allah's will."

    If it's not a health query, reply: "I'm here to help with Tib medicine. Ask me about health conditions or treatments."
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
                              f"<td style='padding: 8px; color: black;'>{parts[0]}</td>"
                              f"<td style='padding: 8px; color: black;'>{parts[1]}</td>"
                              f"<td style='padding: 8px; color: black;'>{parts[2]}</td>"
                              f"<td style='padding: 8px; color: black;'>{parts[3]}</td></tr>")
        
        # Handle tab-separated format as fallback
        elif in_table and "\t" in line and header_found:
            parts = [part.strip() for part in line.split('\t')]
            if len(parts) >= 4:
                table_rows += (f"<tr style='border: 1px solid #ddd; background-color: white;'>"
                              f"<td style='padding: 8px; color: black;'>{parts[0]}</td>"
                              f"<td style='padding: 8px; color: black;'>{parts[1]}</td>"
                              f"<td style='padding: 8px; color: black;'>{parts[2]}</td>"
                              f"<td style='padding: 8px; color: black;'>{parts[3]}</td></tr>")

    # 7. Handle Random Queries or Gemini Fallback
    if "I'm here to help" in gemini_response:
        return "<p style='color: white;'>I'm here to help with Tib medicine. Ask me about health conditions or treatments.</p>"
    
    # Final cleanup of description
    description = description.replace("1.", "").replace("2.", "").strip()
    description = re.sub(r'\s+', ' ', description)  # Replace multiple spaces with a single space
    
    # Check if we have enough rows - if not, generate some
    if table_rows.count("<tr") < 3:
        # Generate additional ingredients
        additional_ingredients = generate_additional_ingredients(condition, 3 - table_rows.count("<tr"))
        for ing in additional_ingredients:
            table_rows += (f"<tr style='border: 1px solid #ddd; background-color: white;'>"
                          f"<td style='padding: 8px; color: black;'>{ing[0]}</td>"
                          f"<td style='padding: 8px; color: black;'>Appropriate dosage</td>"
                          f"<td style='padding: 8px; color: black;'>{ing[1]}</td>"
                          f"<td style='padding: 8px; color: black;'>Consult a Tib practitioner for individual guidance</td></tr>")
    
    return (f"<h3 style='color: #ffffff;'>{response_header}</h3>"
            f"<p style='color: white;'>{description}</p>"
            f"<table style='width: 100%; border-collapse: collapse; margin: 10px 0;'>"
            f"<thead><tr style='background-color: white;'>"
            f"<th style='border: 1px solid #000; padding: 8px; color: black;'>Ingredient</th>"
            f"<th style='border: 1px solid #000; padding: 8px; color: black;'>Dosage</th>"
            f"<th style='border: 1px solid #000; padding: 8px; color: black;'>Benefits</th>"
            f"<th style='border: 1px solid #000; padding: 8px; color: black;'>Precautions</th>"
            f"</tr></thead><tbody>{table_rows}</tbody></table>"
            f"<p style='color: white; font-style: italic;'>Indeed, the cure is Allah's will.</p>")

def generate_dynamic_header(condition):
    """Generate varied and unique headers for each condition"""
    # Use current timestamp to create variation even for the same condition
    seed = int(time.time()) % 100
    random.seed(seed)
    
    # Properly capitalize the condition (handle multi-word conditions)
    capitalized_condition = ' '.join(word.capitalize() for word in condition.split())
    
    # Create a list of template headers with more variety
    templates = [
        f"Tib Remedies for {capitalized_condition}",
        f"Natural Treatment: {capitalized_condition}",
        f"Tibb-e-Nabawi: Healing {capitalized_condition}",
        f"Traditional Cures for {capitalized_condition}",
        f"Healing {capitalized_condition} with Tib Medicine",
        f"Ancient Wisdom for {capitalized_condition}",
        f"Prophetic Medicine for {capitalized_condition}",
        f"{capitalized_condition}: Tib Solutions",
        f"Treating {capitalized_condition} Naturally",
        f"Holistic Approach to {capitalized_condition}",
        f"{capitalized_condition}: Balancing the Humors",
        f"Tib Perspective on {capitalized_condition}",
        f"Addressing {capitalized_condition} with Tibb",
        f"{capitalized_condition}: Nature's Pharmacy",
        f"Time-Tested Remedies for {capitalized_condition}",
        f"Unani Treatment for {capitalized_condition}",
        f"{capitalized_condition}: The Unani Approach",
        f"Traditional Healing for {capitalized_condition}",
        f"Herbal Remedies for {capitalized_condition}",
        f"Managing {capitalized_condition} with Tib Medicine"
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
        "fever": "According to Tib medicine, fever (Humma) is an increase in innate heat that spreads throughout the body through the heart, arteries and blood. It is often associated with an imbalance in the phlegmatic or bilious humors and can be treated with cooling herbs and dietary adjustments.",
        "cough": "In Tib medicine, cough (Sual) is considered a symptom of disruption in the respiratory system, often due to accumulation of phlegm or irritation in the airways. Traditional treatments focus on balancing the body's moisture and removing excess phlegm.",
        "headache": "Headaches (Suda) in Tib medicine are attributed to imbalances in blood, phlegm, or bile affecting the head region. Treatment typically involves restoring humoral balance through herbs, dietary changes, and sometimes cupping therapy.",
        "cold": "The common cold (Nazla) in Tib medicine is viewed as an accumulation of cold humors in the respiratory system. Treatment aims to restore warmth and eliminate excess phlegm through warming herbs and proper dietary regimen.",
        "piles": "Piles (Bawaseer) in Tib medicine are attributed to an excess of black bile or blood in the rectal veins. Traditional treatments focus on cooling the blood, improving bowel movements, and reducing inflammation through herbs and dietary modifications.",
        "constipation": "Constipation (Qabz) in Tib medicine is considered a result of dryness in the intestines or weakness in the expulsive faculty. Treatment includes moistening herbs, dietary adjustments, and sometimes gentle laxatives to restore normal bowel function."
    }
    
    # Check for exact matches first
    if condition in descriptions:
        return descriptions[condition]
    
    # Check for partial matches
    for key, desc in descriptions.items():
        if key in condition or condition in key:
            return desc
    
    # Default description for unknown conditions
    return f"In Tib medicine, health conditions like {condition} are typically approached by understanding the imbalance in bodily humors (Akhlaat) and temperament (Mizaj). Treatment focuses on restoring balance through natural remedies, dietary adjustments, and lifestyle modifications."

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
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={user_lat},{user_lon}&radius=5000&type=hospital&keyword=Tib&key={GOOGLE_PLACES_API_KEY}"
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