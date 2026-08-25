from django.urls import path
from . import views
urlpatterns=[
 path("health",views.health),path("districts",views.districts_api),path("districts/",views.districts_api),
 path("districts/<str:name>",views.district_api),path("predict/",views.predict_api),path("predict/districts",views.predict_districts),
 path("predict/monthly",views.monthly_api),path("predict/metrics",views.metrics_api),path("evacuate/",views.evacuate_api),
 path("live/<str:name>",views.live_api),path("hazards/<str:name>",views.hazards_api),path("hazards/earthquakes",views.earthquake_api),path("hazards/fires",views.fire_api),path("hazards/sealevel",views.sealevel_api),path("alerts",views.alerts_api),path("chat",views.chat_api),
 path("auth/register",views.register_api),path("auth/login",views.login_api),path("auth/logout",views.logout_api),
 path("alerts/subscribe",views.subscribe_alerts_api),path("alerts/unsubscribe",views.unsubscribe_alerts_api),path("alerts/subscriptions",views.subscription_api),
]