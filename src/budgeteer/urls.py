"""
Budgeteer main app URL configuration
"""
from django.contrib import admin
from django.urls import path

import budgeteer.views as views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('account/view/<int:id>', views.AccountOverview.as_view(), name="account-view"),
    path('account/list', views.AccountList.as_view(), name="account-list")
]
