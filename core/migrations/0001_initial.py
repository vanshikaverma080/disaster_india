from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
      migrations.CreateModel(name="Alert",fields=[
       ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
       ("district",models.CharField(max_length=160)),("state",models.CharField(blank=True,max_length=120)),
       ("hazard",models.CharField(max_length=40)),("level",models.CharField(max_length=20)),
       ("message",models.TextField()),("source",models.CharField(blank=True,max_length=300)),
       ("external_id",models.CharField(blank=True,max_length=200)),("created_at",models.DateTimeField(auto_now_add=True))],
       options={"ordering":["-created_at"]}),
      migrations.CreateModel(name="ChatMessage",fields=[
       ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
       ("message",models.TextField()),("response",models.TextField()),("created_at",models.DateTimeField(auto_now_add=True)),
       ("user",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL))])
    ]
