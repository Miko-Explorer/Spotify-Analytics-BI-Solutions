"""Local, read-only analytics site. Connection credentials remain in the .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Pure-Python MySQL driver avoids blocked mysqlclient DLLs on managed Windows PCs.
import pymysql
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / '.env')
load_dotenv(BASE_DIR / '.env', override=False)
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if host.strip()]
INSTALLED_APPS = ['django.contrib.staticfiles', 'analytics']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.middleware.common.CommonMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DW_DB_NAME', 'spotify_analytics_dw'),
        'USER': os.getenv('DW_DB_USER', os.getenv('DB_USER', 'root')),
        'PASSWORD': os.getenv('DW_DB_PASSWORD', os.getenv('DB_PASSWORD', '')),
        'HOST': os.getenv('DW_DB_HOST', os.getenv('DB_HOST', '127.0.0.1')),
        'PORT': os.getenv('DW_DB_PORT', os.getenv('DB_PORT', '3306')),
        'OPTIONS': {'connect_timeout': 8, 'read_timeout': 90, 'write_timeout': 20, 'charset': 'utf8mb4'},
        'CONN_MAX_AGE': 0,
    }
}
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'Asia/Manila'
