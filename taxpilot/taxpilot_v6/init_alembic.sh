#!/bin/bash
# Run this script to initialize Alembic migrations
# Usage: ./init_alembic.sh

echo "Initializing Alembic migrations..."

# Initialize alembic
alembic init migrations

# Update alembic.ini with your database URL
# For SQLite (dev): sqlalchemy.url = sqlite:///./taxpilot.db
# For MySQL (prod): sqlalchemy.url = mysql+pymysql://taxpilot:taxpilot123@mysql:3306/taxpilot

# Update env.py to import your models
# Add to env.py:
# from app.database import Base
# from app.models.models import *
# target_metadata = Base.metadata

echo "Alembic initialized. Next steps:"
echo "1. Edit alembic.ini with your database URL"
echo "2. Edit migrations/env.py to import Base and models"
echo "3. Run: alembic revision --autogenerate -m 'initial migration'"
echo "4. Run: alembic upgrade head"
