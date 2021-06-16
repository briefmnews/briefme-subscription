import pytest

from briefme_subscription.chargify import (
    ChargifyHelper,
    ChargifyUnprocessableEntityError,
)
from briefme_subscription.forms import ChargifyUpdateCustomerForm, ChargifyJsPaymentForm

pytestmark = pytest.mark.django_db()


class TestChargifyUpdateCustomerForm:
    @pytest.mark.parametrize("payment_method", ["credit_card", "paypal"])
    def test_form_works(self, payment_method):
        # GIVEN
        data = {
            "first_name": "john",
            "last_name": "doe",
            "payment_method": payment_method,
            "country": "FR",
            "zip": "75000",
        }

        # WHEN
        form = ChargifyUpdateCustomerForm(data=data)

        # THEN
        assert form.is_valid()

    def test_form_with_invalid_payment_choice(self):
        # GIVEN
        data = {
            "first_name": "john",
            "last_name": "doe",
            "payment_method": "dummy",
            "country": "FR",
            "zip": "75000",
        }

        # WHEN
        form = ChargifyUpdateCustomerForm(data=data)

        # THEN
        form.is_valid()
        assert "payment_method" in form.errors

    def test_form_with_invalid_country(self):
        # GIVEN
        data = {
            "first_name": "john",
            "last_name": "doe",
            "payment_method": "dummy",
            "country": "france",
            "zip": "75000",
        }

        # WHEN
        form = ChargifyUpdateCustomerForm(data=data)

        # THEN
        form.is_valid()
        assert "country" in form.errors

    def test_form_with_missing_fields(self):
        # GIVEN
        data = {}

        # WHEN
        form = ChargifyUpdateCustomerForm(data=data)

        # THEN
        form.is_valid()
        assert "first_name" in form.errors
        assert "last_name" in form.errors
        assert "payment_method" in form.errors
        assert "country" in form.errors
        assert "zip" in form.errors

    def test_form_with_blank_fields(self):
        # GIVEN
        data = {
            "first_name": "",
            "last_name": "",
            "payment_method": "",
            "country": "",
            "zip": "",
        }

        # WHEN
        form = ChargifyUpdateCustomerForm(data=data)

        # THEN
        form.is_valid()
        assert "first_name" in form.errors
        assert "last_name" in form.errors
        assert "payment_method" in form.errors
        assert "country" in form.errors
        assert "zip" in form.errors


class TestChargifyJsPaymentForm:
    @pytest.mark.usefixtures("mock_chargify_helper")
    @pytest.mark.parametrize("state", ["trialing", "trial_ended", "canceled"])
    @pytest.mark.parametrize("payment_method", ["credit_card", "paypal"])
    def test_create_payment_profile_works(
        self, state, subscription_with_state, payment_method
    ):
        # GIVEN
        data = {"chargify_token": "dummy-token", "country": "FR", "zip": "75000"}
        request = {"user": subscription_with_state.user}

        # WHEN
        form = ChargifyJsPaymentForm(
            data=data,
            request=request,
            current_subscription=subscription_with_state,
            payment_method="credit_card",
        )

        # THEN
        assert form.is_valid()
        ChargifyHelper().create_default_payment_profile_from_token.assert_called_once_with(
            subscription_with_state, form.cleaned_data["chargify_token"]
        )
        assert subscription_with_state.payment_collection_method == "automatic"

    @pytest.mark.usefixtures("mock_chargify_helper")
    @pytest.mark.parametrize("state", ["trial_ended", "canceled"])
    def test_reactivate_subscription(self, state, subscription_with_state):
        # GIVEN
        data = {"chargify_token": "dummy-token", "country": "FR", "zip": "75000"}
        request = {"user": subscription_with_state.user}

        # WHEN
        form = ChargifyJsPaymentForm(
            data=data,
            request=request,
            current_subscription=subscription_with_state,
            payment_method="credit_card",
        )

        # THEN
        assert form.is_valid()
        ChargifyHelper().reactivate_subscription.assert_called_once_with(
            subscription_id=subscription_with_state.uuid, include_trial=False
        )
