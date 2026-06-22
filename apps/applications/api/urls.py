from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# 1. Core Application Management (CRUD + custom actions)
router.register(r'applications', views.ApplicationViewSet, basename='application')

urlpatterns = [
    # Include base router URLs
    path('', include(router.urls)),
]