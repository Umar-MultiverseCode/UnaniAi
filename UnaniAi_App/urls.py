from django.urls import path
from .views import index, chat_view , get_response

urlpatterns = [
    path('', index, name='index'),  # Home page
    path('chat/', chat_view, name='chat_view'),
    path('get_response/', get_response, name='get_response'),  # Chat page
]
