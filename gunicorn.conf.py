# gunicorn.conf.py

bind = "0.0.0.0:5000"

workers = 4
worker_class = "sync"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
timeout = 60
