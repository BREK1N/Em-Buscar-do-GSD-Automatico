from django.contrib import admin
from .models import GrupoMaterial, SubgrupoMaterial, Material, Cautela, CautelaItem

# Register your models here.
admin.site.register(GrupoMaterial)
admin.site.register(SubgrupoMaterial)
admin.site.register(Material)
admin.site.register(Cautela)
admin.site.register(CautelaItem)