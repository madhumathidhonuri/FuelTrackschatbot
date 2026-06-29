# FuelTracks WhatsApp AI Bot

A Django-based WhatsApp AI assistant integrated with Groq Cloud and the Meta Graph API. This bot automates customer queries, delivers product catalogs dynamically, and supports marketing broadcast campaigns.

---

## 🛠️ Local Development Setup

### 1. Prerequisites
*   Python 3.10+
*   Meta Developer Account (with WhatsApp Business API access)
*   Groq API Key

### 2. Environment Setup
1.  Clone the repository to your local machine.
2.  Create and activate a virtual environment:
    ```bash
    # Windows (PowerShell)
    python -m venv venv
    .\venv\Scripts\Activate.ps1

    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### 3. Environment Variables Configuration
Create a `.env` file in the root of your project directory (this file is ignored by Git). Set the following variables:

```env
# Meta WhatsApp API Credentials
WHATSAPP_TOKEN=your_whatsapp_access_token_here
PHONE_NUMBER_ID=your_whatsapp_phone_number_id_here
VERIFY_TOKEN=your_webhook_verify_token_here
WHATSAPP_APP_SECRET=your_meta_app_secret_here

# Groq Cloud AI API Key
GROQ_API_KEY=your_groq_api_key_here

# Django Configurations
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=your_django_secret_key_here
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Running Migrations & Local Server
Prepare the local SQLite database and start the development server:
```bash
python manage.py migrate
python manage.py runserver
```
Once started, you can access the admin panel at `http://127.0.0.1:8000/admin/`.

### 5. Running Tests
To verify all unit tests run and pass correctly:
```bash
python manage.py test
```

---

## 🚀 Production Deployment Configuration

The application is built to be cloud-ready and supports standard hosting platforms (e.g. Render, Heroku, AWS).

### 1. Database (PostgreSQL Support)
*   By default, the application runs on **SQLite** locally.
*   In production, if you specify the **`DATABASE_URL`** environment variable (e.g., `postgres://user:password@host:5432/db`), Django will automatically connect to your PostgreSQL database.

### 2. Static Files (WhiteNoise Middleware)
*   Django disables built-in static files serving when `DEBUG = False`.
*   The application includes **WhiteNoise** support. If `whitenoise` is installed in the environment, Django will automatically compress and serve static files (CSS, JS, images) in production without needing a separate Nginx/CDN config.
*   Ensure your build command runs `python manage.py collectstatic --no-input` (configured in `build.sh`).

### 3. Webhook Payload Verification
*   Ensure **`WHATSAPP_APP_SECRET`** is set in your production environment settings. When provided, the webhook endpoint automatically validates signatures on incoming Meta HTTP payloads to guarantee requests originate from Meta.

### 4. Required Production `.env` / Environment Variables
Ensure these are configured in your production host dashboard:
*   `DJANGO_DEBUG=False`
*   `DJANGO_SECRET_KEY=a-secure-long-random-string`
*   `ALLOWED_HOSTS=your-app-domain.com,your-subdomain.onrender.com`
*   `DATABASE_URL=postgres://...`
