from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

urlpatterns = [
    # Web интерфейс
    path('', views.dashboard, name='dashboard'),
    path('users/', views.users_list, name='users_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('moderation/', views.moderation_actions, name='moderation_actions'),
    path('analytics/', views.analytics, name='analytics'),
    path('settings/', views.settings_view, name='settings'),

    # API endpoints
    path('api/', include(router.urls)),
    path('api/ban/', views.api_ban_user, name='api_ban_user'),
    path('api/user/<int:user_id>/', views.api_user_info, name='api_user_info'),
]
