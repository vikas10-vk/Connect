import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\Capstone\Intership_main\hipages\.env", override=True)

SECRET_KEY = os.getenv('SECRET_KEY', 'django-admin-secret-key')
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

def _parse_db_url(url: str) -> dict:
    """Parse postgresql://user:pass@host:port/dbname into Django DB dict."""
    if not url:
        return {}
    # Strip driver prefix
    url = url.replace('postgresql://', '').replace('postgres://', '')
    # user:pass@host:port/dbname
    user_pass, rest = url.split('@')
    user, password = user_pass.split(':')
    host_port, name = rest.split('/')
    if ':' in host_port:
        host, port = host_port.split(':')
    else:
        host, port = host_port, '5432'
    return {'NAME': name, 'USER': user, 'PASSWORD': password, 'HOST': host, 'PORT': port}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'options': '-c search_path=public',
        },
        **_parse_db_url(os.getenv('SYNC_DATABASE_URL', ''))
    }
}

STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'