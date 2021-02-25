import logging

from django.http import HttpResponseBadRequest

from ..chargify import ChargifyHelper


logger = logging.getLogger(__name__)


class ChargifyDirectMixin:
    chargify_helper = None
    chargify_api_call = None
    chargify_direct_prefix = "payment_profile"

    def dispatch(self, *args, **kwargs):
        self.chargify_helper = ChargifyHelper()
        self.chargify_api_call = None

        return super().dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        if "call_id" in request.GET:
            return self.handle_chargify_direct_callback(request, *args, **kwargs)

        return super().get(request, *args, **kwargs)

    def handle_chargify_direct_callback(self, request, *args, **kwargs):
        """
        When user has lands on this page back again after submitting to
        Chargify's "Transparent Redirect".
        """
        if not self.chargify_helper.chargify_direct_callback_is_valid(request):
            return HttpResponseBadRequest()

        # Retrieve JSON call response.
        chargify_api_call = self.chargify_helper.get_chargify_api_call(
            request.GET["call_id"]
        )
        self.chargify_api_call = chargify_api_call
        response = chargify_api_call["response"]
        result = response["result"]
        subscriptioncardupdater = response.get("subscriptioncardupdater", None)

        if subscriptioncardupdater:
            self.payment_profile = subscriptioncardupdater["payment_profile"]

        # End wizard and notify if card update call is successful
        if int(result["result_code"]) == 2000:
            return self.chargify_direct_done()
        else:
            logger.error(result["errors"][0]["message"])

        return super().get(request, *args, **kwargs)

    def chargify_direct_done(self):
        raise NotImplementedError

    def get_chargify_direct_context_data(self):
        chargify_api_call = (
            self.chargify_api_call if "call_id" in self.request.GET else None
        )
        return {
            "chargify_direct_form_url": self.get_chargify_direct_form_url(),
            "chargify_api_call": chargify_api_call,
        }

    def get_chargify_direct_initial(self, redirect_url, data):
        """
        Build initial secure data of form to be sent to Chargify Transparent
        Redirect.
        """
        initial = self.chargify_helper.chargify_direct_secure_initial(
            redirect_url, data=data
        )

        return initial

    def get_chargify_direct_form_url(self):
        raise NotImplementedError
