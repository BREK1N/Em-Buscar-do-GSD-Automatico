from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile

# Define um inline admin descriptor para o UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil do Militar'

# Define um novo User admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

# Re-regista o User admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
