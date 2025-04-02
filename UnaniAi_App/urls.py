from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    index, 
    chat_view, 
    chatbot_response, 
    signup, 
    login,
    logout,
    emergency_assistance,
    add_medicine_reminder,
    medicine_reminders,
    send_medicine_reminders
)

urlpatterns = [
    # Main application URLs
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

    # Password reset URLs
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='login.html',
             extra_context={'reset_form': True},
             email_template_name='password_reset_email.html',
             subject_template_name='password_reset_subject.txt'
         ),
         name='password_reset'),
         
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='login.html',
             extra_context={'reset_done': True}
         ),
         name='password_reset_done'),
         
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='login.html',
             extra_context={'reset_confirm': True}
         ),
         name='password_reset_confirm'),
         
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='login.html',
             extra_context={'reset_complete': True}
         ),
         name='password_reset_complete'),
]