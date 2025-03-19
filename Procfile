release: pip install alembic psycopg2-binary && cd api && alembic upgrade head
web: cd api && gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT --workers=2 --max-requests=1000
