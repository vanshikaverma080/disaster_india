from django.contrib import admin
from .models import Alert, ChatMessage, AlertSubscription

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display=("district","hazard","level","source","created_at")
    list_filter=("hazard","level","source")
    search_fields=("district","message")

@admin.register(AlertSubscription)
class AlertSubscriptionAdmin(admin.ModelAdmin):
    list_display=("email","district","threshold","active","created_at","last_alert_at")
    list_filter=("active","threshold")
    search_fields=("email","district")
    readonly_fields=("unsubscribe_token","last_alert_key","last_alert_at")

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display=("user","created_at")
    search_fields=("message","response")
from .models import DisasterEvent, Shelter, Hospital
admin.site.register(DisasterEvent)
admin.site.register(Shelter)
admin.site.register(Hospital)
