from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("directory.urls")),
    path("api/v1/", include("operations.urls")),
    path("api/v1/", include("communications.urls")),
]

if settings.DEBUG:
    urlpatterns.append(path("django-admin/", admin.site.urls))
