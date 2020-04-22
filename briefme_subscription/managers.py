from django.conf import settings
from django.db import models


class TrialCouponManager(models.Manager):
    def get_default(self):
        return self.get_queryset().get(token=settings.TRIAL_DEFAULT_TOKEN)
