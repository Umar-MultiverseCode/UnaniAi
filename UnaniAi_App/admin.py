from django.contrib import admin

from .models import UserChat

@admin.register(UserChat)
class UserChatAdmin(admin.ModelAdmin):
    list_display = ('user_message', 'bot_response', 'timestamp')
