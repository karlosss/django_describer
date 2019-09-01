# django_describer

An easy-to-use tool to auto-generate GraphQL API from Django models. More APIs TBD.

## Get started

- Install `django_describer` via PyPI, e. g. `pip install django_describer`.
- Add `graphene_django` to your `INSTALLED_APPS` in Django settings. Otherwise, the template for GraphQL would be invisible.

## Usage

Write your Django models:

```python
from django.db import models


class Publisher(models.Model):
    name = models.CharField(max_length=50)

    @property
    def short_books(self):
        return self.books.all().filter(page_count__lt=300)

    def __str__(self):
        return self.name


class Book(models.Model):
    name = models.CharField(max_length=50)
    page_count = models.IntegerField()
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, blank=True, null=True, related_name="books")

    def __str__(self):
        return "{} ({})".format(self.name, self.publisher)
```

Now write a Describer for it. You can specify:

- which fields (and model properties) are exposed to the API and who can access them
- which CRUD operations are allowed for each model and who can perform them
- extra actions on each model

Per-request field specification, ordering, filtering and pagination are for granted.

```python
from django_describer.actions import DetailAction
from django_describer.datatypes import QuerySet
from django_describer.describers import Describer
from django_describer.permissions import IsAuthenticated

from user.models import User


class UserDescriber(Describer):
    model = User

    extra_actions = {
        "myself": DetailAction(permissions=IsAuthenticated, fetch_fn=lambda request, pk: request.user, id_arg=False)
    }
```

Import all describers into your `urls.py` and create a URL for the api:

```python
from django.contrib import admin
from django.urls import path
from django_describer.adapters.base import generate
from django_describer.adapters.graphql.main import GraphQL

from course.describers import *
from user.describers import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path("graphql/", generate(GraphQL)),
]
```

Now you can do things such as:

```
query q{
  UserMyself{
    id
    username
  }
}

mutation m{
  UserCreate(data: {username: "John", password: "asdf"}){
    object{
      id
    }
  }
}
```
