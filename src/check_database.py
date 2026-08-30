import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError("DATABASE_URL was not found in the .env file.")

with psycopg.connect(database_url) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT current_database(), current_user
            """
        )

        database_name, database_user = cursor.fetchone()

print("Python connected to PostgreSQL")
print(f"Database: {database_name}")
print(f"User: {database_user}")