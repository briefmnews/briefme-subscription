# briefme-subscription
[![Python 3.9](https://img.shields.io/badge/python-3.8|3.9-blue.svg)](https://www.python.org/downloads/release/python-390/) 
[![Django 2.2](https://img.shields.io/badge/django-2.2-blue.svg)](https://docs.djangoproject.com/en/2.2/)
[![Python CI](https://github.com/briefmnews/briefme-subscription/actions/workflows/workflow.yaml/badge.svg)](https://github.com/briefmnews/briefme-subscription/actions/workflows/workflow.yaml)
[![codecov](https://codecov.io/gh/briefmnews/briefme-subscription/branch/master/graph/badge.svg?token=7PPVF71G1F)](https://codecov.io/gh/briefmnews/briefme-subscription)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black) 

Base subscription app for Brief.me projects

## Installation
Intall with pip:
```shell script
pip install -e git://github.com/briefmnews/briefme-subscription.git@master#egg=briefme_subscription
```

## Setup
In order to make `briefme-subscription` works, you'll need to follow the steps below.

### Install app
```python
INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',

    'briefme_subscription',
    ...
)
```

### Mandatory Settings
Here is the list of all the mandatory settings with examples:
```python
TRIAL_DEFAULT_TOKEN = "default"
CHARGIFY_API_KEY = "dummy-key"
CHARGIFY_SITE = "dummy-site"
SUBSCRIPTION_PAYMENT_METHOD_CHOICES = (
    ("credit_card", "Carte bancaire"),
    ("paypal", "PayPal"),
)
```