from django.db import models


from django.db import models

class Signup(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)  # Store hashed passwords