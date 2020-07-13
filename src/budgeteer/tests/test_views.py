"""
Unit tests for the budgeteer main app views.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

import budgeteer.models as models

#pylint: disable=missing-function-docstring
#pylint: disable=missing-class-docstring

class AccountOverviewTest(TestCase):
    fixtures = ["test_data.json"]

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('test', 'test@test.zz', 'testpassword')

    def test_reachable(self):
        self.__login()
        response = self.client.get(reverse('account-view', args=[1]))
        self.assertEqual(response.status_code, 200)

    def test_prevents_not_logged_in_user(self):
        response = self.client.get(reverse('account-view', args=[1]))
        self.assertEqual(response.status_code, 302)

    def test_contains_account_info(self):
        self.__login()
        response = self.client.get(reverse('account-view', args=[1]))
        self.assertEqual(models.Account.objects.get(pk=1), response.context['account'])

    def test_contains_ordered_transactions_of_account(self):
        self.__login()
        response = self.client.get(reverse('account-view', args=[1]))
        self.assertListEqual(
            list(models.Transaction.objects.filter(account__pk=1).order_by('-date')),
            list(response.context['object_list'])
        )

    def test_404_on_unknown_account(self):
        self.__login()
        response = self.client.get(reverse('account-view', args=[1234]))
        self.assertEqual(response.status_code, 404)

    def __login(self):
        self.client.login(username='test', password='testpassword')

class AccountListTest(TestCase):
    fixtures = ["test_data.json"]

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('test', 'test@test.zz', 'testpassword')

    def test_reachable(self):
        self.__login()
        response = self.client.get(reverse('account-list'))
        self.assertEqual(response.status_code, 200)

    def test_prevents_not_logged_in_user(self):
        response = self.client.get(reverse('account-list'))
        self.assertEqual(response.status_code, 302)

    def test_contains_all_accounts(self):
        self.__login()
        response = self.client.get(reverse('account-list'))
        self.assertListEqual(
            list(models.Account.objects.all()),
            list(response.context['object_list'])
        )

    def __login(self):
        self.client.login(username='test', password='testpassword')
