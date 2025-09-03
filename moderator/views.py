from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

import asyncio
import json
import hmac
import hashlib
import time  # ВАЖЛИВО: використовуємо stdlib time
from datetime import datetime, timedelta  # НЕ імпортуємо `time` звідси!

from .models import *
from .database import db_manager, ModerationTask

import logging
logger = logging.getLogger(__name__)

# --- Telegram Auth Widget ---

TELEGRAM_BOT_TOKEN = getattr(settings, "TELEGRAM_BOT_TOKEN", None)

def check_telegram_auth(querydict, bot_token):
    """
    Перевірка автентичності даних Telegram Login Widget (згідно з офіційною документацією).
    """
    if not bot_token:
        return False

    # Витягуємо РЯДКОВІ значення з QueryDict
    data = {k: querydict.get(k) for k in querydict.keys()}

    received_hash = data.pop('hash', '')
    if not received_hash:
        return False

    # Формуємо data_check_string: сортуємо саме за КЛЮЧАМИ
    parts = []
    for k in sorted(data.keys()):
        v = data[k]
        if v is not None:
            parts.append(f"{k}={v}")
    data_check_string = "\n".join(parts)

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    my_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    # Перевірка "свіжості" підпису (рекомендовано Telegram)
    try:
        auth_ts = int(data.get('auth_date', '0'))
        # 86400 секунд = 24 години
        if abs(int(time.time()) - auth_ts) > 86400:
            return False
    except Exception:
        # Якщо не змогли прочитати auth_date — не валимо, але краще логувати
        pass

    logger.info("Checking Telegram signature: %s", data)
    logger.info("Calculated hash: %s, Received: %s", my_hash, received_hash)

    # Constant-time порівняння
    return hmac.compare_digest(my_hash, received_hash)


@xframe_options_exempt
def tg_login_test(request):
    html = """
<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8" />
  <title>Telegram Login Test (debug)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Arial, sans-serif; padding: 20px; }
    pre { background: #f6f8fa; padding: 12px; border-radius: 8px; overflow: auto; max-height: 280px; }
    .row { margin: 12px 0; }
    button { padding: 10px 16px; font-size: 14px; }
    code { background: #eee; padding: 0 4px; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Telegram Login Test (debug)</h1>

  <ol>
    <li>Увійдіть у <a href="https://web.telegram.org/" target="_blank" rel="noopener">Telegram Web</a> у цьому браузері.</li>
    <li>Переконайтесь, що в <a href="https://t.me/QuantRPModerator_bot" target="_blank" rel="noopener">чаті з ботом</a> натиснуто <strong>Start</strong>.</li>
    <li>Дозвольте попапи і third‑party cookies для <code>*.telegram.org</code>.</li>
  </ol>

  <div class="row">
    <script>
      // Додаткове логування подій від попапа Telegram
      function log(msg, obj) {
        const el = document.getElementById('log');
        const line = document.createElement('div');
        line.textContent = '[LOG] ' + msg + (obj ? ' ' + JSON.stringify(obj) : '');
        el.appendChild(line);
      }

      window.addEventListener('message', (e) => {
        const rec = {origin: e.origin, data: e.data};
        log('window.message', rec);
      });

      window.onerror = function(message, source, lineno, colno, error) {
        const info = {message, source, lineno, colno};
        log('window.onerror', info);
      };

      function onTelegramAuth(user) {
        const out = document.getElementById('out');
        out.textContent = JSON.stringify(user, null, 2);
        window.__tgUser = user;
        document.getElementById('go-backend').disabled = false;
        log('onTelegramAuth fired', user);
      }
    </script>

    <script async src="https://telegram.org/js/telegram-widget.js?7"
            data-telegram-login="QuantRPModerator_bot"
            data-size="large"
            data-userpic="false"
            data-auth-url="https://quantrpmoderatordjango.onrender.com/telegram_auth/"
            data-onauth="onTelegramAuth(user)">
    </script>
  </div>

  <div class="row">
    <button id="go-backend" disabled onclick="
      try {
        const user = window.__tgUser || {};
        const params = new URLSearchParams(user);
        const url = 'https://quantrpmoderatordjango.onrender.com/telegram_auth/?' + params.toString();
        window.location.href = url;
      } catch (e) { console.error(e); alert('Помилка побудови URL'); }
    ">Продовжити → бекенд (/telegram_auth)</button>
  </div>

  <div class="row">
    <strong>user (з Telegram):</strong>
    <pre id="out">Натисніть кнопку Telegram вище…</pre>
  </div>

  <hr />
  <div class="row">
    <strong>Живий лог подій:</strong>
    <div id="log" style="background:#fff;border:1px solid #ddd;border-radius:8px;padding:8px;min-height:80px;"></div>
  </div>

  <hr />
  <div class="row">
    <strong>Пряме посилання на OAuth (для тесту):</strong><br/>
    <a id="oauth-link" href="#" target="_blank" rel="noopener">Відкрити OAuth вручну</a>
    <script>
      // BOT ID з getMe: 7797651194
      const origin = 'https://quantrpmoderatordjango.onrender.com';
      const oauth = 'https://oauth.telegram.org/auth?bot_id=7797651194&origin=' + encodeURIComponent(origin);
      document.getElementById('oauth-link').href = oauth;
    </script>
    <div style="font-size:12px;color:#666;margin-top:6px;">
      Якщо при кліку попап відкривається і миттєво закривається, але тут немає подій <code>onTelegramAuth</code> чи <code>window.message</code> — це майже завжди блокування попапів/кукі або неактивний чат із ботом (нема Start).
    </div>
  </div>
</body>
</html>
"""
    return HttpResponse(html)


@csrf_exempt
@require_http_methods(["GET"])
def telegram_auth(request):
    logger.info("Telegram login requested: %s", request.GET.dict())

    # Перевірка підпису Telegram
    valid_signature = check_telegram_auth(request.GET, TELEGRAM_BOT_TOKEN)
    logger.info("Signature valid: %s", valid_signature)
    if not valid_signature:
        logger.warning("Auth failed for data: %s", request.GET.dict())
        return HttpResponse("Auth failed", status=403)

    try:
        telegram_id = int(request.GET.get('id', '0'))
    except (TypeError, ValueError):
        logger.error("Could not parse telegram_id from: %s", request.GET.get('id'))
        return HttpResponse("Bad request", status=400)
    logger.info("Parsed telegram_id: %s", telegram_id)

    username = request.GET.get('username')
    first_name = request.GET.get('first_name')
    last_name = request.GET.get('last_name')
    logger.info("Username: %s, First name: %s, Last name: %s", username, first_name, last_name)

    moderator = Moderator.objects.filter(user_id=telegram_id).first()
    logger.info("Moderator found: %s", bool(moderator))
    if moderator:
        from django.contrib.auth.models import User
        user, created = User.objects.get_or_create(username=str(telegram_id))
        logger.info("Django User created: %s, User ID: %s", created, user.id)
        user.first_name = first_name or ""
        user.last_name = last_name or ""
        user.save()
        login(request, user)
        logger.info("User logged in: %s", user.username)
        return redirect('profile')
    else:
        logger.warning("Access denied for telegram_id: %s", telegram_id)
        return HttpResponse("Вам доступ заборонено", status=403)

@login_required
def profile(request):
    """Профіль модератора з його покараннями"""
    username = request.user.username

    moderator = Moderator.objects.filter(username=username).first()
    punishments = None

    if moderator:
        punishments = Punishment.objects.filter(moderator_id=moderator.user_id).order_by('-timestamp')
    else:
        try:
            telegram_id = int(username)
            moderator = Moderator.objects.filter(user_id=telegram_id).first()
            if moderator:
                punishments = Punishment.objects.filter(moderator_id=telegram_id).order_by('-timestamp')
        except ValueError:
            moderator = None
            punishments = Punishment.objects.none()

    # Мапа chat_id -> chat_title
    chat_titles = {str(cs.chat_id): cs.chat_title for cs in ChatSetting.objects.all()}

    context = {
        'moderator': moderator,
        'punishments': punishments,
        'chat_titles': chat_titles,
    }
    return render(request, 'moderator/profile.html', context)

@login_required
def dashboard(request):
    """Главная панель"""
    recent_punishments_all = Punishment.objects.order_by('-timestamp')
    paginator = Paginator(recent_punishments_all, 20)
    page = request.GET.get('page')
    recent_punishments = paginator.get_page(page)

    # Отримати всі user_id, які є у покараннях на поточній сторінці
    user_ids = [p.user_id for p in recent_punishments]
    # Створити словник user_id -> TelegramUser об'єкт
    user_map = {u.user_id: u for u in TelegramUser.objects.filter(user_id__in=user_ids)}

    moderator_map = {
        m.user_id: (m.username if m.username else str(m.user_id))
        for m in Moderator.objects.all()
    }

    context = {
        'total_bans': Ban.objects.count(),
        'total_moderators': Moderator.objects.count(),
        'total_chats': ChatSetting.objects.count(),
        'recent_punishments': recent_punishments,
        'moderator_map': moderator_map,
        'user_map': user_map,
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

    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    users = paginator.get_page(page)

    # Ось це потрібно!
    moderators_list = list(Moderator.objects.values_list('user_id', flat=True))

    context = {
        'users': users,
        'search_query': search_query,
        'moderators': moderators_list,  # Передаємо список ID
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
    """Страница модераторских действий: наказания и их отмена"""

    chats = ChatSetting.objects.all()  # Для выпадающего списка чатов

    # Дістаємо Telegram ID модератора
    try:
        telegram_id = int(request.user.username)
        moderator = Moderator.objects.filter(user_id=telegram_id).first()
    except Exception:
        moderator = Moderator.objects.filter(username=request.user.username).first()
        telegram_id = moderator.user_id if moderator else None

    if request.method == 'POST':
        # Основная форма наказания
        if 'action' in request.POST and 'user_id' in request.POST and 'chat_id' in request.POST:
            action = request.POST.get('action')
            user_id = int(request.POST.get('user_id'))
            chat_id = int(request.POST.get('chat_id', 0))
            reason = request.POST.get('reason', 'No reason provided')
            duration = request.POST.get('duration')

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                if action == 'ban':
                    loop.run_until_complete(db_manager.add_ban(user_id, chat_id, reason))
                    loop.run_until_complete(db_manager.add_punishment(
                        user_id, chat_id, 'ban', reason, telegram_id
                    ))
                    messages.success(request, f'User {user_id} banned successfully')

                elif action == 'warn':
                    warn_count = loop.run_until_complete(db_manager.add_warning(user_id, chat_id))
                    loop.run_until_complete(db_manager.add_punishment(
                        user_id, chat_id, 'warn', reason, telegram_id
                    ))
                    messages.success(request, f'Warning added. Total warnings: {warn_count}')

                elif action == 'mute':
                    duration_minutes = int(duration) if duration else 60
                    loop.run_until_complete(db_manager.add_punishment(
                        user_id, chat_id, 'mute', reason, telegram_id, duration_minutes
                    ))
                    messages.success(request, f'User {user_id} muted for {duration_minutes} minutes')

                elif action == 'kick':
                    loop.run_until_complete(db_manager.add_punishment(
                        user_id, chat_id, 'kick', reason, telegram_id
                    ))
                    messages.success(request, f'User {user_id} kicked')

                # Формируем ModerationTask для воркера
                task = ModerationTask(
                    task_type=action,
                    user_id=user_id,
                    username=None,
                    reason=reason,
                    chat_id=chat_id,
                    moderator_id=telegram_id,
                    duration_minutes=int(duration) if action == 'mute' and duration else None
                )
                db_manager.add_to_queue(task)

            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
            finally:
                loop.close()

            return redirect('moderation_actions')

        # Форма отмены наказания
        elif 'remove_action' in request.POST and 'user_id' in request.POST and 'chat_id' in request.POST:
            action = request.POST.get('remove_action')  # unban, unmute, unwarn
            user_id = int(request.POST.get('user_id'))
            chat_id = int(request.POST.get('chat_id'))

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Формируем ModerationTask для отмены наказания
                task = ModerationTask(
                    task_type=action,
                    user_id=user_id,
                    username=None,
                    reason=None,
                    chat_id=chat_id,
                    moderator_id=request.user.id,
                    duration_minutes=None
                )
                db_manager.add_to_queue(task)

                # Для unwarn — удаляем предупреждение в БД
                if action == 'unwarn':
                    loop.run_until_complete(db_manager.remove_warning(user_id, chat_id))
                    messages.success(request, f'Warning removed from user {user_id}')
                elif action == 'unban':
                    loop.run_until_complete(db_manager.remove_ban(user_id, chat_id))
                    messages.success(request, f'Ban removed from user {user_id}')
                elif action == 'unmute':
                    loop.run_until_complete(db_manager.remove_mute(user_id, chat_id))
                    messages.success(request, f'Mute removed from user {user_id}')
                else:
                    messages.success(request, f'Action {action} queued for user {user_id}')

            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
            finally:
                loop.close()

            return redirect('moderation_actions')

    return render(request, 'moderator/moderation_actions.html', {'chats': chats})

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


@login_required
def edit_chat_settings(request, chat_id):
    chat = ChatSetting.objects.filter(chat_id=chat_id).first()
    if not chat:
        return HttpResponse("Чат не знайдено", status=404)

    if request.method == 'POST':
        # Перемикаємо фільтр
        chat.filter_enabled = not chat.filter_enabled
        chat.save()
        messages.success(request, f"Фільтр для чату оновлено: {'Увімкнено' if chat.filter_enabled else 'Вимкнено'}")
        return redirect('settings')

    return render(request, 'moderator/edit_chat_settings.html', {'chat': chat})

@login_required
def bulk_filter_toggle(request, action):
    if action == 'enable':
        ChatSetting.objects.update(filter_enabled=True)
        messages.success(request, "Фільтр слів увімкнено у всіх чатах!")
    elif action == 'disable':
        ChatSetting.objects.update(filter_enabled=False)
        messages.success(request, "Фільтр слів вимкнено у всіх чатах!")
    else:
        messages.error(request, "Некоректна дія.")
    return redirect('settings')