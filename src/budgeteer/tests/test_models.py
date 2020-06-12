"""
Unit tests for the budgeteer main app models.
"""

import datetime
import random
import string
import calendar
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase

import budgeteer.models as models

#pylint: disable=missing-function-docstring
#pylint: disable=missing-class-docstring

class CategoryTests(TestCase):

    def test_name_save(self):
        category = models.Category()
        category.name = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        category.full_clean()
        category.save()

        category_from_db = models.Category.objects.get(pk=category.pk)

        self.assertEqual(category.name, category_from_db.name)

    def test_name_max_length_not_ok(self):
        category = models.Category()
        category.name = ''.join(random.choices(string.ascii_letters + string.digits, k=201))
        with self.assertRaises(ValidationError):
            category.full_clean()

class SheetTests(TestCase):

    def test_month_save(self):
        expected_month = random.randint(1, 12)

        sheet = models.Sheet()
        sheet.month = expected_month
        sheet.year = 1
        sheet.full_clean()
        sheet.save()

        sheet_from_db = models.Sheet.objects.get(pk=sheet.pk)

        self.assertEqual(expected_month, sheet_from_db.month)

    def test_month_allowed_values(self):
        for month in range(1, 12):
            sheet = models.Sheet()
            sheet.month = month
            sheet.year = 1

            try:
                sheet.full_clean()
            except ValidationError:
                self.fail(f"Month {month} failed to validate")

    def test_month_min_value(self):
        sheet = models.Sheet()
        sheet.year = 1
        sheet.month = 0
        with self.assertRaises(ValidationError):
            sheet.full_clean()

    def test_month_max_value(self):
        sheet = models.Sheet()
        sheet.year = 1
        sheet.month = 13
        with self.assertRaises(ValidationError):
            sheet.full_clean()

    def test_year_save(self):
        expected_year = random.randint(1980, 2100)

        sheet = models.Sheet()
        sheet.month = 1
        sheet.year = expected_year
        sheet.full_clean()
        sheet.save()

        sheet_from_db = models.Sheet.objects.get(pk=sheet.pk)

        self.assertEqual(expected_year, sheet_from_db.year)

    def test_year_no_negative_values(self):
        sheet = models.Sheet()
        sheet.month = 1
        sheet.year = -1

        with self.assertRaises(IntegrityError):
            sheet.save()

    def test_combination_unique(self):
        sheet_1 = models.Sheet(month=1, year=1)
        sheet_1.full_clean()
        sheet_1.save()

        sheet_2 = models.Sheet(month=1, year=1)
        with self.assertRaises(ValidationError):
            sheet_2.full_clean()

    def test_carryover_save(self):
        expected_value = (Decimal(random.uniform(-999999999.99, 999999999.99))
                          .quantize(Decimal('.01')))

        sheet = models.Sheet(month=6, year=2929)
        sheet.carryover = expected_value
        sheet.full_clean()
        sheet.save()

        sheet_in_db = models.Sheet.objects.get(pk=sheet.pk)

        self.assertEqual(expected_value, sheet_in_db.carryover)

    def test_carryover_max_digits(self):
        expected_value = Decimal('12345678901.23')

        sheet = models.Sheet(month=6, year=2020)
        sheet.carryover = expected_value

        with self.assertRaises(ValidationError):
            sheet.full_clean()

    def test_carryover_decimal_places(self):
        expected_value = Decimal('123456789.123')

        sheet = models.Sheet(month=6, year=2020)
        sheet.carryover = expected_value

        with self.assertRaises(ValidationError):
            sheet.full_clean()

    def test_get_transactions(self):
        sheet = models.Sheet(month=2, year=2020)
        sheet.save()

        transaction_to_expect_1 = _create_transaction(2, 2020)
        transaction_to_expect_2 = _create_transaction(2, 2020)
        transaction_to_expect_3 = _create_transaction(2, 2020)

        _create_transaction(2, 2019)
        _create_transaction(2, 2021)
        _create_transaction(1, 2020)
        _create_transaction(3, 2020)
        _create_transaction(3, 2021)
        _create_transaction(1, 2019)
        _create_transaction(3, 2019)
        _create_transaction(1, 2021)

        expected_transactions = [transaction_to_expect_1,
                                 transaction_to_expect_2,
                                 transaction_to_expect_3]
        actual_transactions = list(sheet.transactions)

        self.assertCountEqual(expected_transactions, actual_transactions)

    def test_available(self):
        sheet = models.Sheet(month=2, year=2020)
        sheet.save()

        transactions = [_create_transaction(2, 2020) for _ in range(10)]
        inflow = sum(trans.value.quantize(Decimal('.01'))
                     for trans in filter(lambda t: t.value > 0, transactions))

        entries = [_create_sheet_entry(sheet)]
        budget = sum(e.value.quantize(Decimal('.01')) for e in entries)

        expected_available = inflow - budget

        self.assertAlmostEqual(expected_available, sheet.available, 2)

    def test_available_with_carryover(self):
        sheet = models.Sheet(month=12, year=2020)
        sheet.save()

        transactions = [_create_transaction(12, 2020) for _ in range(10)]
        inflow = sum(trans.value.quantize(Decimal('.01'))
                     for trans in filter(lambda t: t.value > 0, transactions))

        entries = [_create_sheet_entry(sheet)]
        budget = sum(e.value.quantize(Decimal('.01')) for e in entries)

        previous_sheets = [_create_sheet(month=month, year=2020) for month in range(1, 12)]

        expected_available = inflow - budget + previous_sheets[-1].available

        self.assertAlmostEqual(expected_available, sheet.available, 2)

    def test_available_with_locked_carryover(self):
        sheet = models.Sheet(month=12, year=2020)
        sheet.save()

        transactions = [_create_transaction(12, 2020) for _ in range(10)]
        inflow = sum(trans.value.quantize(Decimal('.01'))
                     for trans in filter(lambda t: t.value > 0, transactions))

        entries = [_create_sheet_entry(sheet)]
        budget = sum(e.value.quantize(Decimal('.01')) for e in entries)

        previous_sheet = models.Sheet(month=11, year=2020)
        previous_sheet.carryover = Decimal(random.uniform(-999.99, 999.99))
        previous_sheet.save()

        for month in range(1, 11):
            _create_sheet(month=month, year=2020)

        expected_available = inflow - budget + previous_sheet.carryover

        self.assertAlmostEqual(expected_available, sheet.available, 2)

    def test_get_previous_exists_same_year(self):
        sheet = models.Sheet(month=2, year=2020)
        sheet.save()

        previous_sheet = models.Sheet(month=1, year=2020)
        previous_sheet.save()

        sheet_in_db = models.Sheet.objects.get(pk=sheet.pk)

        self.assertEqual(previous_sheet, sheet_in_db.previous)

    def test_get_previous_exists_other_year(self):
        sheet = models.Sheet(month=1, year=2020)
        sheet.save()

        previous_sheet = models.Sheet(month=12, year=2019)
        previous_sheet.save()

        sheet_in_db = models.Sheet.objects.get(pk=sheet.pk)

        self.assertEqual(previous_sheet, sheet_in_db.previous)

    def test_get_previous_not_exists(self):
        sheet = models.Sheet(month=1, year=2020)
        sheet.save()

        sheet_in_db = models.Sheet.objects.get(pk=sheet.pk)

        self.assertIsNone(sheet_in_db.previous)

    def test_initialize_entries_on_creation(self):
        expected_categories = [_create_category() for _ in range(10)]

        sheet = models.Sheet(month=2, year=2020)
        sheet.save()

        sheet_in_db = models.Sheet.objects.get(pk=sheet.pk)
        self.assertListEqual(expected_categories,
                             list(map(lambda e: e.category, sheet_in_db.sheetentry_set.all())))
        for entry in sheet_in_db.sheetentry_set.all():
            self.assertEqual(Decimal(0), entry.value)

class SheetEntryTest(TestCase):

    def setUp(self):
        self.sheet = models.Sheet(month=1, year=1)
        self.sheet.save()

        self.category = models.Category(name=_get_random_name())
        self.category.save()

    def test_entry_save(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=0)
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(entry, entry_in_db)

    def test_foreign_key_sheet(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=0)
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(self.sheet, entry_in_db.sheet)

    def test_foreign_key_category(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=0)
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(self.category, entry_in_db.category)

    def test_sheet_cascade(self):
        sheet = models.Sheet(month=2, year=1)
        sheet.save()

        entry = models.SheetEntry(sheet=sheet, category=self.category, value=0)
        entry.save()

        sheet.delete()

        actual_count = models.SheetEntry.objects.filter(pk=entry.pk).count()

        self.assertEqual(0, actual_count)

    def test_category_cascade(self):
        category = models.Category(name="Test")
        category.save()

        entry = models.SheetEntry(sheet=self.sheet, category=category, value=0)
        entry.save()

        category.delete()

        actual_count = models.SheetEntry.objects.filter(pk=entry.pk).count()

        self.assertEqual(0, actual_count)

    def test_value_save(self):
        expected_value = (Decimal(random.uniform(-999999999.99, 999999999.99))
                          .quantize(Decimal('.01')))

        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=expected_value)
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(expected_value, entry_in_db.value)

    def test_value_max_digits(self):
        expected_value = Decimal('12345678901.23')

        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=expected_value)

        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_value_decimal_places(self):
        expected_value = Decimal('123456789.123')

        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=expected_value)

        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_locked(self):
        expected_lock = bool(random.getrandbits(1))

        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=Decimal(0))
        entry.locked = expected_lock
        entry.full_clean()
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(expected_lock, entry_in_db.locked)

    def test_locked_default_false(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=Decimal(0))
        entry.full_clean()
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertFalse(entry_in_db.locked)

    def test_locked_no_change_to_sheet(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=Decimal(0))
        entry.locked = True
        entry.full_clean()
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        new_sheet = models.Sheet(month=1, year=self.sheet.year + 1)
        new_sheet.save()

        entry_in_db.sheet = new_sheet

        with self.assertRaises(ValidationError):
            entry_in_db.full_clean()

    def test_locked_no_change_to_category(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=Decimal(0))
        entry.locked = True
        entry.full_clean()
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        new_category = models.Category(name=_get_random_name())
        new_category.save()

        entry_in_db.category = new_category

        with self.assertRaises(ValidationError):
            entry_in_db.full_clean()

    def test_locked_no_change_to_value(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=Decimal(0))
        entry.locked = True
        entry.full_clean()
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        entry_in_db.value = Decimal(1)

        with self.assertRaises(ValidationError):
            entry_in_db.full_clean()

    def test_created_for_open_sheets_when_category_created(self):
        open_sheets = [_create_sheet(month, 2020) for month in range(1, 13)]
        closed_sheets = [_create_sheet(month, 2021) for month in range(1, 13)]

        for sheet in closed_sheets:
            sheet.carryover = Decimal(random.uniform(-999.99, 999.99))
            sheet.save()

        new_categories = [_create_category() for _ in range(10)]

        for category in new_categories:
            for sheet in open_sheets:
                self.assertEqual(1, models.SheetEntry.objects.filter(category=category,
                                                                     sheet=sheet).count())
            for sheet in closed_sheets:
                self.assertEqual(0, models.SheetEntry.objects.filter(category=category,
                                                                     sheet=sheet).count())

class AccountTest(TestCase):

    def test_name_save(self):
        expected_name = ''.join(random.choices(string.ascii_letters + string.digits, k=200))

        account = models.Account()
        account.name = expected_name
        account.balance = Decimal(0)
        account.full_clean()
        account.save()

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_name, account_in_db.name)

    def test_name_max_value(self):
        expected_name = ''.join(random.choices(string.ascii_letters + string.digits, k=201))

        account = models.Account()
        account.name = expected_name
        account.balanace = 0

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_balance(self):
        expected_balance = (Decimal(random.uniform(-999999999.99, 999999999.99))
                            .quantize(Decimal('.01')))

        account = models.Account()
        account.balance = expected_balance
        account.save()

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_balance, account_in_db.balance)

    def test_balance_max_digits(self):
        balance = Decimal('12345678901.23')

        account = models.Account(name=_get_random_name(), balance=balance)

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_balance_decimal_places(self):
        balance = Decimal('123456789.123')

        account = models.Account(name=_get_random_name(), balance=balance)

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_total_no_transactions(self):
        expected_total = (Decimal(random.uniform(-999999999.99, 999999999.99))
                          .quantize(Decimal('.01')))

        account = models.Account()
        account.balance = expected_total
        account.save()

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_total, account_in_db.total)

    def test_total_only_unlocked_transactions(self):
        starting_balance = (Decimal(random.uniform(-9999.99, 9999.99))
                            .quantize(Decimal('.01')))

        account = models.Account()
        account.balance = starting_balance
        account.save()

        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        transactions = ([_create_transaction(tomorrow.month, tomorrow.year, account)
                         for _ in range(1)])

        expected_total = ((starting_balance + sum(Decimal(t.value) for t in transactions))
                          .quantize(Decimal('.01')))

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_total, account_in_db.total)

    def test_total_ignore_other_accounts(self):
        #pylint: disable=unused-variable
        starting_balance = Decimal(random.uniform(-9999.99, 9999.99)).quantize(Decimal('.01'))

        account = models.Account()
        account.balance = starting_balance
        account.save()

        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        transactions = ([_create_transaction(tomorrow.month, tomorrow.year, account)
                         for _ in range(10)])
        for _ in range(10):
            _create_transaction(tomorrow.month, tomorrow.year, account, locked=True)

        expected_total = ((starting_balance + sum(Decimal(t.value) for t in transactions))
                          .quantize(Decimal('.01')))

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertAlmostEqual(expected_total, account_in_db.total, 2)

class TransactionTest(TestCase):

    def setUp(self):
        self.category = models.Category(name="Test")
        self.category.save()
        self.account = models.Account(name="Test", balance=Decimal(0))
        self.account.save()

    def test_partner_save(self):
        expected_name = ''.join(random.choices(string.ascii_letters + string.digits, k=200))

        transaction = models.Transaction()
        transaction.partner = expected_name
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_name, transaction_in_db.partner)

    def test_partner_max_length(self):
        expected_name = ''.join(random.choices(string.ascii_letters + string.digits, k=201))

        transaction = models.Transaction()
        transaction.partner = expected_name
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_date_save(self):
        expected_date = datetime.date(random.randrange(1980, 2100),
                                      random.randrange(1, 12),
                                      random.randrange(1, 28))

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = expected_date
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_date,
                         transaction_in_db.date)

    def test_value_save(self):
        expected_value = (Decimal(random.uniform(-999999999.99, 999999999.99))
                          .quantize(Decimal('.01')))

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = expected_value
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_value, transaction_in_db.value)

    def test_value_max_digits(self):
        expected_value = Decimal('12345678901.23')

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = expected_value
        transaction.category = self.category
        transaction.account = self.account

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_value_decimal_places(self):
        expected_value = Decimal('123456789.123')

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = expected_value
        transaction.category = self.category
        transaction.account = self.account

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_category(self):
        expected_category = models.Category(name="Expected category")
        expected_category.save()

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = expected_category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_category, transaction_in_db.category)

    def test_category_must_be_set(self):

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = None
        transaction.account = self.account

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_category_prevent_deletion(self):
        category = models.Category(name="Expected category")
        category.save()

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        with self.assertRaises(ProtectedError):
            category.delete()

    def test_account(self):
        expected_account = models.Account(name="Expected account", balance=Decimal(0))
        expected_account.save()

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = expected_account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_account, transaction_in_db.account)

    def test_account_must_be_net(self):

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = None

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_account_prevent_deletion(self):
        account = models.Account(name="Expected account", balance=Decimal(0))
        account.save()

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = account
        transaction.full_clean()
        transaction.save()

        with self.assertRaises(ProtectedError):
            account.delete()

    def test_locked(self):
        expected_lock = bool(random.getrandbits(1))

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.locked = expected_lock
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.full_clean()
        self.assertEqual(expected_lock, transaction_in_db.locked)

    def test_locked_default_false(self):
        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertFalse(transaction_in_db.locked)

    def test_locked_no_change_to_partner(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.partner = "b"

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

    def test_locked_no_change_to_date(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.date = datetime.date.today() + datetime.timedelta(days=1)

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

    def test_locked_no_change_to_value(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.value = 1

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

    def test_locked_no_change_to_category(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        category = models.Category(name=_get_random_name())
        category.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.category = category

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

    def test_locked_no_change_to_account(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        account = models.Account(name=_get_random_name(), balance=0)
        account.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.account = account

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

def _create_transaction(month, year, account=None, locked=False) -> models.Transaction:
    category = models.Category(name=_get_random_name())
    category.save()
    if account is None:
        account = models.Account(name=_get_random_name(), balance=Decimal(0))
        account.save()

    transaction = models.Transaction()
    transaction.category = category
    transaction.account = account
    transaction.value = Decimal(random.uniform(-999.99, 999.99))
    transaction.partner = "Test partner"
    transaction.locked = locked
    transaction.date = _random_day_in_month(month, year)

    transaction.save()
    return transaction

def _create_sheet_entry(sheet) -> models.SheetEntry:
    category = models.Category(name=_get_random_name())
    category.save()

    entry = models.SheetEntry()
    entry.sheet = sheet
    entry.value = Decimal(random.uniform(-999.99, 999.99))
    entry.category = category
    entry.save()

    return entry

def _random_day_in_month(month, year):
    dates = calendar.Calendar().itermonthdates(year, month)
    return random.choice([date for date in dates if date.month == month])

def _create_sheet(month, year) -> models.Sheet:
    sheet = models.Sheet(month=month, year=year)
    sheet.save()

    for _ in range(10):
        _create_transaction(month, year)
        _create_sheet_entry(sheet)

    return sheet

def _create_category() -> models.Category:
    category = models.Category(name=_get_random_name())
    category.save()
    return category

def _get_random_name() -> string:
    return "".join(random.choice(string.ascii_letters) for _ in range(10))
