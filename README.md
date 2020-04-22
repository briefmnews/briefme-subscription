# briefme-subscription
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
Here is the list of all the mandatory settings:
```python
TRIAL_DEFAULT_TOKEN
```