"""
Budgeteer main app models.

This includes everything that's absolutely needed for Budgeteer to function.
"""
import calendar
import datetime

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Category(models.Model):
    """
    A category that money goes into when budgeting.
    """
    name = models.CharField(max_length=200)

class Sheet(models.Model):
    """
    A round of budgeting where categories get assigned monetary values.
    """
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.PositiveSmallIntegerField()

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
        Calculates the value left to budget on this sheet.

        Calculated as all positive transactions (inflow) minus already budgeted amounts.
        """
        return self.__get_sum_of_inflows() - self.__get_sum_of_budgets()

    def __get_sum_of_inflows(self):
        return sum(trans.value for trans in filter(lambda t: t.value > 0, self.transactions))

    def __get_sum_of_budgets(self):
        return self.sheetentry_set.all().aggregate(models.Sum('value'))['value__sum']

    class Meta:
        unique_together = ['month', 'year']

class SheetEntry(models.Model):
    """
    The budget of a single category for a single sheet.
    """
    sheet = models.ForeignKey(Sheet, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    value = models.DecimalField(max_digits=12, decimal_places=2)

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
