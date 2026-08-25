from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('core','0002_alertsubscription')]
    operations=[migrations.AddField(model_name='alertsubscription',name='user',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name='alert_subscriptions',to=settings.AUTH_USER_MODEL))]
