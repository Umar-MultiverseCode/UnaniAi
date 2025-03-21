from django.urls import path
from .views import index, chat_view, chatbot_response, signup, login, logout, emergency_assistance, add_medicine_reminder, medicine_reminders, send_medicine_reminders

urlpatterns = [
    path('', index, name='index'),
    path('chat/', chat_view, name='chat_view'),
    path('chatbot/', chatbot_response, name='chatbot_response'),
    path('signup/', signup, name='signup'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('emergency_assistance/', emergency_assistance, name='emergency_assistance'),
    path('add_medicine_reminder/', add_medicine_reminder, name='add_medicine_reminder'),
    path('medicine_reminders/', medicine_reminders, name='medicine_reminders'),
    path('send_medicine_reminders/', send_medicine_reminders, name='send_medicine_reminders'),
]