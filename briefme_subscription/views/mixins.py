import logging

logger = logging.getLogger(__name__)


class AddCurrentSubscriptionMixin:
    """Add the current subscription to context and as attribute."""

    current_subscription = None
    reset_subscription = True

    def dispatch(self, request, *args, **kwargs):
        if not self.current_subscription:
            self.set_current_subscription()

        return super().dispatch(request, *args, **kwargs)

    def set_current_subscription(self):
        if self.request.user.is_authenticated:
            self.current_subscription = self.request.user.current_subscription
            if self.reset_subscription and self.current_subscription:
                self.current_subscription.clear_chargify_subscription_cache()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_subscription"] = self.current_subscription
        return context
