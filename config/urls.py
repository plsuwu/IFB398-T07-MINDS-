from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path("auth/login/", auth_views.LoginView.as_view(), name="login"),
    path("auth/logout/", auth_views.LogoutView.as_view(next_page="/auth/login/"), name="logout"),
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
]
