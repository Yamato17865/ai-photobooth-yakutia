# 🎨 AI Фотобудка Якутии | IT-Cube

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green)](https://flask.palletsprojects.com/)
[![Replicate](https://img.shields.io/badge/AI-Replicate-purple)](https://replicate.com)

Веб-приложение для генерации AI-портретов с профессиональной подготовкой к печати (10×15 см, до 1200 DPI).

## ✨ Возможности

- 📸 Захват фото с веб-камеры (WebRTC)
- 🎨 **50+ художественных стилей** (аниме, Дисней, киберпанк, якутские мотивы)
- 🧠 Интеграция с AI-моделями: **FLUX Kontext Pro** и **Google Nano-Banana**
- 🖨️ Автоматическая подготовка к печати: 10×15 см, 300/600/1200 DPI
- 👤 Умное распознавание лица (Face Detection API)
- 💾 Скачивание в Full-HD и печать с брендированием

## 🛠️ Стек технологий

| Backend | Frontend | AI & Обработка |
|:---|:---|:---|
| Python 3 | HTML5/CSS3 | Replicate API |
| Flask | JavaScript (ES6+) | FLUX Kontext Pro |
| Pillow (PIL) | WebRTC | Nano-Banana |
| Requests | Face Detection API | Pillow |

## 🚀 Быстрый старт

### Последовательности действий
1. Клонировать репозиторий
```bash
git clone https://github.com/Yamato17865/ai-photobooth-yakutia.git
cd ai-photobooth-yakutia

2. УСТАНОВИТЬ ЗАВИСИМОСТИ

bash
pip install -r requirements.txt

3. НАСТРОИТЬ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
Создайте файл .env на основе .env.example:

bash
cp .env.example .env
Откройте .env в любом редакторе и добавьте ваш токен Replicate API:
text
REPLICATE_API_TOKEN=r8_ваш_токен_здесь
SECRET_KEY=любой_секретный_ключ

4. ЗАПУСТИТЬ ПРИЛОЖЕНИЕ

bash
python app.py
Откройте браузер и перейдите по адресу: http://localhost:5000

⚠️ ВАЖНО
Для работы генерации изображений требуется платный аккаунт Replicate с привязанной банковской картой. Без токена приложение запустится, но генерация будет недоступна.

![Image](https://github.com/user-attachments/assets/6b8b6ab5-1d2a-47b5-ab06-513fe65f357d)




