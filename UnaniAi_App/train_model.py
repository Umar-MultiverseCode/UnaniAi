import pandas as pd
import joblib  # To save and load the model
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

# ✅ Step 1: Prepare Training Data
data = {
    'Disease': ['cough', 'malaria', 'constipation'],
    'Medicine': ['Marzanjosh', 'Sanna Makki', 'Sanna Makki'],
    'Dosage': [300, 70, 70]
}
df = pd.DataFrame(data)

# ✅ Step 2: Preprocess Data
df['Disease'] = df['Disease'].astype('category').cat.codes
df['Medicine'] = df['Medicine'].astype('category').cat.codes

X = df[['Disease', 'Dosage']]
y = df['Medicine']

# ✅ Step 3: Train-test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# ✅ Step 4: Train the Model
model = DecisionTreeClassifier(random_state=42)
model.fit(X_train, y_train)

# ✅ Step 5: Save the Trained Model
joblib.dump(model, 'trained_model.pkl')

print("✅ Model training complete! Model saved as 'trained_model.pkl'")
