import json
import logging
import pytest

from briefme_subscription.chargify import ChargifyHelper
from .factories import ChargifySubscriptionFactory, UserFactory

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_chargify_helper(mocker):
    mocker.patch.object(
        ChargifyHelper, "create_default_payment_profile_from_token", return_value=[]
    )
    mocker.patch.object(
        ChargifyHelper, "reactivate_subscription", return_value={"subscription": None}
    )


def get_chargify_subscription(mocker, filename):
    with open(filename) as f:
        chargify_subscription = json.load(f)
    return mocker.patch.object(
        ChargifyHelper, "get_subscription", return_value=chargify_subscription
    )


@pytest.fixture
def subscription_with_state(mocker, state):
    assert state in [
        "active",
        "trialing",
        "past_due",
        "trial_ended",
        "canceled",
    ]
    get_chargify_subscription(mocker, f"tests/fixtures/{state}_subscription.json")

    subscription = ChargifySubscriptionFactory(user=UserFactory())
    subscription.refresh_chargify_subscription_cache()

    return subscription
