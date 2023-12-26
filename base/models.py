from django.db import models
from django.contrib.auth.models import User

class steganography(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_steg')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_Steg')
    image = models.ImageField(upload_to='originalImages/')
    message = models.TextField()
    dest = models.CharField(max_length=128)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    encoded_img = models.ImageField(null=True, blank=True, upload_to='stegoImages/')

    def __str__(self):
        return self.image

class UserRegistration(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email = models.CharField(max_length=128, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)





