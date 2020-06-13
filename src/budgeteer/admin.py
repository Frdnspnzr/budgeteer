from django.contrib import admin
from budgeteer.models import Account, Category, Sheet, SheetEntry, Transaction

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    pass

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass

@admin.register(Sheet)
class SheetAdmin(admin.ModelAdmin):
    pass

@admin.register(SheetEntry)
class SheetEntryAdmin(admin.ModelAdmin):
    pass

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    pass
