"""
Budgeteer main app models.

This includes everything that's absolutely needed for Budgeteer to function.
"""
import calendar
import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class Category(models.Model):
    """
    A category that money goes into when budgeting.

    Model instances should not be deleted when they are used in locked sheets. The data model
    however does not enforce this.
    """
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

class Sheet(models.Model):
    """
    A round of budgeting where categories get assigned monetary values.

    Only a single sheet can be created per month. The calculation of the available amount expects
    sheets to be continous without skipped months. The data model however does not enforce this.

    After a carryover is calculated the sheet is assumed to be locked from further modification.
    The sheet entries on this sheet should not be changed anymore.
    """
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.PositiveSmallIntegerField()
    carryover = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    @property
    def transactions(self):
        """
        Returns all transactions on this sheet.
        """
        date_start = datetime.date(self.year, self.month, 1)
        date_end = datetime.date(self.year, self.month,
                                 calendar.monthrange(self.year, self.month)[1])
        return Transaction.objects.filter(date__gte=date_start).filter(date__lte=date_end)

    @property
    def available(self):
        """
        Calculates the value left to budget on this sheet (may be negative if overbudgeted).

        Calculated as all transactions minus already budgeted amounts plus what is left from the
        previous sheet.
        """
        if self.carryover is not None:
            return self.carryover

        if self.previous is not None:
            return (self.__get_sum_of_inflows()
                    - self.__get_sum_of_budgets()
                    + self.previous.available)

        return self.__get_sum_of_inflows() - self.__get_sum_of_budgets()

    @property
    def previous(self):
        """
        Gets the previous sheet or None of none exists.

        This expects sheets to be continuous without gaps.
        """
        month = self.month - 1 if self.month > 1 else 12
        year = self.year if self.month > 1 else self.year - 1
        try:
            return Sheet.objects.get(month=month, year=year)
        except Sheet.DoesNotExist:
            return None

    def __str__(self):
        return f"{self.month:02d}/{self.year}"

    class Meta:
        unique_together = ['month', 'year']

    def __get_sum_of_inflows(self):
        return sum(trans.value for trans in filter(lambda t: t.value > 0, self.transactions))

    def __get_sum_of_budgets(self):
        return self.sheetentry_set.all().aggregate(models.Sum('value'))['value__sum']

@receiver(post_save, sender=Sheet)
def initialize_sheet_with_entries(instance, created, raw, **kwargs):
    """
    Creates a sheet entry for every category the moment the sheet is created.
    """
    if created and not raw:
        for category in Category.objects.all():
            SheetEntry(sheet=instance, category=category, value=Decimal(0)).save()

class SheetEntry(models.Model):
    """
    The budget of a single category for a single sheet.

    This model is not intended to have instances created or deleted by the user. The instance's
    lifecycle is completely dependent upon other model instances.

    After the sheet entry is locked nothing can be edited anymore. It exists only for
    statistical purposes.
    """
    sheet = models.ForeignKey(Sheet, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    locked = models.BooleanField(default=False)

    LOCKABLE_FIELDS = ['sheet', 'category', 'value']

    def clean(self):
        super(SheetEntry, self).clean()

        if self.pk is not None and self.locked:
            previous_state = SheetEntry.objects.get(pk=self.pk)
            for field in SheetEntry.LOCKABLE_FIELDS:
                previous_value = getattr(previous_state, field)
                current_value = getattr(self, field)
                if previous_value != current_value:
                    raise ValidationError(f"Field {field} was changed on locked sheet entry.")

    def __str__(self):
        return f"[{str(self.sheet)}] {str(self.category)}: {str(self.value)}"

@receiver(post_save, sender=Category)
def create_sheet_entries_on_category_creation(instance, created, raw, **kwargs):
    """
    Creates a sheet entry for every open sheet the moment a new category is created.
    """
    if created and not raw:
        for sheet in Sheet.objects.filter(carryover__isnull=True):
            new_sheet = SheetEntry(sheet=sheet, category=instance, value=Decimal(0))
            new_sheet.save()

class Account(models.Model):
    """
    A place where money is kept, eg. a checking account or your wallet.
    """
    name = models.CharField(max_length=200)
    balance = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def total(self):
        """
        Returns the account total.

        This includes the starting balance and all non-locked transactions, including upcoming
        """
        return self.balance + self.__get_transaction_total()

    def __str__(self):
        return self.name

    def __get_transaction_total(self):
        aggregated = (Transaction.objects
                      .filter(account=self)
                      .filter(locked=False)
                      .aggregate(models.Sum('value'))
                      ['value__sum'])
        return aggregated if aggregated is not None else 0

class Transaction(models.Model):
    """
    The flow of money from an account to a partner with a category as classification.
    """
    partner = models.CharField(max_length=200)
    date = models.DateField()
    value = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    locked = models.BooleanField(default=False)

    LOCKABLE_FIELDS = ['partner', 'date', 'value', 'category', 'account']

    def clean(self):
        super(Transaction, self).clean()

        if self.pk is not None and self.locked:
            previous_state = Transaction.objects.get(pk=self.pk)
            for field in Transaction.LOCKABLE_FIELDS:
                previous_value = getattr(previous_state, field)
                current_value = getattr(self, field)
                if previous_value != current_value:
                    raise ValidationError(f"Field {field} was changed on locked transaction.")

    def __str__(self):
        return (
            f"[{self.date:%Y-%m-%d}] {str(self.account)} "
            f"-> {str(self.partner)} ({str(self.category)})"
        )
