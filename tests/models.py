from django.db import models

from briefme_subscription.models import TrialCoupon as AbstractTrialCoupon
from briefme_subscription.models import ChargifySubscription as AbstractChargifySubscription


class TrialCoupon(AbstractTrialCoupon):
    pass


class ChargifySubscription(AbstractChargifySubscription):
    trial_coupon = models.ForeignKey(TrialCoupon, null=True, blank=True, on_delete=models.CASCADE)
