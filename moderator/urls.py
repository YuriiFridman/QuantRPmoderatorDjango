from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import admin_views

router = DefaultRouter()

urlpatterns = [
    # Web інтерфейс
    path('', views.dashboard, name='dashboard'),
    path('users/', views.users_list, name='users_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('moderation/', views.moderation_actions, name='moderation_actions'),
    path('analytics/', views.analytics, name='analytics'),
    path('settings/', views.settings_view, name='settings'),
    path('profile/', views.profile, name='profile'),
    path('moderator-profile/<int:moderator_id>/', views.profile, name='moderator_profile'),

    # Адміністративні URL для управління модераторами
    path('manage-moderators/', admin_views.manage_moderators, name='manage_moderators'),
    path('create-moderator/', admin_views.create_moderator, name='create_moderator'),
    path('delete-moderator/<int:user_id>/', admin_views.delete_moderator, name='delete_moderator'),
    path('create-django-user/<int:user_id>/', admin_views.create_django_user, name='create_django_user'),
    path('reset-password/<int:user_id>/', admin_views.reset_password, name='reset_password'),

    # API endpoints
    path('api/', include(router.urls)),
    path('api/ban/', views.api_ban_user, name='api_ban_user'),
    path('api/user/<int:user_id>/', views.api_user_info, name='api_user_info'),
    path('chat/<str:chat_id>/settings/', views.edit_chat_settings, name='edit_chat_settings'),
    path('settings/bulk_filter/<str:action>/', views.bulk_filter_toggle, name='bulk_filter_toggle'),
]