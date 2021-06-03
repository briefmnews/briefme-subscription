import factory

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import ChargifySubscription, TrialCoupon

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    email = factory.Sequence(lambda n: "john.doe{0}@brief.me".format(n))
    password = factory.PostGenerationMethodCall("set_password", "briefme")
    first_name = "John"
    last_name = "Doe"
    city = "Paris"
    country = "FR"
    expertise = "geek"
    last_login = timezone.now()
    is_staff = False

    class Meta:
        model = User


class TrialCouponFactory(factory.django.DjangoModelFactory):
    number_of_days = 15
    codename = factory.Sequence(lambda n: f"codename_{n}")
    token = factory.Sequence(lambda n: f"token_{n}")

    class Meta:
        model = TrialCoupon


class ChargifySubscriptionFactory(factory.django.DjangoModelFactory):
    uuid = factory.Sequence(lambda n: n)
    user = factory.SubFactory(UserFactory)
    trial_coupon = factory.SubFactory(TrialCouponFactory)
    chargify_subscription_cache = {"dummy": "dummy"}

    class Meta:
        model = ChargifySubscription

