import google.generativeai as genai

# API Key set karna
genai.configure(api_key="AIzaSyCnLkFs3-8aufez4jPpQFnahj4ropCNBfg")

# Model select karna
model = genai.GenerativeModel("gemini-1.5-flash")

print("Gemini Chatbot (Type 'exit' to quit)\n")

while True:
    user_input = input("You: ")  # Terminal se user input
    if user_input.lower() == "exit":
        print("Chatbot: Goodbye!")
        break
    response = model.generate_content(user_input)
    print("Chatbot:", response.text)  # AI ka response print karna
