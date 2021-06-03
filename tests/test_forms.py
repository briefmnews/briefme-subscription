import pytest

from briefme_subscription.forms import ChargifyUpdateCustomerForm

pytestmark = pytest.mark.django_db()


class TestChargifyUpdateCustomerForm:
    @pytest.mark.parametrize("payment_method", ["credit_card", "paypal"])
    def test_form_works(self, payment_method):
        # GIVEN
        data = {"first_name": "john", "last_name": "doe", "payment_method": payment_method, "country": "FR", "zip": "75000"}

        # WHEN
        form = ChargifyUpdateCustomerForm(data=data)

        # THEN
        assert form.is_valid()

    def test_form_with_invalid_payment_choice(self):
        # GIVEN
        data = {"first_name": "john", "last_name": "doe", "payment_method": "dummy", "country": "FR", "zip": "75000"}

        # WHEN
        form = ChargifyUpdateCustomerForm(data=data)

        # THEN
        form.is_valid()
        assert "payment_method" in form.errors

    def test_form_with_invalid_country(self):
        # GIVEN
        data = {"first_name": "john", "last_name": "doe", "payment_method": "dummy", "country": "france", "zip": "75000"}

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
        data = {"first_name": "", "last_name": "", "payment_method": "", "country": "", "zip": ""}

        # WHEN
        form = ChargifyUpdateCustomerForm(data=data)

        # THEN
        form.is_valid()
        assert "first_name" in form.errors
        assert "last_name" in form.errors
        assert "payment_method" in form.errors
        assert "country" in form.errors
        assert "zip" in form.errors
