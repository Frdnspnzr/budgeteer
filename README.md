# Budgeteer - The opinionated personal finance helper

[![Build Status](https://travis-ci.org/Friedenspanzer/budgeteer.svg?branch=master)](https://travis-ci.org/Friedenspanzer/budgeteer)

## Installing

### The Easy Way

Currently there is no easy way.
As budgeteer is in heavy development the main focus is not fast deployment but making the software itself better.
This however is a long term goal and should change at some point in the future.

### The Hard Way

Budgeteer is a simple [Django](https://www.djangoproject.com/) application.
It can be hooked up to any webserver supporting WSGI or ASGI (eg. Gunicorn or Daphne).
See [Deploying Django](https://docs.djangoproject.com/en/3.0/howto/deployment/) in the Django documentation for extensive documentation.

## Planned features

Currently the main focus is a better user interface for the core features:

  * Edit and add transactions on the overview screen
  * Easier mass locking of transactions
  * Re-categorization of existing transactions to allow category deletion
  * Automatically lock old sheets to keep system performance up

After that, some planned features are:

  * Recurring transactions
  * Statistics
  * Automatic import from various banking systems
  * Budget targets like monthly amounts, total amounts, etc
  * Purchase budgeting as transient budgets sitting below categories
  * Project budgeting as overarching budgets spanning multiple categories