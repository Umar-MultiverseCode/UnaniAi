from django.urls import path
from .views import index, chat_view, chatbot_response   

urlpatterns = [
    path('', index, name='index'),  # Home page
    path('chat/', chat_view, name='chat_view'),  # Chat page
    path('chatbot/', chatbot_response, name='chatbot_response'),  # API endpoint for chatbot
]
