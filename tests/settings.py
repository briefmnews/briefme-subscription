import sys
from unittest.mock import MagicMock

sys.modules["libs.chargify_python"] = MagicMock()
sys.modules["nonce.models"] = MagicMock()

SECRET_KEY = "dump-secret-key"

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.admin",
    "briefme_subscription",
    "tests",
    "briefme_test_user",
)

AUTH_USER_MODEL = "briefme_test_user.User"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "test",
        "USER": "briefme",
        "PASSWORD": "briefme",
        "HOST": "localhost",
    }
}

CHARGIFY_API_KEY = "dummy-key"
CHARGIFY_SITE = "dummy-site"
SUBSCRIPTION_PAYMENT_METHOD_CHOICES = (
    ("credit_card", "Carte bancaire"),
    ("paypal", "PayPal"),
)
