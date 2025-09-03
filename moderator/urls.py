from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

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
    path('telegram_auth/', views.telegram_auth, name='telegram_auth'),

    # API endpoints
    path('api/', include(router.urls)),
    path('api/ban/', views.api_ban_user, name='api_ban_user'),
    path('api/user/<int:user_id>/', views.api_user_info, name='api_user_info'),
    path('chat/<str:chat_id>/settings/', views.edit_chat_settings, name='edit_chat_settings'),
    path('settings/bulk_filter/<str:action>/', views.bulk_filter_toggle, name='bulk_filter_toggle'),

    path('telegram_auth/', views.telegram_auth, name='telegram_auth'),
    path('tg-test/', views.tg_login_test, name='tg_login_test'),  # ДОДАНО: тестова сторінка
    path('api/', include(router.urls)),
]