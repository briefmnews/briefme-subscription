import datetime

from django.db import models

from model_utils.models import TimeStampedModel

from .managers import TrialCouponManager


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
    verbose_name = models.CharField(
        max_length=200,
        verbose_name="Nom public",
        help_text="Exemple: un abonnement à vie",
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
            delta_days = (self.expires_at - datetime.date.today).days
            duration = delta_days if delta_days >= 0 else 0
        else:
            duration = self.number_of_days

        return duration
