import datetime
import logging
from hashlib import sha1
import hmac
import urllib.request, urllib.parse, urllib.error
import sys

from django.conf import settings

import requests

from libs.chargify_python import ChargifyNotFoundError, ChargifyUnprocessableEntityError
from nonce.models import Nonce

logger = logging.getLogger(__name__)


def get_chargify_python():
    """
    Get an instance of the "Chargify Python" library:
    https://github.com/hindsightlabs/chargify-python
    """
    from libs.chargify_python import Chargify

    chargify_python = Chargify(settings.CHARGIFY_API_KEY, settings.CHARGIFY_SITE)
    return chargify_python


class ChargifyException(Exception):
    pass


class ChargifyHelper(object):
    """
    Chargify helper to interect with Chargify's API.

    Inspired by Recurly's helper for consistency & backward compat.
    """

    chargify_python = None

    STATES = [
        ("trialing", "trialing"),
        ("trial_ended", "trial_ended"),
        ("active", "active"),
        ("on_hold", "on_hold"),
        ("soft_failure", "soft_failure"),
        ("past_due", "past_due"),
        ("canceled", "canceled"),
        ("unpaid", "unpaid"),
        ("expired", "expired"),
    ]

    def __init__(self):
        self.chargify_python = get_chargify_python()

    def get_card_update_url(self, remote_subscription_id):
        return "%s/api/v2/subscriptions/%s/card_update" % (
            settings.CHARGIFY_SUBDOMAIN,
            remote_subscription_id,
        )

    def get_signup_url(self):
        return "%s/api/v2/signups" % (settings.CHARGIFY_SUBDOMAIN,)

    # DOUBT rename in get_customer() ? ("account" in Chargify are called
    # customers)
    def create_account(self, user):
        """
        Create the corresponding Chargify account to the given `user`.
        """

        data = {
            "customer": {
                "reference": user.pk,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
            }
        }

        try:
            self.chargify_python.customers.create(data=data)
        except Exception as e:
            raise ChargifyException("Unable to create customer: %s" % (e,))

        return self.get_customer_by_reference(user.pk)

    def update_customer(self, user, customer_id=None, extra_fields=None):
        """
        Update remote Customer with relevant fields of given `user`.

        `customer_id` is the id of the user in Chargify. If not specified, an
        additional request will be made to find the user in Chargify, based on
        their id in the Brief.me database.

        `extra_fields` is an optional dict to set more informations.
        """
        if not customer_id:
            customer_id = self.get_customer_by_reference(user.pk)["id"]

        default_last_name = settings.AUTH_USER_LASTNAME_DEFAULT
        data = {
            "customer": {
                "first_name": user.first_name or user.email,
                "last_name": user.last_name or default_last_name,
                "email": user.email,
            }
        }

        if user.organization:
            data["customer"]["organization"] = user.organization

        if extra_fields:
            data["customer"].update(extra_fields)

        self.chargify_python.customers.update(customer_id=customer_id, data=data)

    def get_subscription_preview(
        self, product_handle, billing_country="FR", coupon_code=None
    ):
        data = {
            "subscription": {
                "product_handle": product_handle,
                "coupon_code": coupon_code,
                "payment_profile_attributes": {"billing_country": billing_country},
                "customer_attributes": {
                    "email": "fake@email.com"
                },  # Doesn't have to exist...
            }
        }

        response = self.chargify_python.subscriptions.preview.create(data=data)
        subscription_preview = response["subscription_preview"]

        if subscription_preview["current_billing_manifest"]["period_type"] == "trial":
            preview_data = subscription_preview["next_billing_manifest"]
        else:  # `period_type` is "recurring"
            preview_data = subscription_preview["current_billing_manifest"]

        return preview_data

    def create_subscription(
        self,
        customer_reference,
        product_handle,
        coupon_code=None,
        next_billing_at=None,
        expires_at=None,
        chargify_token=None,
    ):
        """
        Subscribe Chargify `account` to a subscription corresponding to
        the given `product`.
        """
        data = {
            "subscription": {
                "product_handle": product_handle,
                "customer_reference": customer_reference,
            }
        }
        if coupon_code:
            data["subscription"].update({"coupon_code": coupon_code})
        if next_billing_at:
            data["subscription"].update(
                {"next_billing_at": next_billing_at.isoformat()}
            )
        if chargify_token:
            data["subscription"].update(
                {"credit_card_attributes": {"chargify_token": chargify_token}}
            )

        subscription = self.chargify_python.subscriptions.create(data=data)

        subscription_id = subscription["subscription"]["id"]

        if expires_at:
            data = {"subscription": {"expires_at": expires_at.isoformat()}}
            self.chargify_python.subscriptions.override.update(
                subscription_id=subscription_id, data=data
            )

        return subscription["subscription"]

    def update_subscription(self, user, product_handle, next_billing_at=None):
        """
        Update Subscription
        https://reference.chargify.com/v1/subscriptions/update-subscription
        """
        data = {"subscription": {"product_handle": product_handle}}
        if next_billing_at:
            data["subscription"].update(
                {"next_billing_at": next_billing_at.isoformat()}
            )

        try:
            subscription = self.chargify_python.subscriptions.update(
                subscription_id=user.current_subscription.uuid, data=data
            )
            return subscription
        except ChargifyUnprocessableEntityError as e:
            logger.error(f"Cannot update subscription: {e}")
            raise ChargifyException(f"Cannot update subscription: {e}")

    def get_subscriptions_by_customer_id(self, customer_id):
        """
        This method will retreive a list of subscriptions associated with a Customer.
        https://reference.chargify.com/v1/subscriptions/list-by-customer
        """
        try:
            return self.chargify_python.customers.subscriptions.read(
                customer_id=customer_id
            )
        except ChargifyNotFoundError:
            return None

    def get_subscriptions(self, **kwargs):
        if "page" not in kwargs:
            kwargs["page"] = 1
        if "per_page" not in kwargs:
            kwargs["per_page"] = 200

        while True:
            subscriptions = self.chargify_python.subscriptions(**kwargs)
            if not subscriptions:
                break
            kwargs["page"] += 1
            yield subscriptions

    def get_subscription(self, subscription_id):
        try:
            response = self.chargify_python.subscriptions(
                subscription_id=subscription_id
            )
        except ChargifyNotFoundError:
            return None

        return response["subscription"]

    def get_subscription_product(self, subscription_id):
        subscription = self.get_subscription(subscription_id)
        if subscription:
            return subscription["product"]
        else:
            return None

    def get_product(self, handle=None, product_id=None):
        if handle:
            try:
                return self.chargify_python.products.handle(api_handle=handle)[
                    "product"
                ]
            except ChargifyNotFoundError:
                return None

        if product_id:
            try:
                return self.chargify_python.products(product_id=product_id)["product"]
            except ChargifyNotFoundError:
                return None

        return None

    def get_products(self, handles):
        products = []
        for handle in handles:
            try:
                products.append(
                    self.chargify_python.products.handle(api_handle=handle)["product"]
                )
            except ChargifyNotFoundError:
                continue

        return products

    def hold(self, subscription_id, automatically_resume_at):
        try:
            self.chargify_python.subscriptions.hold.create(
                subscription_id=subscription_id,
                data={
                    "hold": {
                        "automatically_resume_at": automatically_resume_at.strftime(
                            "%Y-%m-%d"
                        )
                    }
                },
            )
        except ChargifyUnprocessableEntityError as e:
            raise e

    def resume(self, subscription_id):
        self.chargify_python.subscriptions.resume.create(
            subscription_id=subscription_id
        )

    def get_invoices(self, **kwargs):
        if "page" not in kwargs:
            kwargs["page"] = 1
        if "per_page" not in kwargs:
            kwargs["per_page"] = 200

        while True:
            invoices = self.chargify_python.invoices(**kwargs)
            if not invoices:
                break
            kwargs["page"] += 1
            yield invoices

    def register_payment(self, invoice_id, amount_in_cents, memo=""):
        self.chargify_python.invoices.payments.create(
            invoice_id=invoice_id,
            data={"payment": {"amount_in_cents": amount_in_cents}, "memo": memo},
        )

    def get_subscription_statements(self, subscription_id):
        domain = settings.CHARGIFY_SUBDOMAIN
        sorting = "sort=created_at&direction=desc"
        statements_url = (
            f"{domain}/subscriptions/{subscription_id}/statements.json?{sorting}"
        )
        response = requests.get(statements_url, auth=(settings.CHARGIFY_API_KEY, "x"))

        if not response.status_code == 200:
            raise ChargifyException(
                "Error getting Chargify statements on subscription {subscription_id}: {response}".format(
                    subscription_id=subscription_id, response=str(response.content)
                )
            )

        statements = response.json()
        response_list = [statement["statement"] for statement in statements]

        return response_list

    def get_statement(self, statement_id):
        statement_url = "{domain}/statements/{statement_id}.json".format(
            domain=settings.CHARGIFY_SUBDOMAIN, statement_id=statement_id
        )
        response = requests.get(statement_url, auth=(settings.CHARGIFY_API_KEY, "x"))

        if not response.status_code == 200:
            raise ChargifyException(
                "Error getting Chargify statement {statement_id}: {response}".format(
                    statement_id=statement_id, response=str(response.content)
                )
            )

        return response.json()["statement"]

    def get_subscription_transactions(self, subscription_id):
        return [
            t["transaction"]
            for t in self.chargify_python.subscriptions.transactions(
                subscription_id=subscription_id
            )
        ]

    def get_transaction(self, transaction_id):
        if transaction_id:
            return self.chargify_python.transactions(transaction_id=transaction_id)[
                "transaction"
            ]

    def get_customer_by_reference(self, user_id):
        """
        Read the Customer by Reference Value
        https://reference.chargify.com/v1/customers/read-the-customer-by-reference-value
        """
        try:
            return self.chargify_python.customers.lookup.read(
                qs_params={"reference": user_id}
            )["customer"]
        except ChargifyNotFoundError:
            return None

    def get_coupon(self, code):
        res = requests.get(
            "%s/coupons/find.json?code=%s" % (settings.CHARGIFY_SUBDOMAIN, code),
            auth=(settings.CHARGIFY_API_KEY, "x"),
        )

        if res.status_code == 200:
            coupon = res.json()["coupon"]
        elif res.status_code == 404:
            coupon = None
        else:
            raise ChargifyException(
                "Error retrieving Chargify coupon (code: %s)." % code
            )

        return coupon

    def set_product(self, subscription_id, product_handle, delayed=False):
        """
        Set `product_handle` on remote Chargify subscription identified by
        `subscription_id`.
        """
        data = {
            "subscription": {
                "product_handle": product_handle,
                "product_change_delayed": delayed,
            }
        }
        response = self.chargify_python.subscriptions.update(
            subscription_id=subscription_id, data=data
        )
        if not delayed:
            new_handle = response["subscription"]["product"]["handle"]
        else:
            product_id = response["subscription"]["next_product_id"]
            new_handle = self.get_product(product_id=product_id)["handle"]
        if new_handle != product_handle:
            raise ChargifyException(
                'Unable to set new product "%s" for subscription %s.'
                % (product_handle, subscription_id)
            )
        return response

    def cancel_delayed_product_change(self, subscription_id):
        data = {"subscription": {"next_product_id": ""}}
        self.chargify_python.subscriptions.update(
            subscription_id=subscription_id, data=data
        )

    def add_coupon(self, subscription_id, coupon_code):
        """
        Add coupon `coupon_code` on remote Chargify subscription identified by
        `subscription_id`.
        """
        response = self.chargify_python.subscriptions.add_coupon.create(
            subscription_id=subscription_id, qs_params={"code": coupon_code}
        )
        return response

    def remove_coupon(self, subscription_id):
        response = self.chargify_python.subscriptions.remove_coupon.delete(
            subscription_id=subscription_id
        )
        return response

    def cancel_subscription(self, subscription_id, delayed=False, msg=""):

        try:
            if delayed:
                self.chargify_python.subscriptions.update(
                    subscription_id=subscription_id,
                    data={"subscription": {"cancel_at_end_of_period": True}},
                )
            else:
                self.chargify_python.subscriptions.delete(
                    subscription_id=subscription_id,
                    data={"subscription": {"cancellation_message": msg}},
                )
        except ChargifyUnprocessableEntityError as e:
            if "The subscription is already canceled" in e.errors:
                pass
            else:
                raise e

    def cancel_pending_cancellation(self, subscription_id):
        """
        Remove delayed cancel

        https://reference.chargify.com/v1/subscriptions-cancellations/cancel-subscription
        """

        self.chargify_python.subscriptions.delayed_cancel.delete(
            subscription_id=subscription_id
        )

    def reactivate_subscription(self, subscription_id, **qs):
        response = self.chargify_python.subscriptions.reactivate.update(
            subscription_id=subscription_id, qs_params=qs
        )
        return response

    def set_subscription_next_billing_at(self, subscription_id, dt):
        self.chargify_python.subscriptions.update(
            subscription_id=subscription_id,
            data={"subscription": {"next_billing_at": dt.isoformat()}},
        )

    def set_subscription_expires_at(self, subscription_id, expires_at):
        self.chargify_python.subscriptions.override.update(
            subscription_id=subscription_id,
            data={"subscription": {"expires_at": expires_at.isoformat()}},
        )

    def set_subscription_payment_collection_method(self, subscription_id, value):
        if value not in ("automatic", "invoice"):
            raise ValueError(
                "The payment collection method must be 'automatic' or invoice"
            )
        self.chargify_python.subscriptions.update(
            subscription_id=subscription_id,
            data={"subscription": {"payment_collection_method": value}},
        )

    def unset_subscription_expires_at(self, subscription_id):
        self.chargify_python.subscriptions.override.update(
            subscription_id=subscription_id, data={"subscription": {"expires_at": ""}}
        )

    def get_chargify_direct_signature(self, timestamp, nonce, *args):
        api_id = settings.CHARGIFY_DIRECT_API_ID
        secret = settings.CHARGIFY_DIRECT_API_SECRET
        data = "".join([str(x) for x in args])
        value = "{api_id}{timestamp}{nonce}{data}".format(
            api_id=api_id, timestamp=timestamp, nonce=nonce, data=data
        )

        return hmac.new(secret.encode("UTF-8"), value.encode("UTF-8"), sha1).hexdigest()

    def chargify_direct_secure_initial(self, redirect_uri, data=None):
        """
        Initiate Chargify Direct Secure Parameters.

        https://docs.chargify.com/chargify-direct-introduction#secure-parameters
        """
        if data is None:
            data = {}

        data["redirect_uri"] = redirect_uri
        data = urllib.parse.urlencode(data)

        nonce = Nonce.new("chargify")
        nonce.save()

        return {
            "secure_api_id": settings.CHARGIFY_DIRECT_API_ID,
            "secure_nonce": nonce.value,
            "secure_timestamp": nonce.timestamp,
            "secure_data": data,
            "secure_signature": self.get_chargify_direct_signature(
                nonce.timestamp, nonce.value, data
            ),
        }

    def chargify_direct_callback_is_valid(self, request):
        """
        Check Chargify Direct Response Parameters.

        https://docs.chargify.com/chargify-direct-introduction#response-parameters
        """
        api_id = request.GET["api_id"]

        if api_id != settings.CHARGIFY_DIRECT_API_ID:
            return False

        try:
            nonce = Nonce.objects.get(
                service="chargify",
                value=request.GET["nonce"],
                timestamp=request.GET["timestamp"],
            )
        except (Nonce.DoesNotExist, Nonce.MultipleObjectsReturned):
            return False

        if nonce.expired:
            return False

        nonce.delete()

        local_signature = self.get_chargify_direct_signature(
            nonce.timestamp,
            nonce.value,
            request.GET["status_code"],
            request.GET["result_code"],
            request.GET["call_id"],
        )

        if request.GET["signature"] == local_signature:
            return True

        return False

    def get_chargify_api_call(self, call_id):
        """
        Retrieve Chargify API v2 & Chargify Direct call.

        https://docs.chargify.com/api-call
        """
        url = "%s/api/v2/calls/%s" % (settings.CHARGIFY_SUBDOMAIN, call_id)
        call = requests.get(
            url,
            auth=(
                settings.CHARGIFY_DIRECT_API_ID,
                settings.CHARGIFY_DIRECT_API_PASSWORD,
            ),
        )

        if call.status_code != 200:
            raise ChargifyException(
                "Error retrieving Chargify API call (ID %s)." % call_id
            )

        return call.json()["call"]

    def create_payment_profile_from_token(self, subscription, token):
        return self.chargify_python.payment_profiles.create(
            data={
                "payment_profile": {
                    "customer_id": subscription.customer["id"],
                    "chargify_token": token,
                }
            }
        )

    def set_default_payment_profile(self, subscription, payment_profile_id):
        return self.chargify_python.subscriptions.payment_profiles.change_payment_profile.create(
            subscription_id=subscription.uuid, payment_profile_id=payment_profile_id
        )

    def create_default_payment_profile_from_token(self, subscription, token):
        payment_profile = self.create_payment_profile_from_token(subscription, token)
        return self.set_default_payment_profile(
            subscription, payment_profile["payment_profile"]["id"]
        )

    def delete_payment_profile(self, subscription_id, payment_profile_id):
        return self.chargify_python.subscriptions.payment_profiles.delete(
            subscription_id=subscription_id, payment_profile_id=payment_profile_id
        )

    def get_product_families(self):
        """
        Read Product Families For a Site
        https://reference.chargify.com/v1/product-families/list-product-family-via-site
        """
        return self.chargify_python.product_families.read()

    def get_products_for_a_product_family(self, product_family_id):
        """
        This method allows to retrieve a list of Products belonging to a Product Family.
        https://reference.chargify.com/v1/products/list-products
        """
        return self.chargify_python.product_families.products.read(
            product_family_id=str(product_family_id)
        )

    def retry_subscription(self, subscription_id):
        """
        Retry a Subscription
        https://reference.chargify.com/v1/subscriptions-payment-methods-retries-balance-reset/retry-subscription
        """
        self.chargify_python.subscriptions.retry.update(subscription_id=subscription_id)

    def create_migration(self, subscription_id, product_handle):
        """
        Migrate a subscription from one product to another
        https://reference.chargify.com/v1/subscriptions-product-changes-migrations-upgrades-downgrades/create-migration#create-migration
        """
        data = {
            "migration": {
                "product_handle": product_handle,
                "include_trial": False,
                "include_initial_charge": False,
                "include_coupons": False,
                "preserve_period": False,
            }
        }
        self.chargify_python.subscriptions.migrations.create(
            subscription_id=subscription_id, data=data
        )

    def create_metadata(self, resource, resource_id, data):
        """
        Create Metadata
        https://reference.chargify.com/v1/custom-fields-metadata/create-metadata
        """
        self.chargify_python.metadata.create(
            resource=resource, resource_id=resource_id, data={"metadata": data}
        )

    def get_metadata_for_subscriber(self, subscription_id):
        return self.chargify_python.subscriptions.metadata.read(
            subscription_id=subscription_id
        )["metadata"]

    def purge_subscription(self, subscription_id, customer_id):
        """
        Remove a subscription in chargify. This works on live site because Chargify activated for us.
        https://reference.chargify.com/v1/subscriptions/purge-subscription
        """
        self.chargify_python.subscriptions.purge.create(
            subscription_id=subscription_id, qs_params={"ack": customer_id}
        )


class ProductsDict(dict):
    """
    Dict-like object providing informations about Chargify's products,
    with live updating and cache.
    """

    chargify = None
    last_update = None
    paying = None
    trial = None
    update_delay = 60 * 20  # Every 20 minutes.

    def __init__(self, *args, **kwargs):
        r = super(ProductsDict, self).__init__(*args, **kwargs)
        self.chargify = ChargifyHelper()
        return r

    def __getattribute__(self, *args, **kwargs):

        # If requiried attribute accesses the products' data and the object is
        # empty or data outdated, let's (re)load.
        if (
            args[0]
            in (
                "get",
                "keys",
                "items",
                "values",
                "paying",
                "trial",
                "__str__",
                "__str__",
            )
            and (not self.last_update or self._is_outdated())
        ):
            self._load()

        return super().__getattribute__(*args, **kwargs)

    def __getitem__(self, *args, **kwargs):
        # When accessing an item and the object is empty or data outdated,
        # let's (re)load the products.
        if not self.last_update or self._is_outdated():
            self._load()

        return super().__getitem__(*args, **kwargs)

    def _is_outdated(self):
        now = datetime.datetime.now()
        return (now - self.last_update).total_seconds() > self.update_delay

    def _load(self):
        # (Re)loading the products.
        if not self.last_update:
            load = "Loading"
        else:
            load = "Updating"

        sys.stdout.write("%s Chargify products… " % load)
        sys.stdout.flush()

        self.clear()

        products = self.get_all_products()

        for p in products:
            # Insert some helper data on-the-fly into the products.
            p["interval_yearly"] = False
            p["interval_monthly"] = False

            if p["interval_unit"] == "month" and p["interval"] == 12:
                p["interval_yearly"] = True

            if p["interval_unit"] == "month" and p["interval"] == 1:
                p["interval_monthly"] = True

            self[p["handle"]] = p

        self.last_update = datetime.datetime.now()

        # This could be done automatically from Chargify's data,
        # but this way is better to specify the order we want.
        self.paying = []
        handles = settings.CHARGIFY_PAYING_PRODUCTS_HANDLES

        for handle in handles:
            self.paying.append(self[handle])

        self.trial = self[settings.CHARGIFY_TRIAL_PRODUCT_HANDLE]

        sys.stdout.write("Done.\n")

    def get_all_products(self):
        products = []
        product_families = self.chargify.get_product_families()
        for product_family in product_families:
            for product in self.chargify.get_products_for_a_product_family(
                product_family["product_family"]["id"]
            ):
                products.append(product["product"])

        return products

    def get_by_id(self, product_id, default=None):
        try:
            return [p for _, p in PRODUCTS.items() if p["id"] == product_id][0]
        except IndexError as e:
            if default is not None:
                return default
            raise e


# Instantiate a `ProductsDict` into PRODUCTS to make once instance
# available anywhere via __import__.
PRODUCTS = ProductsDict()
