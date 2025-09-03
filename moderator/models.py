from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# Соответствует вашей таблице bans
class Ban(models.Model):
    user_id = models.BigIntegerField(primary_key=True)
    chat_id = models.BigIntegerField()
    reason = models.TextField()

    class Meta:
        db_table = 'bans'
        unique_together = ('user_id', 'chat_id')
        managed = False


# Соответствует вашей таблице chat_settings
class ChatSetting(models.Model):
    chat_id = models.BigIntegerField(primary_key=True)
    chat_title = models.CharField(max_length=255, blank=True, null=True)
    filter_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'chat_settings'
        managed = False



# Соответствует вашей таблице moderators
class Moderator(models.Model):
    user_id = models.BigIntegerField(primary_key=True)
    username = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'moderators'
        managed = False



# Соответствует вашей таблице punishments
class Punishment(models.Model):
    PUNISHMENT_TYPES = [
        ('kick', 'Kick'),
        ('ban', 'Ban'),
        ('mute', 'Mute'),
        ('warn', 'Warning'),
    ]

    id = models.AutoField(primary_key=True)
    user_id = models.BigIntegerField()
    chat_id = models.BigIntegerField()
    punishment_type = models.CharField(max_length=10, choices=PUNISHMENT_TYPES)
    reason = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    duration_minutes = models.IntegerField(null=True, blank=True)
    moderator_id = models.BigIntegerField()

    class Meta:
        db_table = 'punishments'
        managed = False



# Соответствует вашей таблице warnings
class Warning(models.Model):
    user_id = models.BigIntegerField(primary_key=True)
    chat_id = models.BigIntegerField()
    warn_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'warnings'
        unique_together = ('user_id', 'chat_id')
        managed = False



# Дополнительная модель для кеширования информации о пользователях Telegram
class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, primary_key=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    last_seen = models.DateTimeField(auto_now=True)

    def get_display_name(self):
        if self.username:
            return f"@{self.username}"
        elif self.first_name:
            return f"{self.first_name} {self.last_name or ''}".strip()
        else:
            return f"User {self.user_id}"

    class Meta:
        db_table = 'telegramuser'  # вкажи реальне ім’я таблиці в БД



# Дополнительная модель для информации о чатах
class TelegramChat(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    chat_type = models.CharField(max_length=50, default='group')
    member_count = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

