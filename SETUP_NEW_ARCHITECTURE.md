# Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Create database migrations:
   `python manage.py makemigrations core`
4. Apply migrations:
   `python manage.py migrate`
5. Import CSV data:
   `python manage.py import_disaster_csv`
6. Start the server:
   `python manage.py runserver`

The project includes historical and static CSV files. The import command loads them into `DisasterEvent`, `Shelter`, and `Hospital` database tables.
