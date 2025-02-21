from django.urls import path
from .views import index, chat_view, chatbot_response, signup, login,logout

urlpatterns = [
    path('', index, name='index'),  # Home page
    path('chat/', chat_view, name='chat_view'),  # Chat page
    path('chatbot/', chatbot_response, name='chatbot_response'),  # API endpoint for chatbot
    path('signup/', signup, name='signup'),
    path('login/', login, name='login'),
     path('logout/', logout, name='logout'),
]
