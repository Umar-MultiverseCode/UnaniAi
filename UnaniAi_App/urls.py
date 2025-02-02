from django.urls import path
from .views import index, chat_view

urlpatterns = [
    path('', index, name='index'),  # Home page
     path('chat/', chat_view, name='chat_view'),  # Chat page
]
