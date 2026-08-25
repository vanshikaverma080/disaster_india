import os
import time
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import ChatMessage, AlertSubscription, DisasterEvent, Shelter, Hospital
from .services import districts,district,predict,route,live_weather,monthly,news_alerts,live_earthquakes,live_fires,live_sealevel,hazard_snapshot
import json,requests


def _client_ip(req):
    forwarded = req.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0] or req.META.get("REMOTE_ADDR") or "unknown").strip()


def _rate_limited(req, bucket, limit, seconds=60):
    key = f"rate:{bucket}:{_client_ip(req)}"
    now = time.time()
    hits = [x for x in (cache.get(key) or []) if now - x < seconds]
    if len(hits) >= limit:
        cache.set(key, hits, seconds)
        return True
    hits.append(now)
    cache.set(key, hits, seconds)
    return False


def body(req): 
    try:return json.loads(req.body or "{}")
    except:return {}
def health(req):return JsonResponse({"status":"ok","service":"ClimateGuard Django","live_weather":bool(os.getenv("OPENWEATHER_API_KEY"))})
def districts_api(req):return JsonResponse({"districts":districts()})
def district_api(req,name):
    d=district(name)
    return JsonResponse(d or {"error":"District not found"},status=200 if d else 404)
@csrf_exempt
def predict_api(req):
    if req.method!="POST":return JsonResponse({"error":"POST required"},status=405)
    try:return JsonResponse(predict(body(req)))
    except Exception as e:return JsonResponse({"error":str(e)},status=500)
def predict_districts(req):return JsonResponse({"districts":[d["name"] for d in districts()]})
@csrf_exempt
def monthly_api(req):
    b=body(req);return JsonResponse(monthly(b.get("district","Patna"), b.get("hazard","flood")))
def metrics_api(req):return JsonResponse({"model":"Random Forest + Gradient Boosting ensemble","status":"uses generated normal-day samples plus bundled historical disaster events; live weather can be injected into predictions","data_files":True,"live_apis":["Open-Meteo","OpenWeather (optional)","USGS Earthquakes","NASA FIRMS (key)","Stormglass Sea Level (key)","NewsAPI (optional)","Gemini (optional)"]})
@csrf_exempt
def evacuate_api(req):
    b=body(req);r=route(b.get("origin_district",""),b.get("disaster_type","flood"),b.get("destination_district"))
    return JsonResponse(r,status=200 if "error" not in r else 400)
def live_api(req,name):
    try:return JsonResponse(live_weather(name))
    except Exception as e:return JsonResponse({"error":f"Live weather unavailable: {e}"},status=503)
def alerts_api(req):
    alerts=news_alerts()
    if not alerts:
        for d in districts():
            for h,r in d["risks"].items():
                driver=d.get("risk_drivers",{}).get(h,"district risk profile")
                if r>=.75:alerts.append({"level":"CRITICAL","district":d["name"],"hazard":h,"message":f"{h.title()} risk is {(r*100):.0f}%: {driver}. Review dashboard details, prepare essentials, and follow official authority guidance if conditions worsen.","source":"ClimateGuard model"})
                elif r>=.55:alerts.append({"level":"HIGH","district":d["name"],"hazard":h,"message":f"{h.title()} risk is {(r*100):.0f}%: {driver}. Monitor local updates and keep emergency contacts and travel plans ready.","source":"ClimateGuard model"})
    return JsonResponse({"alerts":alerts[:50]})

def local_chat_response(msg, selected_district=""):
    q = msg.lower()
    district_name = (selected_district or "").strip()
    matched_district = district(district_name) if district_name else None

    if not matched_district:
        for item in districts():
            name = item.get("name", "")
            if name and name.lower() in q:
                matched_district = item
                break

    if any(x in q for x in ["hi", "hello", "hey"]):
        return "Hi, I am ClimateGuard AI. Ask me about district risk, flood prediction, alerts, live weather, or evacuation routes.", "ClimateGuard"

    if any(x in q for x in ["evac", "route", "shelter", "safe place", "escape"]):
        return "Use the Evacuate page to choose an origin district and hazard. ClimateGuard can auto-select a nearby shelter or safe point, then estimate a safer route using district risk levels. In a real emergency, follow local authority and NDMA instructions.", "ClimateGuard"

    if any(x in q for x in ["weather", "rain", "temperature", "wind", "humidity"]):
        return "Use Dashboard -> Live weather for current district conditions. Flood risk is most sensitive to rainfall, river level, elevation, month, and local historical flood context.", "ClimateGuard"

    if any(x in q for x in ["alert", "warning", "notify", "subscription", "email"]):
        return "The Alerts panel lists high and critical hazard signals. With an account, you can save email subscriptions by district, hazard type, and threshold from the Account button.", "ClimateGuard"

    if any(x in q for x in ["predict", "prediction", "probability", "risk score", "model", "ml"]):
        return "The Predict page runs the flood ML model for flood questions and shows monthly signals for earthquake, fire, and sea-level hazards. The score is decision support only, not an official warning.", "ClimateGuard"

    if any(x in q for x in ["flood", "river", "waterlogging"]):
        return "For flood risk, check rainfall, river level, elevation, live weather, and the monthly signal. If risk is high, prepare documents, medicines, power backup, drinking water, and a route to a safer local shelter.", "ClimateGuard"

    if any(x in q for x in ["earthquake", "quake", "magnitude"]):
        return "For earthquakes, use the Dashboard earthquake filter and live feed. During shaking: drop, cover, and hold on; after shaking stops, move away from damaged buildings and follow official instructions.", "ClimateGuard"

    if any(x in q for x in ["fire", "wildfire", "heat", "smoke"]):
        return "For fire risk, use the Fire hazard filter and check live fire detections where configured. Avoid smoke exposure, keep evacuation bags ready, and follow local fire and disaster management guidance.", "ClimateGuard"

    if any(x in q for x in ["sea", "coast", "cyclone", "storm surge", "sealevel", "sea level"]):
        return "For coastal and sea-level risk, check the Sea Level hazard filter and monthly signal. Coastal users should watch IMD, INCOIS, NDMA, and local authority updates during cyclone or surge conditions.", "ClimateGuard"

    if any(x in q for x in ["emergency", "help", "what should i do", "danger", "now"]):
        return "If there is immediate danger, call local emergency services and follow official evacuation orders. Use ClimateGuard only as planning support: check nearby shelters, avoid high-risk routes, and keep family contacts reachable.", "ClimateGuard"

    if matched_district:
        risks = matched_district.get("risks", {})
        top = sorted(risks.items(), key=lambda x: x[1], reverse=True)[:2]
        summary = ", ".join(f"{hazard} {(score*100):.0f}%" for hazard, score in top)
        return f"{matched_district['name']} currently shows strongest modeled signals for {summary}. Open Dashboard, select the hazard filter, then click the district for risk drivers and live context.", "ClimateGuard"

    return "I can answer ClimateGuard questions about district hazard risk, flood prediction inputs, alerts, live weather, and evacuation routing. Try asking about a hazard or district, for example: flood risk in Patna, how alerts work, or safest route from Delhi.", "ClimateGuard"

def openrouter_chat_response(msg, selected_district=""):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None

    model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-32b")
    site_url = os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8000")
    site_name = os.getenv("OPENROUTER_SITE_NAME", "ClimateGuard India")
    district_context = f" Selected district: {selected_district}." if selected_district else ""
    system_prompt = (
        "You are ClimateGuard AI, a concise disaster decision-support assistant for India. "
        "Help users understand flood prediction, hazard alerts, live weather, evacuation routing, "
        "and district risk signals. Do not claim to issue official warnings. Always advise users "
        "to follow NDMA, IMD, and local authorities during emergencies."
        + district_context
    )
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": site_url,
        "X-OpenRouter-Title": site_name,
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": msg},
        ],
    }
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=settings.CHAT_TIMEOUT_SECONDS,
    )
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"].strip()
    return text, f"OpenRouter · {model}"

@csrf_exempt
def chat_api(req):
    if _rate_limited(req, "chat", settings.CHAT_RATE_LIMIT_PER_MINUTE):
        return JsonResponse({"error":"Too many chat messages. Please wait a minute and try again."}, status=429)
    b=body(req);msg=(b.get("message") or "").strip()
    if not msg:return JsonResponse({"response":"Please enter a question."})
    try:
        ai_response = openrouter_chat_response(msg, b.get("district") or "")
        if ai_response:
            text, source = ai_response
            ChatMessage.objects.create(user=req.user if req.user.is_authenticated else None,message=msg,response=text)
            return JsonResponse({"response":text,"source":source})
    except Exception:
        pass
    text, source = local_chat_response(msg, b.get("district") or "")
    return JsonResponse({"response": text, "source": source})
@csrf_exempt
def register_api(req):
    if req.method != "POST":
        return JsonResponse({"error":"POST required"}, status=405)
    b=body(req);u=(b.get("username") or "").strip();p=b.get("password") or "";email=(b.get("email") or "").strip().lower()
    if len(u)<3 or len(p)<6 or "@" not in email:
        return JsonResponse({"error":"Username (3+), password (6+), and a valid email are required."},status=400)
    if User.objects.filter(username__iexact=u).exists():
        return JsonResponse({"error":"Username already exists"},status=409)
    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"error":"Email already registered"},status=409)
    user=User.objects.create_user(username=u,password=p,email=email);login(req,user)
    return JsonResponse({"ok":True,"username":u,"email":email})
@csrf_exempt
def login_api(req):
    b=body(req);user=authenticate(username=b.get("username",""),password=b.get("password",""))
    if not user:return JsonResponse({"error":"Invalid credentials"},status=401)
    login(req,user);return JsonResponse({"ok":True,"username":user.username})
def logout_api(req):logout(req);return JsonResponse({"ok":True})

def resources_api(req):
    district=(req.GET.get("district") or "").strip()
    shelters=Shelter.objects.all(); hospitals=Hospital.objects.all()
    if district:
        shelters=shelters.filter(district__iexact=district); hospitals=hospitals.filter(district__iexact=district)
    return JsonResponse({"shelters":[{"name":x.name,"district":x.district,"state":x.state,"latitude":x.latitude,"longitude":x.longitude,"capacity":x.capacity,"contact":x.contact} for x in shelters],"hospitals":[{"name":x.name,"district":x.district,"state":x.state,"latitude":x.latitude,"longitude":x.longitude,"emergency_available":x.emergency_available,"contact":x.contact} for x in hospitals]})

def history_api(req):
    qs=DisasterEvent.objects.all().order_by("-date")
    district=(req.GET.get("district") or "").strip(); dtype=(req.GET.get("type") or "").strip()
    if district: qs=qs.filter(district__iexact=district)
    if dtype: qs=qs.filter(disaster_type__iexact=dtype)
    rows=list(qs[:500].values("date","disaster_type","district","state","latitude","longitude","rainfall_mm","temperature_c","humidity_pct","wind_speed_kmh","magnitude","affected_population","severity"))
    for r in rows: r["date"]=r["date"].isoformat()
    return JsonResponse({"count":len(rows),"events":rows})

def earthquake_api(req):
    try:
        return JsonResponse(live_earthquakes(float(req.GET.get("lat",20)), float(req.GET.get("lng",78)), float(req.GET.get("radius_km",1200))))
    except Exception as e: return JsonResponse({"error":str(e)},status=503)

def fire_api(req):
    try:
        return JsonResponse(live_fires(float(req.GET.get("lat",20)), float(req.GET.get("lng",78)), int(req.GET.get("days",1)), float(req.GET.get("radius_deg",10))))
    except Exception as e: return JsonResponse({"error":str(e)},status=503)

def sealevel_api(req):
    try:
        return JsonResponse(live_sealevel(float(req.GET.get("lat",20)), float(req.GET.get("lng",78))))
    except Exception as e: return JsonResponse({"error":str(e)},status=503)

def hazards_api(req,name):
    try:
        x=hazard_snapshot(name)
        return JsonResponse(x or {"error":"District not found"},status=200 if x else 404)
    except Exception as e: return JsonResponse({"error":str(e)},status=503)


@csrf_exempt
@require_http_methods(["POST"])
def subscribe_alerts_api(req):
    b=body(req)
    email=(b.get("email") or "").strip().lower()
    if "@" not in email:
        return JsonResponse({"error":"A valid email address is required."}, status=400)
    district=(b.get("district") or "").strip()
    hazards=b.get("hazards") or ["flood","earthquake","fire","sealevel"]
    allowed={"flood","earthquake","fire","sealevel"}
    hazards=[h for h in hazards if h in allowed]
    if not hazards:
        return JsonResponse({"error":"Select at least one hazard."}, status=400)
    try: threshold=float(b.get("threshold",0.75))
    except: threshold=.75
    threshold=min(.95,max(.30,threshold))
    sub=AlertSubscription.objects.filter(email=email, district=district).first()
    if sub:
        sub.hazards=hazards; sub.threshold=threshold; sub.active=True;
        if req.user.is_authenticated: sub.user=req.user
        sub.save()
    else:
        sub=AlertSubscription.objects.create(email=email,district=district,hazards=hazards,threshold=threshold,user=req.user if req.user.is_authenticated else None)
    return JsonResponse({"ok":True,"email":sub.email,"district":sub.district or "All districts",
                         "hazards":sub.hazards,"threshold":sub.threshold,
                         "unsubscribe_token":str(sub.unsubscribe_token),
                         "message":"Subscription saved. Alerts are sent when a live hazard reaches your threshold."})

@csrf_exempt
@require_http_methods(["GET", "POST"])
def unsubscribe_alerts_api(req):
    b=body(req); token=b.get("token") or req.GET.get("token")
    if not token:
        if req.method == "GET":
            return HttpResponse("Unsubscribe token required.", status=400)
        return JsonResponse({"error":"Unsubscribe token required."}, status=400)
    try:
        sub=AlertSubscription.objects.get(unsubscribe_token=token)
    except AlertSubscription.DoesNotExist:
        if req.method == "GET":
            return HttpResponse("Subscription not found.", status=404)
        return JsonResponse({"error":"Subscription not found."}, status=404)
    sub.active=False; sub.save(update_fields=["active","updated_at"])
    if req.method == "GET":
        return HttpResponse("ClimateGuard email alerts unsubscribed successfully.")
    return JsonResponse({"ok":True,"message":"Email alerts unsubscribed."})

def subscription_api(req):
    email=(req.GET.get("email") or "").strip().lower()
    if req.user.is_authenticated:
        rows=AlertSubscription.objects.filter(user=req.user, active=True)
    elif email:
        rows=AlertSubscription.objects.filter(email=email,active=True)
    else:
        return JsonResponse({"error":"Login or email required."},status=400)
    return JsonResponse({"subscriptions":[{"id":x.id,"email":x.email,"district":x.district or "All districts","hazards":x.hazards,"threshold":x.threshold} for x in rows]})
