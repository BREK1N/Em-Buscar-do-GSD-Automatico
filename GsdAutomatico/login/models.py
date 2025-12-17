from django.db import models
from django.contrib.auth.models import User
from Secao_pessoal.models import Efetivo
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Garantir que a associação com um militar é opcional
    militar = models.OneToOneField(Efetivo, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.username

# Estes "sinais" garantem que um UserProfile é criado automaticamente
# sempre que um novo User é criado (por exemplo, através do createsuperuser).
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
