# run.py
from infrastructure.logging import configure_logging, get_logger
from infrastructure.config import get_settings
from infrastructure.db import init_db
from workers.scheduler import start_scheduler
from app import create_app

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
log = get_logger(__name__)

app = create_app()

# Banco: em DEV podemos criar as tabelas automaticamente; em PROD use migrações.
init_db(create_all=(settings.FLASK_ENV == "development"))

# Scheduler só inicia se SCHEDULER=1 (checado dentro do próprio start_scheduler)
start_scheduler()

if __name__ == "__main__":
    app.run(debug=settings.DEBUG)
    log.info("DB URL: %s", settings.DATABASE_URL)

