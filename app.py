"""
WSGI entrypoint alias for platforms (e.g. Render/Heroku) defaulting to `app:app` or `app:application`.
"""
import os
from config.wsgi import application

app = application
