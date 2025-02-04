from django.db import models

class UserChat(models.Model):
    user_message = models.TextField()  # User ka message
    bot_response = models.TextField()  # Bot ka reply
    timestamp = models.DateTimeField(auto_now_add=True)  # Message time store karega

    def __str__(self):
        return f"User: {self.user_message[:50]} - Bot: {self.bot_response[:50]}"

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score

def train_and_predict(disease, dosage):
    # Placeholder data, replace with API integration in the future
    data = {
        'Disease': ['cough', 'malaria', 'constipation'],
        'Medicine': ['Marzanjosh', 'Sanna Makki', 'Sanna Makki'],
        'Dosage': [300, 70, 70]
    }
    df = pd.DataFrame(data)

    # Preprocessing
    df['Disease'] = df['Disease'].astype('category').cat.codes
    df['Medicine'] = df['Medicine'].astype('category').cat.codes

    # Features (X) and Target (y)
    X = df[['Disease', 'Dosage']]
    y = df['Medicine']

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Model training
    model = DecisionTreeClassifier(random_state=42)
    model.fit(X_train, y_train)

    # Model prediction
    disease_code = pd.Series([disease]).astype('category').cat.codes[0]
    medicine_code = model.predict([[disease_code, dosage]])[0]

    # Decode predicted medicine back to original label
    medicine_name = pd.Series(['Marzanjosh', 'Sanna Makki']).iloc[medicine_code]
    
    return medicine_name
