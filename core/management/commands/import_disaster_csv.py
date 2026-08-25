import csv
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import DisasterEvent, Shelter, Hospital

class Command(BaseCommand):
    help = 'Import bundled historical and static CSV data into the database.'
    def handle(self, *args, **kwargs):
        base = Path(settings.BASE_DIR) / 'data'
        mapping = [
            (base/'historical'/'historical_disasters.csv', DisasterEvent, ['date','disaster_type','district','state','latitude','longitude','rainfall_mm','temperature_c','humidity_pct','wind_speed_kmh','magnitude','affected_population','severity']),
            (base/'static'/'shelters.csv', Shelter, ['name','district','state','latitude','longitude','capacity','contact']),
            (base/'static'/'hospitals.csv', Hospital, ['name','district','state','latitude','longitude','emergency_available','contact']),
        ]
        for path, model, fields in mapping:
            count=0
            with path.open(encoding='utf-8', newline='') as f:
                for row in csv.DictReader(f):
                    data={k: row.get(k) for k in fields}
                    if model is DisasterEvent:
                        from datetime import date
                        data['date']=date.fromisoformat(data['date'])
                    if model is Hospital:
                        data['emergency_available']=str(data['emergency_available']).lower() in ('true','1','yes')
                    lookup={k:data[k] for k in ('name','district') if k in data}
                    if model is DisasterEvent: lookup={'date':data['date'],'disaster_type':data['disaster_type'],'district':data['district']}
                    model.objects.update_or_create(**lookup, defaults=data); count+=1
            self.stdout.write(self.style.SUCCESS(f'Imported {count} rows from {path.name}'))
