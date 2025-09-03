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
    # Отримуємо всіх модераторів з таблиці moderators
    moderators = Moderator.objects.all()

    # Для кожного модератора перевіряємо, чи є відповідний обліковий запис Django
    moderators_data = []
    for moderator in moderators:
        django_user_exists = User.objects.filter(username=moderator.username).exists() if moderator.username else False
        moderators_data.append({
            'moderator': moderator,
            'django_user_exists': django_user_exists
        })

    context = {
        'moderators_data': moderators_data,
    }
    return render(request, 'moderator/manage_moderators.html', context)


@user_passes_test(is_superuser)
def create_moderator(request):
    """Створення нового модератора"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        username = request.POST.get('username')
        create_django_user = request.POST.get('create_django_user') == 'on'
        password = request.POST.get('password') if create_django_user else None

        # Перевірка чи вже існує модератор з таким ID
        if Moderator.objects.filter(user_id=user_id).exists():
            messages.error(request, f'Модератор з ID {user_id} вже існує')
            return redirect('create_moderator')

        # Перевірка чи вже існує користувач Django з таким username
        if create_django_user and User.objects.filter(username=username).exists():
            messages.error(request, f'Користувач Django з іменем {username} вже існує')
            return redirect('create_moderator')

        # Створення модератора в таблиці модераторів
        moderator = Moderator(user_id=user_id, username=username)
        moderator.save()

        # Створення облікового запису Django для модератора, якщо потрібно
        if create_django_user:
            if not password:
                # Якщо пароль не вказаний, генеруємо випадковий
                password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))

            # Створення користувача Django (не суперкористувача)
            user = User.objects.create_user(
                username=username,
                password=password,
                is_staff=False,
                is_superuser=False
            )

            messages.success(request,
                             f'Модератор {username} створений успішно. '
                             f'Створено обліковий запис Django з паролем: {password}. '
                             f'Запишіть цей пароль, він більше не буде показаний.')
        else:
            messages.success(request, f'Модератор {username} створений успішно.')

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
            if username:
                user = User.objects.get(username=username)
                user.delete()
                messages.success(request, f'Модератор {username} та його обліковий запис Django видалені')
            else:
                messages.success(request, f'Модератор видалений')
        except User.DoesNotExist:
            messages.success(request, f'Модератор {username} видалений (без облікового запису Django)')

    except Moderator.DoesNotExist:
        messages.error(request, f'Модератор з ID {user_id} не знайдений')

    return redirect('manage_moderators')


@user_passes_test(is_superuser)
def create_django_user(request, user_id):
    """Створення облікового запису Django для існуючого модератора"""
    try:
        moderator = Moderator.objects.get(user_id=user_id)

        if not moderator.username:
            messages.error(request, 'Неможливо створити обліковий запис: модератор не має імені користувача')
            return redirect('manage_moderators')

        # Перевірка чи вже існує користувач Django з таким username
        if User.objects.filter(username=moderator.username).exists():
            messages.error(request, f'Користувач Django з іменем {moderator.username} вже існує')
            return redirect('manage_moderators')

        # Генерація випадкового паролю
        password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))

        # Створення користувача Django
        user = User.objects.create_user(
            username=moderator.username,
            password=password,
            is_staff=False,
            is_superuser=False
        )

        messages.success(request,
                         f'Створено обліковий запис Django для модератора {moderator.username}. '
                         f'Пароль: {password}. Запишіть цей пароль, він більше не буде показаний.')

    except Moderator.DoesNotExist:
        messages.error(request, f'Модератор з ID {user_id} не знайдений')

    return redirect('manage_moderators')


@user_passes_test(is_superuser)
def reset_password(request, user_id):
    """Скидання пароля для облікового запису Django модератора"""
    try:
        moderator = Moderator.objects.get(user_id=user_id)

        if not moderator.username:
            messages.error(request, 'Неможливо скинути пароль: модератор не має імені користувача')
            return redirect('manage_moderators')

        try:
            user = User.objects.get(username=moderator.username)

            # Генерація нового випадкового паролю
            new_password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))

            # Встановлення нового пароля
            user.set_password(new_password)
            user.save()

            messages.success(request,
                             f'Пароль для користувача {moderator.username} скинуто. '
                             f'Новий пароль: {new_password}. Запишіть цей пароль, він більше не буде показаний.')

        except User.DoesNotExist:
            messages.error(request, f'Користувача Django з іменем {moderator.username} не знайдено')

    except Moderator.DoesNotExist:
        messages.error(request, f'Модератор з ID {user_id} не знайдений')

    return redirect('manage_moderators')