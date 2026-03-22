# Transcripta Analyst — AI Analytics Agent

## Проект
ИИ агент для аналитики сервиса транскрибации Transcripta. Анализирует продуктовые метрики из MySQL БД, визуализирует дашборд, отправляет сводки в Telegram, генерирует продуктовые гипотезы через Claude API.

## Стек
- **Python** — основной язык
- **MySQL** — БД сервиса, доступ через SSH-туннель
- **Streamlit** — интерактивный дашборд (синий + фиолетовый цвет, открытый доступ)
- **Telegram Bot** — уведомления
- **Claude API** (claude-opus-4-6) — генерация гипотез и инсайтов
- **Хостинг** — Beget VPS (без Docker, МВП)

## Инфраструктура
- Beget VPS (SSH-доступ)
- MySQL через SSH-туннель (host: 127.0.0.1, port: 3306)
- SSH-ключи уже сгенерированы: `id_ed25519` / `id_ed25519.pub`
- Публичный ключ нужно добавить в панели Beget → SSH-ключи

## Telegram
- Бот уже создан (токен в .env)
- Chat ID группы аналитики: `-5172505765`
- Расписание отправки: **раз в час** (основные метрики за текущий день)
- Гипотезы: **раз в день** (генерирует Claude как лучший CPO)

## Метрики (все продуктовые)
### Посещения и активность
- DAU, MAU, WAU
- Retention (Day 1, 7, 30)
- Churn rate
- Новые регистрации

### Финансы
- ARPPU, LTV
- Выручка (день / месяц / всё время)
- Покупки (количество, сумма)

### Продукт
- Средняя оценка пользователей
- Использование транскрибации (кол-во файлов, минут)

### Срезы
- По дню / месяцу / всему периоду
- Когортный анализ (weekly + monthly)
- По плану подписки / UTM / типу

## Важные правила БД
- Таблица `users` имеет поле `is_test = '1'` — таких пользователей **исключать из всей аналитики**
- БД называется `transcription_ai`

## Схема БД (transcription_ai)

### users
Пользователи, подписки, лимиты, UTM, платежи.
- `id` PK, `email` UNI, `username`, `name`
- `subscription_plan` (Free / платные планы), `subscription_expires_at`, `subscription_type` (monthly/yearly)
- `transcriptions_remaining` (int), `transcriptions_used` (decimal), `transcriptions_completed` (int)
- `first_purchase_completed`, `subscription_auto_renewal`, `manual_subscription`
- `yookassa_payment_method_id`, `last_payment_date`, `failed_payment_count`
- `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`
- `referral_code`, `google_id`, `email_verified`
- `created_at`, `updated_at`
- `is_test` — **фильтровать: WHERE is_test != '1'**
- `first_payment_discount_used`, `auto_renewal_disabled_at`, `transcription_retention_days`
- `card_mask`, `avatar_base64`

### transcriptions
Расшифровки аудио/видео.
- `id` PK, `user_id` FK→users
- `filename`, `transcription` (JSON), `audio_format`, `audio_size`, `media_type` (audio/video)
- `duration` (сек), `transcribed_duration_seconds`
- `summary`, `participants`, `tags`
- `project_id` FK→projects
- `s3_media_url`, `share_token` UNI, `is_shared`, `shared_at`
- `from_landing_funnel` (загрузка с лендинга до регистрации)
- `full_transcript_paid` (апсейл с лендинга)
- `created_at`

### projects
Проекты для группировки транскрипций.
- `id` PK, `user_id` FK→users, `name`, `created_at`

### active_subscriptions
Активные подписки.
- `id` PK, `user_id` FK→users
- `plan_name`, `transcriptions_remaining`, `transcriptions_total`
- `start_date`, `end_date`, `subscription_type` (monthly/yearly)
- `auto_renewal`, `payment_method_id`
- `created_at`, `updated_at`

### payment_history
История платежей (YooKassa).
- `id` PK, `user_id` FK→users
- `yookassa_payment_id`, `plan_name`, `amount`, `currency` (RUB)
- `status`, `payment_method_type`, `payment_method_id`
- `is_autopay`, `metadata` (JSON)
- `created_at`

### future_subscriptions
Очередь подписок к активации.
- `id` PK, `user_id`, `plan_name`, `payment_history_id`, `activation_date`, `created_at`

### reviews
Отзывы к транскрипциям (рейтинг 1–5).
- `id` PK, `user_id` FK→users, `transcription_id` FK→transcriptions
- `rating` (1–5), `review_text`, `created_at`, `updated_at`
- UNIQUE (user_id, transcription_id)

### feedbacks
Общая обратная связь.
- `id` PK, `user_id` FK→users, `email` UNI, `user_name`
- `rating` (1–5), `title`, `message`
- `likes` (JSON), `improvements` (JSON), `wishes` (JSON)
- `created_at`, `ip_address`, `user_agent`

### chat_history
История чата с ИИ по транскрипции.
- `id` PK, `user_id`, `transcription_id`
- `message` (вопрос), `response` (ответ ИИ), `created_at`

### ai_reports
AI-отчёты по транскрипциям.
- `id` PK, `transcription_id`, `user_id`
- `style_key`, `style_name`, `category`, `content`
- `tokens_used`, `generation_time_ms`
- UNIQUE (transcription_id, user_id, style_key)

### user_discounts
Скидки пользователей.
- `id` PK, `user_id`
- `discount_type` (new_user_50 / referral_50 / promo_code)
- `discount_value`, `used_at`, `expires_at`, `promo_code`
- UNIQUE (user_id, discount_type)

## Структура проекта (запланированная)
```
transcription_analytics/
├── config/         # настройки, SQL-запросы
├── db/             # подключение MySQL (SQLAlchemy + пул)
├── metrics/        # все метрики
├── cohorts/        # когортный анализ
├── segmentation/   # срезы
├── anomaly/        # детектор аномалий (Z-score + IQR)
├── ai_agent/       # Claude: инсайты и гипотезы
├── dashboard/      # Streamlit дашборд
├── bot/            # Telegram бот
└── scheduler/      # планировщик задач
```

## Статус проекта
- [x] Требования собраны
- [x] Стек выбран
- [x] SSH-ключи сгенерированы
- [ ] Схема БД — **нужно прислать повторно** (не сохранилась)
- [ ] SSH доступы (host, user, password)
- [ ] MySQL доступы (db name, user, password)
- [ ] Код написан
- [ ] Деплой на Beget

## Credentials (в .env, не хранить в коде)
- `ANTHROPIC_API_KEY` — есть
- `TELEGRAM_BOT_TOKEN` — есть
- `TELEGRAM_CHAT_ID=-5172505765`
- `SSH_HOST` — нужно
- `SSH_USER` — нужно
- `SSH_PASSWORD` — нужно
- `DB_NAME` — нужно
- `DB_USER` — нужно
- `DB_PASSWORD` — нужно
