from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .models import *
from .database import db_manager
import asyncio
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.paginator import Paginator


@login_required
def dashboard(request):
    """Главная панель"""
    context = {
        'total_bans': Ban.objects.count(),
        'total_moderators': Moderator.objects.count(),
        'total_chats': ChatSetting.objects.count(),
        'recent_punishments': Punishment.objects.select_related().order_by('-timestamp')[:10]
    }
    return render(request, 'moderator/dashboard.html', context)


@login_required
def users_list(request):
    """Список пользователей с поиском"""
    search_query = request.GET.get('search', '')
    users = TelegramUser.objects.all()

    if search_query:
        users = users.filter(
            username__icontains=search_query
        ) | users.filter(
            first_name__icontains=search_query
        ) | users.filter(
            user_id=search_query if search_query.isdigit() else 0
        )

    paginator = Paginator(users, 50)
    page = request.GET.get('page')
    users = paginator.get_page(page)

    context = {
        'users': users,
        'search_query': search_query
    }
    return render(request, 'moderator/users_list.html', context)


@login_required
def user_detail(request, user_id):
    """Детальная информация о пользователе"""
    user = TelegramUser.objects.filter(user_id=user_id).first()
    warnings = Warning.objects.filter(user_id=user_id)
    bans = Ban.objects.filter(user_id=user_id)
    punishments = Punishment.objects.filter(user_id=user_id).order_by('-timestamp')

    context = {
        'user': user,
        'warnings': warnings,
        'bans': bans,
        'punishments': punishments,
        'is_moderator': Moderator.objects.filter(user_id=user_id).exists()
    }
    return render(request, 'moderator/user_detail.html', context)


@login_required
def moderation_actions(request):
    """Страница модераторских действий"""
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = int(request.POST.get('user_id'))
        chat_id = int(request.POST.get('chat_id', 0))
        reason = request.POST.get('reason', 'No reason provided')
        duration = request.POST.get('duration')

        # Здесь будет асинхронный вызов функций бота
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            if action == 'ban':
                loop.run_until_complete(db_manager.add_ban(user_id, chat_id, reason))
                loop.run_until_complete(db_manager.add_punishment(
                    user_id, chat_id, 'ban', reason, request.user.id
                ))
                messages.success(request, f'User {user_id} banned successfully')

            elif action == 'warn':
                warn_count = loop.run_until_complete(db_manager.add_warning(user_id, chat_id))
                loop.run_until_complete(db_manager.add_punishment(
                    user_id, chat_id, 'warn', reason, request.user.id
                ))
                messages.success(request, f'Warning added. Total warnings: {warn_count}')

            elif action == 'mute':
                duration_minutes = int(duration) if duration else 60
                loop.run_until_complete(db_manager.add_punishment(
                    user_id, chat_id, 'mute', reason, request.user.id, duration_minutes
                ))
                messages.success(request, f'User {user_id} muted for {duration_minutes} minutes')

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        finally:
            loop.close()

        return redirect('moderation_actions')

    return render(request, 'moderator/moderation_actions.html')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_ban_user(request):
    """API для бана пользователя"""
    user_id = request.data.get('user_id')
    chat_id = request.data.get('chat_id')
    reason = request.data.get('reason', 'No reason provided')

    if not user_id or not chat_id:
        return Response({'error': 'user_id and chat_id are required'},
                        status=status.HTTP_400_BAD_REQUEST)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(db_manager.add_ban(int(user_id), int(chat_id), reason))
        loop.run_until_complete(db_manager.add_punishment(
            int(user_id), int(chat_id), 'ban', reason, request.user.id
        ))
        return Response({'success': True, 'message': 'User banned successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        loop.close()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_user_info(request, user_id):
    """API для получения информации о пользователе"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        punishments = loop.run_until_complete(db_manager.get_user_punishments(int(user_id)))
        is_moderator = loop.run_until_complete(db_manager.is_moderator(int(user_id)))

        return Response({
            'user_id': user_id,
            'is_moderator': is_moderator,
            'punishments': punishments
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        loop.close()


@login_required
def analytics(request):
    """Страница аналитики"""
    days = int(request.GET.get('days', 30))
    chat_id = request.GET.get('chat_id')

    # Статистика по типам наказаний
    punishments_data = Punishment.objects.filter(
        timestamp__gte=timezone.now() - timedelta(days=days)
    )

    if chat_id:
        punishments_data = punishments_data.filter(chat_id=int(chat_id))

    punishment_stats = {}
    for punishment in punishments_data:
        punishment_stats[punishment.punishment_type] = punishment_stats.get(punishment.punishment_type, 0) + 1

    # Топ модераторов
    top_moderators = (punishments_data
                      .values('moderator_id')
                      .annotate(count=models.Count('id'))
                      .order_by('-count')[:10])

    context = {
        'punishment_stats': punishment_stats,
        'top_moderators': top_moderators,
        'days': days,
        'selected_chat_id': chat_id
    }

    return render(request, 'moderator/analytics.html', context)


@login_required
def settings_view(request):
    """Настройки чатов"""
    if request.method == 'POST':
        chat_id = int(request.POST.get('chat_id'))
        filter_enabled = request.POST.get('filter_enabled') == 'on'

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(db_manager.set_filter_status(chat_id, filter_enabled))
            messages.success(request, f'Settings updated for chat {chat_id}')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        finally:
            loop.close()

        return redirect('settings')

    chat_settings = ChatSetting.objects.all()
    context = {'chat_settings': chat_settings}
    return render(request, 'moderator/settings.html', context)