from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test
from .models import Moderator
import random
import string


def is_superuser(user):
    """Перевірка, чи користувач є суперкористувачем"""
    return user.is_superuser


@user_passes_test(is_superuser)
def manage_moderators(request):
    """Сторінка управління модераторами"""
    moderators = Moderator.objects.all()

    context = {
        'moderators': moderators,
    }
    return render(request, 'moderator/manage_moderators.html', context)


@user_passes_test(is_superuser)
def create_moderator(request):
    """Створення нового модератора"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        username = request.POST.get('username')

        # Перевірка чи вже існує модератор з таким ID
        if Moderator.objects.filter(user_id=user_id).exists():
            messages.error(request, f'Модератор з ID {user_id} вже існує')
            return redirect('create_moderator')

        # Створення модератора в таблиці модераторів
        moderator = Moderator(user_id=user_id, username=username)
        moderator.save()

        # Створення облікового запису Django для модератора
        # Генерація випадкового паролю
        password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))

        # Створення користувача Django (не суперкористувача)
        user = User.objects.create_user(
            username=username,
            password=password,
            is_staff=False,
            is_superuser=False
        )

        messages.success(request, f'Модератор {username} створений успішно. Пароль: {password}')
        return redirect('manage_moderators')

    return render(request, 'moderator/create_moderator.html')


@user_passes_test(is_superuser)
def delete_moderator(request, user_id):
    """Видалення модератора"""
    try:
        moderator = Moderator.objects.get(user_id=user_id)
        username = moderator.username

        # Видалення модератора з таблиці модераторів
        moderator.delete()

        # Спроба видалити відповідний обліковий запис Django
        try:
            user = User.objects.get(username=username)
            user.delete()
        except User.DoesNotExist:
            pass

        messages.success(request, f'Модератор {username} видалений')
    except Moderator.DoesNotExist:
        messages.error(request, f'Модератор з ID {user_id} не знайдений')

    return redirect('manage_moderators')