"""
Budgeteer main app views
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic.list import ListView

from budgeteer.models import Account, Transaction


class AccountOverview(LoginRequiredMixin, ListView):
    """
    Shows all transactions and account information for a single account.
    """
    template_name = "pages/account/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = Account.objects.get(pk=self.kwargs['id'])
        return context

    def get_queryset(self):
        account = get_object_or_404(Account, pk=self.kwargs['id'])
        return Transaction.objects.filter(account=account).order_by("-date")

class AccountList(LoginRequiredMixin, ListView):
    """
    Shows a list of all accounts.
    """
    model = Account
    template_name = "pages/account/list.html"
