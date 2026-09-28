from django.urls import path

from .views import MyFamilyView

urlpatterns = [path("my-family/", MyFamilyView.as_view(), name="portal-my-family")]
