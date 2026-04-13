# 🎨 AI Фотобудка Якутии | IT-Cube

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

Веб-приложение для генерации AI-портретов с подготовкой к профессиональной печати (10×15 см, до 1200 DPI).

## ✨ Возможности

- 📸 Захват фото с веб-камеры
- 🎨 **50+ художественных стилей** (аниме, Дисней, киберпанк, якутские мотивы)
- 🧠 Интеграция с AI-моделями: FLUX Kontext Pro и Google Nano-Banana
- 🖨️ Автоматическая подготовка к печати: 10×15 см, 300/600/1200 DPI
- 👤 Умное распознавание лица с подсказками по позиционированию
- 💾 Скачивание и печать с брендированием

## 🚀 Быстрый старт

### 1. Клонировать репозиторий
```bash
git clone https://github.com/Yamato17865/ai-photobooth-yakutia.git
cd ai-photobooth-yakutia

2. Установить зависимости
bash
pip install -r requirements.txt

3. Настроить переменные окружения
Создайте файл .env на основе .env.example:
cp .env.example .env
Добавьте ваш токен Replicate API.

4. Запустить приложение
python app.py
Откройте http://localhost:5000
