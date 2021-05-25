import analytics
import logging

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .chargify import ChargifyHelper, ChargifyUnprocessableEntityError

logger = logging.getLogger(__name__)
User = get_user_model()


class ChargifyUpdateCustomerForm(forms.ModelForm):
    payment_method = forms.ChoiceField(
        label="Je choisis mon mode de paiement",
        choices=settings.SUBSCRIPTION_PAYMENT_METHOD_CHOICES,
        required=False,
        widget=forms.RadioSelect,
        initial="credit_card",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.Meta.fields:
            self.fields[field].required = True

    class Meta:
        model = User
        fields = ("first_name", "last_name", "payment_method", "country", "zip")


class ChargifyJsPaymentForm(forms.Form):
    """
    Chargify `form.Form` that implements a token field for Chargify.js for credit card or PayPal
    """

    chargify_token = forms.CharField(widget=forms.HiddenInput())
    country = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"data-chargify": "country"}),
    )
    zip = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"data-chargify": "zip"}),
    )

    def __init__(self, request, current_subscription, payment_method, *args, **kwargs):
        self.request = request
        self.current_subscription = current_subscription
        self.payment_method = payment_method
        super().__init__(*args, **kwargs)

    def is_valid(self):
        is_valid = super().is_valid()

        self._create_payment_profile()

        current_state = self.current_subscription.state

        if is_valid and current_state in ["trial_ended", "canceled"]:
            is_valid = self._reactivate_subscription()

        return is_valid

    def _create_payment_profile(self):
        ChargifyHelper().create_default_payment_profile_from_token(
            self.current_subscription, self.cleaned_data["chargify_token"]
        )
        self.current_subscription.payment_collection_method = "automatic"

    def _reactivate_subscription(self):
        current_subscription = self.current_subscription
        try:
            current_subscription.reactivate()
        except ChargifyUnprocessableEntityError as e:
            current_subscription.refresh_chargify_subscription_cache()

            self._track_reactivate_error()

            logger.warning(
                f"The subscription {current_subscription.uuid} couldn't be reactivated with error: {e}"
            )

            self._message_reactivate_error()

            return False

        return True

    def _track_reactivate_error(self):
        user = self.request.user
        current_subscription = self.current_subscription
        now = timezone.now()

        if self.payment_method == "paypal":
            label = "Paypal payment failed"
            analytics_data = {
                "date": now.strftime("%d/%m/%Y"),
                "paypal_account_email": current_subscription.paypal_account[
                    "paypal_email"
                ],
                "plan_label": current_subscription.plan_name,
            }
        else:
            label = "Credit card payment failed"
            credit_card = current_subscription.credit_card
            expiration_date = "{expiration_month}/{expiration_year}".format(
                expiration_month=credit_card["expiration_month"],
                expiration_year=credit_card["expiration_year"],
            )
            analytics_data = {
                "date": now.strftime("%d/%m/%Y"),
                "masked_card_number": credit_card["masked_card_number"],
                "expiration_date": expiration_date,
                "plan_label": current_subscription.plan_name,
            }

        analytics.track(user.id, label, analytics_data)

    def _message_reactivate_error(self):
        raise NotImplementedError
