import uuid
from django.db import models
class ChatMessage(models.Model):
    user=models.ForeignKey("auth.User",null=True,blank=True,on_delete=models.SET_NULL)
    message=models.TextField()
    response=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
class Alert(models.Model):
    district=models.CharField(max_length=160)
    state=models.CharField(max_length=120,blank=True)
    hazard=models.CharField(max_length=40)
    level=models.CharField(max_length=20)
    message=models.TextField()
    source=models.CharField(max_length=300,blank=True)
    external_id=models.CharField(max_length=200,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=["-created_at"]


class AlertSubscription(models.Model):
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.CASCADE, related_name="alert_subscriptions")
    email = models.EmailField()
    district = models.CharField(max_length=160, blank=True)
    hazards = models.JSONField(default=list)
    threshold = models.FloatField(default=0.75)
    active = models.BooleanField(default=True)
    unsubscribe_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    last_alert_key = models.CharField(max_length=255, blank=True)
    last_alert_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["email", "active"])]

    def __str__(self):
        return f"{self.email} · {self.district or 'all districts'}"

class DisasterEvent(models.Model):
    date=models.DateField()
    disaster_type=models.CharField(max_length=50)
    district=models.CharField(max_length=160)
    state=models.CharField(max_length=120, blank=True)
    latitude=models.FloatField()
    longitude=models.FloatField()
    rainfall_mm=models.FloatField(default=0)
    temperature_c=models.FloatField(default=0)
    humidity_pct=models.FloatField(default=0)
    wind_speed_kmh=models.FloatField(default=0)
    magnitude=models.FloatField(default=0)
    affected_population=models.PositiveIntegerField(default=0)
    severity=models.CharField(max_length=20)
    class Meta:
        indexes=[models.Index(fields=['disaster_type','district']), models.Index(fields=['date'])]

class Shelter(models.Model):
    name=models.CharField(max_length=200)
    district=models.CharField(max_length=160)
    state=models.CharField(max_length=120, blank=True)
    latitude=models.FloatField(); longitude=models.FloatField()
    capacity=models.PositiveIntegerField(default=0)
    contact=models.CharField(max_length=50, blank=True)
    class Meta: unique_together=[('name','district')]

class Hospital(models.Model):
    name=models.CharField(max_length=200)
    district=models.CharField(max_length=160)
    state=models.CharField(max_length=120, blank=True)
    latitude=models.FloatField(); longitude=models.FloatField()
    emergency_available=models.BooleanField(default=True)
    contact=models.CharField(max_length=50, blank=True)
    class Meta: unique_together=[('name','district')]
