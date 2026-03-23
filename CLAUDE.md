# Transcripta Analyst — AI Analytics Agent

## Проект
ИИ агент для аналитики сервиса транскрибации Transcripta. Анализирует продуктовые метрики из MySQL БД, визуализирует дашборд, отправляет сводки в Telegram, генерирует продуктовые гипотезы через Claude API.

## Стек
- **Python** — основной язык
- **MySQL** — БД сервиса, доступ через SSH-туннель
- **Streamlit** — интерактивный дашборд (синий + фиолетовый цвет, порт 8501)
- **Telegram Bot** — уведомления
- **Claude API** (claude-opus-4-6) — генерация гипотез и инсайтов
- **Хостинг** — Beget VPS (без Docker, МВП)

## Инфраструктура
- **Основной VPS (дашборд + бот)**: 155.212.138.151, user=root, alias=product.studio.test
  - Код: /opt/transcripta/
  - Systemd: transcripta-dashboard.service + transcripta-bot.service
  - SSH-туннель к БД: ssh -fN -L 3306:127.0.0.1:3306 vlad@93.189.229.156
- **БД VPS**: 93.189.229.156, user=vlad, MySQL на 127.0.0.1:3306
- MySQL: host=127.0.0.1, port=3306, db=transcription_ai, user=root, password=root
- SSH ключ: ~/.ssh/transcripta_analyst (для обоих серверов)
- Домен: analytics-transcripta.ru → 155.212.138.151

## Запуск (локально)
```bash
cd transcription_analytics
ssh -fN mysql-tunnel          # поднять SSH-туннель к БД
PYTHONPATH=. python3 -m streamlit run dashboard/app.py   # дашборд на :8501
PYTHONPATH=. python3 main.py --bot                        # только планировщик
PYTHONPATH=. python3 main.py                              # дашборд + планировщик
```

## Telegram
- Бот уже создан (токен в .env)
- Chat ID группы аналитики: `-5172505765`
- **Каждый час в :00** — сводка метрик за текущий день
- **Каждый день в 09:00 МСК** — аномалии + гипотезы от Claude

## GitHub
- Репозиторий: https://github.com/zakharov1vlad/Transcripta-Analyst
- Push через HTTPS + Personal Access Token (repo scope)
- `git remote set-url origin https://zakharov1vlad:TOKEN@github.com/zakharov1vlad/Transcripta-Analyst.git`

## Важные правила БД
- `is_test` = NULL (обычный пользователь) или '1' (тест) — **везде фильтровать: `COALESCE(is_test, '0') != '1'`**
- БД: `transcription_ai`
- Колонка длительности транскрипции: `duration` (секунды), не `duration_seconds`
- `get_plan_distribution()` возвращает колонки: `subscription_plan`, `count`
- `by_utm(days)` возвращает колонки: `utm_source`, `users`, `transcriptions`, `revenue`
- `get_media_type_split()` возвращает колонки: `media_type`, `count`
- `get_reviews_series()` возвращает колонки: `date`, `count`, `avg_rating`
- `get_rating_distribution()` возвращает DataFrame с колонками: `rating`, `count`

## Схема БД (transcription_ai)

### users
- `id`, `email`, `username`, `name`
- `subscription_plan`, `subscription_expires_at`, `subscription_type` (monthly/yearly)
- `transcriptions_remaining`, `transcriptions_used`, `transcriptions_completed`
- `first_purchase_completed`, `subscription_auto_renewal`, `manual_subscription`
- `yookassa_payment_method_id`, `last_payment_date`, `failed_payment_count`
- `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `referral_code`
- `google_id`, `email_verified`, `created_at`, `updated_at`
- `is_test` — NULL (реальный) или '1' (тест)
- `first_payment_discount_used`, `auto_renewal_disabled_at`, `transcription_retention_days`
- `card_mask`, `avatar_base64`

### transcriptions
- `id`, `user_id`, `filename`, `transcription` (JSON)
- `audio_format`, `audio_size`, `media_type` (audio/video)
- `duration` (сек), `transcribed_duration_seconds`
- `summary`, `participants`, `tags`, `project_id`
- `s3_media_url`, `share_token`, `is_shared`, `shared_at`
- `from_landing_funnel`, `full_transcript_paid`, `created_at`

### projects
- `id`, `user_id`, `name`, `created_at`

### active_subscriptions
- `id`, `user_id`, `plan_name`
- `transcriptions_remaining`, `transcriptions_total`
- `start_date`, `end_date`, `subscription_type`
- `auto_renewal`, `payment_method_id`, `created_at`, `updated_at`

### payment_history
- `id`, `user_id`, `yookassa_payment_id`, `plan_name`
- `amount`, `currency` (RUB), `status`, `payment_method_type`, `payment_method_id`
- `is_autopay`, `metadata` (JSON), `created_at`

### future_subscriptions
- `id`, `user_id`, `plan_name`, `payment_history_id`, `activation_date`, `created_at`

### reviews
- `id`, `user_id`, `user_email`, `transcription_id`
- `rating` (1–5), `review_text`, `created_at`, `updated_at`

### feedbacks
- `id`, `user_id`, `email`, `user_name`
- `rating` (1–5), `title`, `message`
- `likes`, `improvements`, `wishes` (JSON)
- `created_at`, `updated_at`, `ip_address`, `user_agent`

### chat_history
- `id`, `user_id`, `transcription_id`, `message`, `response`, `created_at`

### ai_reports
- `id`, `transcription_id`, `user_id`
- `style_key`, `style_name`, `category`, `content`
- `tokens_used`, `generation_time_ms`

### user_discounts
- `id`, `user_id`, `discount_type`, `discount_value`
- `used_at`, `expires_at`, `promo_code`

## Структура проекта
```
transcription_analytics/
├── .env                    # API ключи и доступы к БД (не в git)
├── requirements.txt
├── main.py                 # точка входа (--bot = только планировщик)
├── config/settings.py      # загрузка .env
├── db/
│   ├── connection.py       # SQLAlchemy engine
│   └── queries.py          # fetch_df(), fetch_one()
├── metrics/
│   ├── users.py            # DAU, MAU, WAU, churn, retention, plan_distribution
│   ├── revenue.py          # ARPU, ARPPU, LTV, выручка, покупки
│   ├── product.py          # транскрипции, медиатип, лендинг, ai_reports, chat
│   └── satisfaction.py     # рейтинги reviews + feedbacks
├── cohorts/analysis.py     # weekly/monthly retention pivot
├── segmentation/slices.py  # by_utm, by_plan, by_subscription_type
├── anomaly/detector.py     # Z-score + IQR, check_all_metrics()
├── ai_agent/claude.py      # generate_hypotheses(), save/load JSON
├── dashboard/
│   ├── app.py              # Streamlit: 6 вкладок + сайдбар
│   ├── theme.py            # PRIMARY=#4F46E5, SECONDARY=#7C3AED
│   └── components/
│       ├── overview.py     # KPI-карточки
│       ├── charts.py       # Plotly графики
│       ├── tables.py       # таблицы по дням + когорты
│       └── hypotheses.py   # таблица гипотез
├── bot/
│   ├── hourly_report.py    # метрики за текущий день
│   └── daily_report.py     # аномалии + гипотезы Claude
└── scheduler/jobs.py       # APScheduler: hourly + 09:00 daily
```

## Статус проекта — ЗАВЕРШЁН ✅
- [x] Требования собраны
- [x] Стек выбран
- [x] SSH-туннель настроен
- [x] БД подключена (1139 реальных пользователей)
- [x] Все метрики написаны и работают
- [x] Streamlit дашборд (6 вкладок, Plotly)
- [x] Яндекс Директ аналитика (расход, ROI) в боте и дашборде
- [x] Telegram бот (hourly + daily) — работает на VPS
- [x] Планировщик APScheduler
- [x] Код запушен на GitHub
- [x] Деплой на VPS 155.212.138.151 (systemd, автозапуск)
- [x] SSL сертификат (Let's Encrypt, analytics-transcripta.ru + www, до 2026-06-21)
- [x] Домен analytics-transcripta.ru + www → nginx (HTTPS) → Streamlit
- [x] Страница входа (логин: vlad, пароль: Transcripta2026)
- [x] Часовой бот: МСК время, верифицированные рег., подписки, конверсия, прибыль, AI-отчёты, оценки

## Деплой на VPS (обновление файлов)
Так как VPS не git-репо, файлы копируются через scp:
```bash
scp transcription_analytics/config/settings.py product.studio.test:/opt/transcripta/config/settings.py
# или весь проект:
rsync -av --exclude='.env' --exclude='__pycache__' --exclude='*.pyc' \
  transcription_analytics/ product.studio.test:/opt/transcripta/
ssh product.studio.test 'systemctl restart transcripta-bot transcripta-dashboard'
```

## Credentials (в .env)
- `ANTHROPIC_API_KEY` — есть
- `TELEGRAM_BOT_TOKEN` — есть
- `TELEGRAM_CHAT_ID=-5172505765`
- `DB_HOST=127.0.0.1`
- `DB_PORT=3306`
- `DB_USER=root`
- `DB_PASSWORD=root`
- `DB_NAME=transcription_ai`
