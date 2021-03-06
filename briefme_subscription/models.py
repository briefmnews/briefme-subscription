import calendar
import datetime

from dateutil.parser import parse
from decimal import Decimal, DecimalException

from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import models
from django.shortcuts import reverse

from model_utils.models import TimeStampedModel
from model_utils import Choices

from .chargify import ChargifyHelper
from .managers import TrialCouponManager

User = get_user_model()


class TrialCoupon(TimeStampedModel):
    number_of_days = models.PositiveIntegerField(
        verbose_name="Nombre de jours",
        help_text="Validité du coupon en nombre de jours",
        default=30,
    )
    expires_at = models.DateField(
        verbose_name="Date d'expiration du coupon",
        help_text="La date d'expiration est prioritaire sur le nombre de jours.",
        blank=True,
        null=True,
    )
    codename = models.SlugField(
        db_index=False,
        unique=True,
        verbose_name="Identifiant interne",
        help_text="Utilisé notamment dans les analytics",
    )
    token = models.SlugField(
        unique=True, verbose_name="Code promo", help_text="Exemple: BRIEF2020"
    )
    welcome_message = models.CharField(
        max_length=200,
        verbose_name="Message personnalisé accueil + e-mail",
        blank=True,
        null=True,
    )
    landing_message = models.CharField(
        max_length=200,
        verbose_name="Message personnalisé sur la page d'accueil",
        blank=True,
        null=True,
    )
    partner_label = models.CharField(
        max_length=200, verbose_name="Nom du partenaire", blank=True
    )

    objects = TrialCouponManager()

    class Meta:
        abstract = True
        verbose_name = "coupon d'essai"
        verbose_name_plural = "coupons d'essai"

    def __str__(self):
        return f"{self.codename} - {self.token} - {self.number_of_days} jours"

    @property
    def duration(self):
        if self.expires_at:
            delta_days = (self.expires_at - datetime.date.today()).days
            duration = delta_days if delta_days >= 0 else 0
        else:
            duration = self.number_of_days

        return duration


###################################################################################################
# Field post-process functions                                                                    #
###################################################################################################
def parse_date(string):
    try:
        return parse(string)
    except (TypeError, ValueError):
        return ""


def expiration_last_day(credit_card):
    expiration_year = int(credit_card["expiration_year"])
    expiration_month = int(credit_card["expiration_month"])

    last_day = calendar.monthrange(expiration_year, expiration_month)[1]
    return datetime.date(expiration_year, expiration_month, last_day)


def convert_price(price):
    try:
        return Decimal(price) / 100
    except (DecimalException, TypeError):
        return Decimal("0")


def lower(string):
    return string.lower()


###################################################################################################
# End field post-process functions                                                                #
###################################################################################################


class ChargifySubscription(TimeStampedModel):
    """
    Subscription model build upon Chargify API & online services.
    """

    # Should be "id" but conflicts with Django's "pk", so we use "uuid" even
    # though it is not a real UUID value but an integer.
    uuid = models.PositiveIntegerField(unique=True)
    chargify_subscription_cache = JSONField(default=dict, blank=True)
    hold_start_date = models.DateField("Date de suspension", null=True, blank=True)
    hold_end_date = models.DateField("Date de reprise", null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    chargify_helper = ChargifyHelper()

    class Meta:
        abstract = True

    def __getattribute__(self, item):
        try:
            return super().__getattribute__(item)
        except AttributeError as e:
            try:
                return getattr(self.chargify_subscription, item)
            except AttributeError:
                raise e

    def __str__(self):
        if self.trialing:
            value = "{state} - date de fin: {end} - coupon: {coupon}".format(
                state=self.state,
                end=self.trial_ended_at.strftime("%d/%m/%Y"),
                coupon=self.trial_coupon.codename,
            )
        else:
            value = "{state} - ID: {id}".format(state=self.state, id=self.uuid)
        return value

    @property
    def chargify_subscription(self):
        if not self.chargify_subscription_cache:
            # load the subscription and copy to cache
            self.refresh_chargify_subscription_cache()
        chargify_proxy = self.ChargifyProxy(self.chargify_subscription_cache)
        return chargify_proxy

    @property
    def STATES(self):
        args = self.chargify_helper.STATES
        return Choices(*args)

    @staticmethod
    def count_days_from_now(to_date):
        try:
            to_date = to_date.replace(tzinfo=None)
        except (AttributeError, TypeError):
            return 0
        from_date = datetime.datetime.now()

        if not to_date or to_date <= from_date:
            return 0
        delta = to_date - from_date
        return delta.days

    @property
    def remaining_trial_days(self):
        """Get the number of days before the end of the trial"""
        try:
            return self.count_days_from_now(self.trial_ended_at)
        except AttributeError:
            return 0

    @property
    def remaining_days_in_current_period(self):
        """Get the number of days before the end of the current period"""
        try:
            return self.count_days_from_now(self.current_period_ends_at)
        except AttributeError:
            return 0

    @property
    def remaining_days(self):
        """Get the number of days before next change in subscription"""
        if self.trialing or self.trial_ended:
            return self.remaining_trial_days
        else:
            return self.remaining_days_in_current_period

    @property
    def active(self):
        return self.state == self.STATES.active

    @property
    def trialing(self):
        return self.state == self.STATES.trialing

    @property
    def trial_ended(self):
        """To check if the status is trial ended

        @return: The state trial ended
        @rtype : bool
        """
        return self.state == self.STATES.trial_ended

    @property
    def canceled(self):
        return self.state == self.STATES.canceled

    @property
    def on_hold(self):
        """To check if the status is on hold

        @return: The state on hold
        @rtype : bool
        """
        return self.state == self.STATES.on_hold

    @property
    def past_due(self):
        """To check if the status is past due

        @return: The state is past due
        @rtype : bool
        """
        return self.state == self.STATES.past_due

    @property
    def running(self):
        return self.state in (self.STATES.trialing, self.STATES.active, self.STATES.past_due)

    @property
    def pending_cancellation(self):
        return self.chargify_subscription.pending_cancellation or False

    @property
    def plan_type_name(self):
        """To get the plan type name.

        @return:  Name of the plan
        @rtype :  str
        """

        if self.converted:
            length = self.plan_interval_length
            unit = self.plan_interval_unit

            if unit == "month" and length == 1:
                return "monthly"
            elif unit == "month" and length == 12:
                return "yearly"

        return ""

    @property
    def credit_card_is_active(self):
        try:
            in_35_days = datetime.date.today() + datetime.timedelta(days=35)
            return self.credit_card_expiration_date > in_35_days
        except (ValueError, TypeError, AttributeError):
            # Let's assume the credit card has expired then
            return False

    def refresh_chargify_subscription_cache(self, chargify_subscription=None):
        self.chargify_subscription_cache = (
            chargify_subscription
            or self.chargify_helper.get_subscription(self.uuid)
            or {}
        )
        if not self.chargify_subscription_cache:
            self.chargify_subscription_cache = {}
        self.save()

    def clear_chargify_subscription_cache(self):
        self.chargify_subscription_cache = {}
        self.save()

    def reactivate(self, include_trial=False, send_event=True):
        previous_state = self.state
        # include_trial should be set to 0 or 1
        include_trial = 1 if include_trial else 0
        response = self.chargify_helper.reactivate_subscription(
            subscription_id=self.uuid, include_trial=include_trial
        )
        self.refresh_chargify_subscription_cache(
            chargify_subscription=response["subscription"]
        )

        if send_event and previous_state != self.STATES.trial_ended:
            self.track_reactivate_event()

    def delete_payment_profile(self, payment_profile_id):
        self.chargify_helper.delete_payment_profile(self.uuid, payment_profile_id)

    def track_conversion_event(self, additional_properties=None):
        pass

    def track_reactivate_event(self, additional_properties=None):
        pass

    def generate_confirmation_url(self):
        token = signing.dumps(self.pk, salt="account-validation")
        path = reverse("validate-account", args=(token,))

        return "{domain}{path}".format(domain=settings.SITE_DOMAIN, path=path)

    class ChargifyProxy:

        attribute_lookup = {
            "balance": ("balance_in_cents", convert_price),
            "canceled_at": ("canceled_at", parse_date),
            "coupon_code": "coupon_code",
            "credit_card": "credit_card",
            "credit_card_expiration_date": ("credit_card", expiration_last_day),
            "credit_card_masked_card_number": "credit_card__masked_card_number",
            "current_billing_amount": (
                "current_billing_amount_in_cents",
                convert_price,
            ),
            "current_billing_amount_in_cents": "current_billing_amount_in_cents",
            "current_period_ends_at": ("current_period_ends_at", parse_date),
            "customer": "customer",
            "next_assessment_at": ("next_assessment_at", parse_date),
            "next_product_id": "next_product_id",
            "next_product_handle": "next_product_handle",
            "payment_collection_method": "payment_collection_method",
            "payment_type": "payment_type",
            "paypal_account": "paypal_account",
            "paypal_email": "paypal_account__paypal_email",
            "pending_cancellation": "cancel_at_end_of_period",
            "product": "product",
            "product_handle": "product__handle",
            "product_price": ("product__price_in_cents", convert_price),
            "state": "state",
            "trial_ended_at": ("trial_ended_at", parse_date),
            "plan_interval_unit": "product__interval_unit",
            "plan_interval_length": "product__interval",
            "plan_name": ("product__name", lower),
            "plan_handle": ("product__handle", lower),
            "total_revenue": ("total_revenue_in_cents", convert_price),
        }

        def __init__(self, chargify_subscription):
            self._chargify_subscription = chargify_subscription

        def __getattribute__(self, item):
            try:
                return super().__getattribute__(item)
            except AttributeError as e:
                if item in self.attribute_lookup:
                    lookup = self.attribute_lookup[item]
                    if isinstance(lookup, str):
                        return self._get_value_from_dict(
                            lookup, self._chargify_subscription
                        )
                    elif isinstance(lookup, tuple):
                        value = self._get_value_from_dict(
                            lookup[0], self._chargify_subscription
                        )
                        if callable(lookup[1]):
                            value = lookup[1](value)
                        return value
                else:
                    raise e

        @staticmethod
        def _get_value_from_dict(key, subscription):
            keys = key.split("__")
            value = subscription
            try:
                for key in keys:
                    value = value.get(key)
                return value if value is not None else ""
            except AttributeError:
                return ""
