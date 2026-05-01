from django.contrib import admin
from .models import CarouselSlide, Tutorial, TutorialImage, TutorialAttachment


class TutorialImageInline(admin.TabularInline):
    model = TutorialImage
    extra = 1
    fields = ['image', 'caption', 'order']


class TutorialAttachmentInline(admin.TabularInline):
    model = TutorialAttachment
    extra = 1
    fields = ['file', 'name', 'description']


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    inlines = [TutorialImageInline, TutorialAttachmentInline]
    list_display = ['title', 'author', 'category', 'published', 'created_at']
    list_filter = ['published', 'category']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CarouselSlide)
class CarouselSlideAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'active', 'created_at']
    list_editable = ['order', 'active']
    readonly_fields = ['created_at']
