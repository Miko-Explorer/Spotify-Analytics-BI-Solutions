"""Read-only analytics site. Production secrets live outside each release."""
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
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if host.strip()]
INSTALLED_APPS = ['django.contrib.staticfiles', 'analytics']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.middleware.common.CommonMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DW_DB_NAME', '2026_3dsa_2_spotifyanalytics'),
        'USER': os.getenv('DW_DB_USER', os.getenv('DB_USER', '')),
        'PASSWORD': os.getenv('DW_DB_PASSWORD', os.getenv('DB_PASSWORD', '')),
        'HOST': os.getenv('DW_DB_HOST', os.getenv('DB_HOST', '127.0.0.1')),
        'PORT': os.getenv('DW_DB_PORT', os.getenv('DB_PORT', '3306')),
        'OPTIONS': {'connect_timeout': 8, 'read_timeout': 90, 'write_timeout': 20, 'charset': 'utf8mb4'},
        'CONN_MAX_AGE': 0,
    }
}
DW_EXPECTED_SCHEMA = os.getenv('DW_EXPECTED_SCHEMA', DATABASES['default']['NAME'])
if os.getenv('DW_DB_SSL_CA'):
    DATABASES['default']['OPTIONS'].update({
        'ssl_ca': os.environ['DW_DB_SSL_CA'],
        'ssl_verify_cert': True,
        'ssl_verify_identity': True,
    })
STATIC_URL = '/static/'
STATIC_ROOT = Path(os.getenv('DJANGO_STATIC_ROOT', BASE_DIR / 'staticfiles'))
STATICFILES_DIRS = [BASE_DIR / 'static']
# Nginx must overwrite this header and bind Gunicorn only to loopback.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '0'))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'Asia/Manila'
