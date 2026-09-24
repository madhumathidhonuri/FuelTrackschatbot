#!/usr/bin/env bash
# exit on error
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Create or update superuser automatically
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.contrib.auth import get_user_model; User = get_user_model(); username=os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin'); email=os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com'); password=os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'AdminPassword@123'); u, created = User.objects.get_or_create(username=username, defaults={'email': email, 'is_staff': True, 'is_superuser': True}); u.set_password(password); u.is_staff = True; u.is_superuser = True; u.save(); print(f'✅ Superuser {username} configured successfully!')"