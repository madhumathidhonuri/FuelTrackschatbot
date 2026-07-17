from django.db import migrations

def backfill_agent_notification_logs(apps, schema_editor):
    AgentNotificationLog = apps.get_model('bot', 'AgentNotificationLog')
    ChatMessage = apps.get_model('bot', 'ChatMessage')

    logs = AgentNotificationLog.objects.all().order_by('created_at')
    for log in logs:
        if not log.message_content or not log.phone_number:
            continue
        content = log.message_content.strip()
        if not content:
            continue

        lines = [line.strip() for line in content.split('\n') if line.strip()]
        for line in lines:
            exists = ChatMessage.objects.filter(
                phone_number=log.phone_number,
                role='user',
                content=line
            ).exists()

            if not exists:
                msg = ChatMessage.objects.create(
                    phone_number=log.phone_number,
                    role='user',
                    content=line,
                    timestamp=log.created_at
                )

def reverse_backfill(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0019_alter_agentnotificationlog_phone_number_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_agent_notification_logs, reverse_code=reverse_backfill),
    ]
