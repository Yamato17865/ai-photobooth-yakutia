import os
import sys
import socket
import time
import traceback
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
import replicate
import base64
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont
import requests
from io import BytesIO
import json
import tempfile

# Устанавливаем глобальный таймаут
socket.setdefaulttimeout(600)

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

app.config['SECRET_KEY'] = 'it-cube-photolab-yakutia-pro-2024'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['BACKGROUNDS_FOLDER'] = os.path.join('static', 'backgrounds')
app.config['REFERENCES_FOLDER'] = os.path.join('static', 'references')
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['BACKGROUNDS_FOLDER'], exist_ok=True)
os.makedirs(app.config['REFERENCES_FOLDER'], exist_ok=True)

# ============================================================
# ФИКСИРОВАННЫЕ ПАРАМЕТРЫ ДЛЯ КНИЖНОЙ ПЕЧАТИ 10×15 СМ
# ============================================================
PRINT_WIDTH_CM = 10  # Ширина 10 см
PRINT_HEIGHT_CM = 15  # Высота 15 см (книжная ориентация)
PRINT_DPI = 300  # 300 DPI для высокой четкости

# Рассчитываем размер в пикселях для книжной ориентации
PRINT_WIDTH_PX = int(PRINT_WIDTH_CM * PRINT_DPI / 2.54)  # ≈ 1181 px
PRINT_HEIGHT_PX = int(PRINT_HEIGHT_CM * PRINT_DPI / 2.54)  # ≈ 1772 px

print(f"\n📏 ПАРАМЕТРЫ КНИЖНОЙ ПЕЧАТИ:")
print(f"   • Размер: {PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см (книжная ориентация)")
print(f"   • DPI: {PRINT_DPI}")
print(f"   • Пиксели: {PRINT_WIDTH_PX}×{PRINT_HEIGHT_PX} px")
print(f"   • Соотношение сторон: {PRINT_WIDTH_PX / PRINT_HEIGHT_PX:.3f} (1:1.5)")

# ============================================================
# НОВЫЕ ПАРАМЕТРЫ ПО УМОЛЧАНИЮ ДЛЯ ВОЗРАСТНОЙ АДАПТАЦИИ
# ============================================================
DEFAULT_STRENGTH = 0.75
DEFAULT_NEGATIVE_PROMPT = ""

# ============================================================
# СТИЛИ ДЛЯ ГЕНЕРАЦИИ - ВСЕ С ФИКСИРОВАННОЙ КНИЖНОЙ ОРИЕНТАЦИЕЙ
# ============================================================
# ============================================================
# 🎨 СТИЛИ ДЛЯ ГЕНЕРАЦИИ — ПОЛНЫЙ СПИСОК (33 стиля)
# ✅ Все с фиксированной портретной ориентацией 3:4
# ✅ Все с максимальным сохранением лица
# ============================================================
# ============================================================
# 🎨 СТИЛИ С МАКСИМАЛЬНЫМ СОХРАНЕНИЕМ ЛИЦА (50 СТИЛЕЙ)
# ✅ Усиленный блок likeness preservation в каждом промпте
# ✅ Стандартизированные негативные промпты
# ============================================================
STYLES = [
    # === FLUX KONTEXT PRO (3 стиля) ===
    {
        "name": "Аниме-протагонист", "id": "anime", "model": "flux-kontext-pro",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, anime style, modern anime aesthetic, sharp clean lineart, vibrant colors, expressive eyes, dynamic pose, youthful energy, cinematic composition, vertical portrait, waist-up, 3:4, 8K, ultra detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "input_image_key": "input_image", "output_format": "jpg", "aspect_ratio": "3:4",
        "enhance_photo": True, "sharpness": 1.5, "contrast": 1.2, "color": 1.15, "saturation": 1.1
    },
    {
        "name": "Дисней - ренессанс", "id": "beauty-beast", "model": "flux-kontext-pro",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, 90s Disney hand-drawn animation, traditional cel animation, enchanted castle background, magical atmosphere, painterly backgrounds, vibrant colors, clean bold outlines, vertical portrait, waist-up, 3:4, 8K, masterpiece",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "input_image_key": "input_image", "output_format": "jpg", "aspect_ratio": "3:4",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.25, "saturation": 1.2
    },
    {
        "name": "Дисней - мечтатель", "id": "dreamer", "model": "flux-kontext-pro",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, 1990s Disney animation style, traditional cel technique, soft watercolor shading, magical starry night, shooting stars, crescent moon, dreamy atmosphere, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "input_image_key": "input_image", "output_format": "jpg", "aspect_ratio": "3:4",
        "enhance_photo": True, "sharpness": 1.25, "contrast": 1.2, "color": 1.25, "saturation": 1.15
    },

    # === NANO-BANANA (47 стилей) ===
    {
        "name": "Миядзаки: Ветер долин", "id": "miyazaki", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Studio Ghibli style, Hayao Miyazaki masterpiece, watercolor painting, soft pastel colors, whimsical, ethereal, Totoro aesthetic, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.15, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Макото Синкай", "id": "shinkai", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Makoto Shinkai style, Your Name aesthetic, photorealistic anime, hyperrealistic clouds, lens flare, cinematic lighting, vertical portrait, waist-up, 3:4, 8K, ultra detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Волшебное фэнтези", "id": "fantasy", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, epic fantasy style, enchanted forest, bioluminescent plants, ancient runes, D&D aesthetic, cinematic lighting, NO STAFF, NO WAND, NO WEAPON, vertical portrait, waist-up, 3:4, 8K, masterpiece",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Ретро-синтвейв 80s", "id": "retro", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, retro synthwave 80s aesthetic, neon purple and cyan rim lighting, deep pink electric blue gradient sky, palm trees silhouette, VHS texture, scan lines, Blade Runner 1982 grading, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.5, "contrast": 1.3, "color": 1.35, "saturation": 1.4,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Киберпанк 2077", "id": "cyberpunk", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, cyberpunk neon noir, holographic pink and blue lights, chrome cybernetic details, dystopian cityscape, rain soaked streets, Blade Runner 2049 style, vertical portrait, waist-up, 3:4, 8K, ultra realistic",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.2, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Якутский богатырь", "id": "bootur", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, authentic Yakut warrior Sakha ethnicity, NO HELMET, face fully visible, traditional Sakha lamellar armor, BATAS polearm, Lena Pillars background, aurora borealis, National Geographic style, photorealistic, vertical portrait, waist-up, 3:4, 8K, ultra detailed",
        "negative_prompt": "helmet, horned helmet, Viking, Norse, sword, European armor, face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "input_image_key": "image_input", "output_format": "jpg", "aspect_ratio": "3:4",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.2, "saturation": 1.15
    },
    {
        "name": "Якутское украшение", "id": "yakut_jewelry", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Sakha woman portrait, BASTYNA forehead band, YTARGA earrings, ILIN KEBIHER necklace on neck only, jewelry limited to head/neck, black background, studio lighting, vertical portrait, waist-up, 3:4, 8K photorealistic, ultra sharp silver filigree",
        "negative_prompt": "face alteration, chest armor, body armor, silver net covering body, jewelry covering chest, Western jewelry, face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "input_image_key": "image_input", "output_format": "jpg", "aspect_ratio": "3:4",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.25, "saturation": 1.15
    },
    {
        "name": "Космическая богиня", "id": "retro_space", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, retro futurism cosmic goddess, ethereal beauty, soft serene features, luminous skin with subtle glow, gentle cosmic aura, dreamy space with pastel nebulas, distant stars, gentle light rays, vertical portrait, waist-up, 3:4, 8K, photorealistic",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.2, "contrast": 1.1, "color": 1.15, "saturation": 1.1,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Викторианский портрет", "id": "victorian", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Victorian era oil painting, 19th century style, elegant vintage attire, soft natural lighting, dramatic chiaroscuro, rich deep colors, classical art, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.25, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Стимпанк", "id": "steampunk", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, steampunk aesthetic, Victorian mechanical accessories, brass and copper gears, goggles on forehead, warm sepia tones, vintage machinery, steam-powered atmosphere, vertical portrait, waist-up, 3:4, 8K, ultra detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Барокко", "id": "baroque", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Baroque painting style, Caravaggio dramatic lighting, Rembrandt aesthetic, rich golden tones, dramatic shadows, ornate frame, luxurious velvet, 17th century aristocracy, vertical portrait, waist-up, 3:4, 8K, masterpiece",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.3, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Арт Нуво", "id": "artnouveau", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Art Nouveau style, Alphonse Mucha aesthetic, elegant flowing lines, floral patterns, pastel colors, decorative frame, botanical details, soft feminine beauty, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Средневековый рыцарь", "id": "knight", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, medieval knight portrait, authentic historical plate armor, castle courtyard background, dramatic clouds, heroic pose, NO HELMET, face fully visible, vertical portrait, waist-up, 3:4, 8K, ultra realistic",
        "negative_prompt": "helmet, face covered, face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Древний Египет", "id": "egypt", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, ancient Egyptian pharaoh portrait, golden nemes headdress, ornate collar necklace, hieroglyphics background, pyramids at sunset, majestic pose, rich gold and lapis lazuli colors, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.3, "saturation": 1.25,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Космонавт", "id": "cosmonaut", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, futuristic cosmonaut portrait, modern space suit with helmet off, face fully visible, Earth view from orbit, stars and galaxies, space station interior, dramatic cosmic lighting, vertical portrait, waist-up, 3:4, 8K, ultra realistic",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Подводное царство", "id": "underwater", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, underwater fantasy portrait, surrounded by colorful tropical fish, coral reef background, sunlight rays through water, bubbles floating, ethereal aquatic lighting, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.3, "saturation": 1.25,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Зимняя сказка", "id": "winter", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, winter wonderland portrait, snow falling gently, frost-covered pine trees, warm cozy winter clothing, magical ice crystals, soft blue white color palette, aurora borealis, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Сакура", "id": "sakura", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, traditional Japanese aesthetic, cherry blossom sakura trees in full bloom, falling pink petals, kimono or elegant attire, Japanese garden background, soft pink gold tones, Ukiyo-e influence, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Ацтекский воин", "id": "aztec", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Aztec warrior portrait, traditional feather headdress, ceremonial armor, jade and gold ornaments, Mesoamerican pyramid background, jungle setting, dramatic sunset lighting, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.3, "saturation": 1.25,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Рококо", "id": "rococo", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Rococo style portrait, 18th century French aristocracy, pastel colors, ornate decorations, flowers and ribbons, elegant pose, Fragonard aesthetic, luxurious fabrics, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Северное сияние", "id": "aurora", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, magical portrait under northern lights, aurora borealis dancing in night sky, snowy arctic landscape, warm winter clothing, mystical green and purple lights, starry night, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.2, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Цветущий сад", "id": "garden", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, blooming garden portrait, surrounded by colorful flowers, roses, peonies, lavender, soft sunlight filtering through leaves, dreamy bokeh background, romantic atmosphere, vertical portrait, waist-up, 3:4, 8K, ultra detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.1, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Голливудский гламур", "id": "hollywood", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, classic Hollywood glamour portrait, 1950s golden age cinema, elegant evening gown or tuxedo, dramatic spotlight, vintage camera flash, Old Hollywood style, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Пират", "id": "pirate", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, pirate captain portrait, tricorn hat, weathered coat, tropical island background, pirate ship at sea, treasure map, golden earrings, Caribbean aesthetic, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Эльф Средиземья", "id": "elf", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Tolkien elf portrait, ethereal elven features, pointed ears subtly visible, flowing robes, Rivendell style architecture, mystical forest, ancient trees, soft magical light, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Викинг", "id": "viking", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Viking warrior portrait, NO HORNED HELMET, authentic Norse armor, fur cloak, braided beard or hair, dramatic fjord background, longships in distance, Nordic runes, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Кофейная атмосфера", "id": "coffee", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, cozy coffee shop portrait, warm atmospheric lighting, steam rising from coffee cup, rustic wooden interior, soft bokeh background, hygge aesthetic, relaxed expression, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.2, "saturation": 1.1,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Ботаническая иллюстрация", "id": "botanical", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, botanical illustration style portrait, surrounded by detailed plant drawings, vintage scientific illustration aesthetic, pressed flowers, herbarium style, delicate line work, watercolor textures, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.1, "color": 1.2, "saturation": 1.1,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Стереотипы 80-х", "id": "80s", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, 1980s portrait aesthetic, bright neon colors, cassette tapes, boombox, retro fashion, MTV style, classic 80s photography, vibrant backgrounds, geometric patterns, polaroid frame effect, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.3, "saturation": 1.3,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Балет", "id": "ballet", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, ballet dancer portrait, elegant tutu or practice attire, theater stage background, soft spotlight, graceful pose, dance studio aesthetic, classical music inspiration, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    # === ДОПОЛНИТЕЛЬНЫЕ 17 СТИЛЕЙ (С ВОЗРАСТНЫМ СОХРАНЕНИЕМ) ===
    {
        "name": "Готический вампир", "id": "gothic_vampire", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, gothic vampire portrait, dark romantic aesthetic, Victorian gothic attire, pale skin with subtle glow, dramatic shadows, candlelight atmosphere, ornate gothic architecture, stained glass windows, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.3, "color": 1.2, "saturation": 1.1,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Русская красавица", "id": "russian_beauty", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, traditional Russian beauty portrait, ornate kokoshnik headdress, embroidered folk costume, rich red and gold colors, winter palace background, snow crystals, imperial elegance, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.3, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Самурай", "id": "samurai", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, feudal Japanese samurai portrait, traditional armor with family mon crest, katana at side, cherry blossom petals falling, ancient temple background, dramatic sunset, NO HELMET, face fully visible, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Греческий бог/богиня", "id": "greek_god", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, ancient Greek god/goddess portrait, flowing white toga with golden accents, laurel wreath crown, marble columns background, Mount Olympus in distance, ethereal divine light, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.2, "color": 1.2, "saturation": 1.15,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Индийский махараджа", "id": "maharaja", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Indian maharaja portrait, ornate turban with peacock feather, jeweled necklace, rich silk robes in gold and crimson, palace arches background, warm golden hour lighting, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.35, "saturation": 1.3,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Африканский вождь", "id": "african_chief", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, African tribal chief portrait, traditional ceremonial attire, ornate beaded necklace and headdress, warm earth tones, savanna sunset background, acacia trees silhouette, dignified and powerful, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.3, "saturation": 1.25,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Мушкетёр", "id": "musketeer", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, 17th century French musketeer portrait, ornate plumed hat, embroidered velvet coat with lace collar, rapier at side, royal palace courtyard background, dramatic baroque lighting, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Гангстер 20-х", "id": "gangster_20s", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, 1920s gangster portrait, pinstripe suit, fedora hat, speakeasy background, dim jazz club lighting, vintage noir aesthetic, sepia and amber tones, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.3, "color": 1.15, "saturation": 1.05,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Бизнес-директор", "id": "ceo_business", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, modern business CEO portrait, premium tailored suit, confident professional pose, corporate office background, city skyline through window, clean minimalist aesthetic, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.2, "color": 1.15, "saturation": 1.1,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Рок-звезда", "id": "rock_star", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, rock star portrait, leather jacket, stage spotlight, concert venue background, dynamic performance energy, smoky atmosphere, dramatic stage lighting, rebellious aesthetic, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.5, "contrast": 1.3, "color": 1.25, "saturation": 1.25,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Хиппи 70-х", "id": "hippie_70s", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, 1970s hippie portrait, bohemian style clothing, flower crown, peace sign, psychedelic colors, woodstock festival vibe, sunset field background, warm vintage tones, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.15, "color": 1.3, "saturation": 1.35,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Футуристический воин", "id": "future_warrior", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, futuristic warrior portrait, advanced combat armor with glowing elements, sci-fi weapon, dystopian battlefield background, dramatic energy effects, neon accents, year 3000 aesthetic, vertical portrait, waist-up, 3:4, 8K, ultra detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.5, "contrast": 1.3, "color": 1.25, "saturation": 1.3,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Автогонщик", "id": "racer_driver", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, professional race car driver portrait, racing suit with sponsor logos, checkered flag background, Formula 1 pit lane, dynamic motion blur, speed and adrenaline, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.25, "saturation": 1.25,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Сёрфер", "id": "surfer", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, surfer portrait, beach lifestyle, surfboard visible, ocean waves background, golden sunset, tropical paradise, laid-back California vibe, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.3, "contrast": 1.2, "color": 1.25, "saturation": 1.3,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Йога/Медитация", "id": "yoga_meditation", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, yoga meditation portrait, peaceful serene expression, lotus position, zen garden background, cherry blossoms, soft natural lighting, spiritual harmony, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.2, "contrast": 1.1, "color": 1.15, "saturation": 1.1,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Детектив нуар", "id": "noir_detective", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, 1940s noir detective portrait, trench coat, fedora hat, rainy city street background, dramatic shadows, film noir aesthetic, black and white with selective color, mysterious atmosphere, vertical portrait, waist-up, 3:4, 8K, ultra sharp",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.35, "color": 1.1, "saturation": 0.9,
        "aspect_ratio": "3:4", "output_format": "jpg"
    },
    {
        "name": "Ковбой", "id": "cowboy", "model": "nano-banana",
        "prompt": "EXACT SAME PERSON, IDENTICAL FACE, 100% LIKENESS TO REFERENCE PHOTO, PRESERVE EXACT AGE, KEEP AGE CHARACTERISTICS IDENTICAL (CHILD/ADULT/ELDERLY EXACTLY AS SHOWN), MAINTAIN ORIGINAL SKIN TEXTURE, WRINKLES OR SMOOTH CHILD SKIN EXACTLY FROM REFERENCE, PRESERVE EYE COLOR IRIS SHAPE NOSE MOUTH JAWLINE CHEEKBONES EXACTLY, DO NOT CHANGE AGE, DO NOT YOUNGIFY, DO NOT AGE UP, DO NOT BEAUTIFY OR SMOOTH SKIN ARTIFICIALLY, STRICT IDENTITY AND AGE FIDELITY PRIORITY OVER STYLE TRANSFER, Wild West cowboy portrait, cowboy hat, leather vest, desert sunset background, saloon and cactus, frontier spirit, American West aesthetic, vertical portrait, waist-up, 3:4, 8K, highly detailed",
        "negative_prompt": "face distortion, face morphing, altered features, wrong age, aged up child, de-aged elderly, generic adult face, artificially smoothed skin, plastic skin, unrealistic age, wrong eye color, identity drift, blurry, lowres, bad anatomy, extra limbs, landscape, horizontal",
        "enhance_photo": True, "sharpness": 1.4, "contrast": 1.25, "color": 1.25, "saturation": 1.2,
        "aspect_ratio": "3:4", "output_format": "jpg"
    }
]

# Проверяем токен Replicate
replicate_api_token = os.getenv('REPLICATE_API_TOKEN')
if not replicate_api_token:
    print("⚠️  ВНИМАНИЕ: Не найден токен REPLICATE_API_TOKEN!")
    print("Создайте файл .env с содержимым:")
    print("REPLICATE_API_TOKEN=ваш_токен_здесь")
    sys.exit(1)

# Устанавливаем токен
os.environ["REPLICATE_API_TOKEN"] = replicate_api_token

print("\n" + "=" * 70)
print("🚀 IT-CUBE AI ФОТОБУДКА ЯКУТИИ - КНИЖНАЯ ПЕЧАТЬ EDITION")
print("=" * 70)
print("✅ Replicate токен загружен")
print(f"🎯 МОДЕЛИ: FLUX для аниме и Дисней 90х, Nano-Banana для остальных 9 стилей!")
print(f"✨ Качество: Ultra-HD (2048×2048) - УЛУЧШЕНО ДЛЯ ПЕЧАТИ!")
print(f"🖨️  Печать: {PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см в {PRINT_DPI} DPI (КНИЖНАЯ ОРИЕНТАЦИЯ)")
print(f"📸 Камеры: Обе зеркальные с одинаковой рамкой")
print(f"🎨 Стилей: {len(STYLES)}")
print(f"🔥 Улучшение качества: ВСЕ СТИЛИ!")
print("=" * 70 + "\n")

print("\n📝 РАСПРЕДЕЛЕНИЕ МОДЕЛЕЙ ПО СТИЛЯМ:")
print("=" * 70)
print("   🔥 FLUX KONTEXT PRO (2 стиля):")
print(f"   •  Аниме-протагонист - МАКСИМАЛЬНОЕ СОХРАНЕНИЕ ЛИЦА")
print(f"   •  Дисней-ренессанс - МАКСИМАЛЬНОЕ СОХРАНЕНИЕ ЛИЦА, 90s Дисней стиль")
print("\n   🍌 NANO-BANANA (9 стилей):")
for style in [s for s in STYLES if s.get('model') != 'flux-kontext-pro']:
    print(f"   •  {style['name']} - 100% СОХРАНЕНИЕ ЛИЦА")
print("=" * 70 + "\n")

print("\n📏 ПАРАМЕТРЫ ПЕЧАТИ (КНИЖНАЯ ОРИЕНТАЦИЯ):")
print("=" * 70)
print(f"   • Размер: {PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см")
print(f"   • DPI: {PRINT_DPI}")
print(f"   • Пиксели: {PRINT_WIDTH_PX}×{PRINT_HEIGHT_PX} px")
print(f"   • Соотношение: 2:3 (книжное)")
print(f"   • Формат: JPEG Quality 100")
print("=" * 70 + "\n")


@app.route('/')
def index():
    return render_template('index.html', styles=STYLES)


@app.route('/capture', methods=['POST'])
def capture():
    try:
        data = request.json
        image_data = data['image']

        if ',' in image_data:
            image_data = image_data.split(',')[1]

        image_bytes = base64.b64decode(image_data)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"original_{timestamp}.png"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        with open(filepath, 'wb') as f:
            f.write(image_bytes)

        optimized_path = optimize_photo_for_ai(filepath, f"optimized_{timestamp}.png")

        return jsonify({
            'success': True,
            'original_image': filename,
            'optimized_image': os.path.basename(optimized_path),
            'message': 'Фото успешно захвачено в Ultra-HD!'
        })
    except Exception as e:
        error_msg = f'Ошибка захвата: {str(e)}'
        print(error_msg)
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500


def optimize_photo_for_ai(input_path, output_filename):
    """Оптимизация фото с веб-камеры для AI моделей - с фиксацией на лицо для книжной печати"""
    try:
        img = Image.open(input_path)

        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background

        width, height = img.size
        print(f"📏 Исходный размер фото: {width}×{height}")

        # ✅ ФИКСИРУЕМ НА ЛИЦО С УЧЁТОМ КНИЖНОЙ ОРИЕНТАЦИИ
        # Обрезаем для лучшего фокуса на лицо (формат 3:4 для генерации)
        if width > height * 1.2:
            # Горизонтальное фото - обрезаем по центру в портрет
            target_height = height
            target_width = int(height * 0.75)  # 3:4 соотношение
            crop_x = (width - target_width) // 2
            img = img.crop((crop_x, 0, crop_x + target_width, target_height))
            print(f"✂️  Обрезано горизонтальное → портрет: {img.width}×{img.height}")
        elif height > width * 1.5:
            # Слишком вытянутое вертикальное - обрезаем верх и низ
            target_width = width
            target_height = int(width * 1.333)  # 3:4 соотношение
            crop_y = (height - target_height) // 2
            img = img.crop((0, crop_y, target_width, crop_y + target_height))
            print(f"✂️  Обрезано вертикальное для фокуса на лицо: {img.width}×{img.height}")

        # ✅ УВЕЛИЧЕНО ДО 2048 ДЛЯ ЛУЧШЕГО КАЧЕСТВА
        target_size = 2048
        img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)

        # Приводим к квадрату или 3:4 в зависимости от стиля
        # Для книжной печати лучше квадрат для генерации, потом обрежем
        if img.width != img.height:
            size = min(img.width, img.height)
            left = (img.width - size) // 2
            top = (img.height - size) // 2
            right = left + size
            bottom = top + size
            img = img.crop((left, top, right, bottom))

        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        img.save(output_path, 'PNG', compress_level=0, optimize=False)

        file_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"💾 Размер файла: {file_size:.2f} MB")
        print(f"✅ Фото оптимизировано: {output_filename}")
        print(f"   📏 Итоговый размер: {img.width}×{img.height} (квадрат для генерации)")

        return output_path
    except Exception as e:
        print(f"⚠️ Ошибка оптимизации: {e}")
        return input_path


def generate_with_flux(image_path, style_config, gender='male'):
    """Генерация с black-forest-labs/flux-kontext-pro"""

    style_name = style_config["name"]
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            print(f"\n🔥 FLUX KONTEXT PRO - {style_name} (попытка {attempt + 1}/{max_retries})")
            print(f"   📸 Стиль: {style_name}")
            print(f"   👤 Пол: {'Женский' if gender == 'female' else 'Мужской'}")

            prompt = style_config.get('prompt', '')

            if gender == 'female':
                prompt = f"{prompt}, beautiful woman, feminine features"
            else:
                prompt = f"{prompt}, handsome man, masculine features"

            print(f"   📤 Загрузка фото в FLUX...")

            client = replicate.Client()

            with open(image_path, 'rb') as f:
                file_data = f.read()

            temp_file_path = os.path.join(tempfile.gettempdir(), f"flux_upload_{int(time.time())}.jpg")
            with open(temp_file_path, 'wb') as f:
                f.write(file_data)

            upload_attempts = 0
            uploaded_file = None

            while upload_attempts < 3 and uploaded_file is None:
                try:
                    with open(temp_file_path, 'rb') as f:
                        uploaded_file = client.files.create(f)
                    break
                except Exception as upload_error:
                    upload_attempts += 1
                    print(f"   ⚠️ Ошибка загрузки (попытка {upload_attempts}/3): {upload_error}")
                    if upload_attempts < 3:
                        time.sleep(2)

            if uploaded_file is None:
                raise Exception("Не удалось загрузить файл после 3 попыток")

            try:
                os.unlink(temp_file_path)
            except:
                pass

            image_url = uploaded_file.urls.get('get') or uploaded_file.urls['get']

            print(f"   ✅ Фото загружено")

            input_params = {
                "prompt": prompt,
                "input_image": image_url,
                "output_format": style_config.get('output_format', 'jpg'),
                "aspect_ratio": "3:4"  # ✅ ФИКСИРОВАННОЕ 3:4 ДЛЯ КНИЖНОЙ ПЕЧАТИ
            }

            print(f"\n   🚀 Запуск генерации FLUX с aspect_ratio 3:4...")

            start_time = time.time()

            output = replicate.run(
                "black-forest-labs/flux-kontext-pro",
                input=input_params
            )

            gen_time = time.time() - start_time
            print(f"\n   ✅ FLUX завершил генерацию за {gen_time:.1f} сек!")

            return output

        except Exception as e:
            print(f"\n⚠️ Попытка {attempt + 1} не удалась: {e}")
            if attempt < max_retries - 1:
                print(f"   🔄 Повтор через {retry_delay} секунд...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"\n❌ Все попытки FLUX исчерпаны")
                traceback.print_exc()
                raise Exception(f"FLUX не смог обработать после {max_retries} попыток: {e}")


def generate_with_nano_banana(image_path, style_config, gender='male',
                              strength=DEFAULT_STRENGTH,
                              negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                              positive_modifier="",
                              age_category="adult"):
    """Генерация с Google/Nano-Banana - с поддержкой возрастной адаптации"""

    style_name = style_config["name"]
    style_id = style_config["id"]

    print(f"\n🍌 GOOGLE/NANO-BANANA - {style_name}")
    print(f"   📊 Параметры возрастной адаптации:")
    print(f"      • Возрастная категория: {age_category}")
    print(f"      • Strength: {strength}")
    print(f"      • Negative prompt: {'есть' if negative_prompt else 'нет'}")

    base_prompt = style_config.get('prompt', '')

    face_preservation = "EXACT SAME PERSON, IDENTICAL FACE, SAME PERSON, DO NOT CHANGE FACE, ABSOLUTELY NO FACE CHANGES, KEEP FACE 100% IDENTICAL TO REFERENCE PHOTO, PERFECT FACE PRESERVATION, "

    # Базовый гендерный промпт (без возрастных модификаторов)
    if style_id == 'fantasy':
        if gender == 'female':
            gender_prompt = "beautiful fairy queen with ethereal beauty, delicate feminine features, luminous skin with soft magical glow, elegant flowing gown, translucent fairy wings with iridescent shimmer, crown of flowers and crystals, enchanted forest princess, dreamy soft focus, romantic fantasy aesthetic, NO STAFF, NO WAND"
        else:
            gender_prompt = "powerful wizard with mystical presence, strong masculine features, flowing magical robes, ancient wisdom, dramatic fantasy portrait, NO STAFF, NO WAND"
    elif style_id == 'retro_space':
        if gender == 'female':
            gender_prompt = "beautiful cosmic goddess with ethereal beauty, serene facial features, graceful expression, luminous skin with subtle glow, gentle cosmic aura, elegant and refined"
        else:
            gender_prompt = "handsome cosmic warrior with strong masculine features, powerful presence, celestial armor, dramatic space portrait"
    elif style_id == 'bootur':
        if gender == 'female':
            gender_prompt = "beautiful Sakha woman with feminine features, elegant, traditional Sakha female attire"
        else:
            gender_prompt = "handsome man, masculine features, strong, traditional Sakha warrior"
    elif gender == 'female':
        gender_prompt = "beautiful woman, feminine features, elegant"
    else:
        gender_prompt = "handsome man, masculine features, strong"

    # Добавляем позитивный модификатор от фронтенда
    if positive_modifier:
        gender_prompt = f"{gender_prompt}, {positive_modifier}"

    prompt = f"{face_preservation} {base_prompt}, {gender_prompt}"

    print(f"   📝 Промпт сформирован (длина: {len(prompt)} символов)")

    try:
        print(f"   📤 Загрузка вашего фото...")

        client = replicate.Client()
        with open(image_path, 'rb') as f:
            uploaded_file = client.files.create(f)
            image_url = uploaded_file.urls.get('get') or uploaded_file.urls['url']

        print(f"   ✅ Фото загружено")

        # Формируем параметры для Nano-Banana
        input_params = {
            "prompt": prompt,
            "image_input": [image_url],
            "aspect_ratio": "3:4",  # ✅ ФИКСИРОВАННОЕ 3:4 ДЛЯ КНИЖНОЙ ПЕЧАТИ
            "output_format": style_config.get('output_format', 'jpg')
        }

        # Добавляем strength если он отличается от значения по умолчанию
        if strength != DEFAULT_STRENGTH:
            input_params["strength"] = strength
            print(f"   ⚙️  Установлен strength: {strength}")

        # Добавляем negative_prompt если он передан
        if negative_prompt:
            input_params["negative_prompt"] = negative_prompt
            print(f"   ⚙️  Добавлен negative_prompt (длина: {len(negative_prompt)})")

        output = replicate.run(
            "google/nano-banana",
            input=input_params
        )

        print(f"\n   ✅ Google/Nano-Banana завершил генерацию!")

        return output

    except Exception as e:
        print(f"\n❌ Ошибка Google/Nano-Banana: {e}")
        traceback.print_exc()
        raise Exception(f"Google/Nano-Banana не смог обработать: {e}")


def generate_image(image_path, style_config, gender='male',
                   strength=DEFAULT_STRENGTH,
                   negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                   positive_modifier="",
                   age_category="adult"):
    """Основная функция генерации с поддержкой возрастной адаптации"""
    model = style_config.get('model', 'nano-banana')

    if model == 'flux-kontext-pro':
        # Для FLUX пока не добавляем возрастные параметры (они и так хорошо работают)
        return generate_with_flux(image_path, style_config, gender)
    else:
        return generate_with_nano_banana(image_path, style_config, gender,
                                         strength, negative_prompt,
                                         positive_modifier, age_category)


def save_generated_image(output, output_path):
    """Сохранение сгенерированного изображения"""
    try:
        if hasattr(output, 'read'):
            print(f"   📥 Сохранение файла из потока...")
            content = output.read()
            with open(output_path, 'wb') as f:
                f.write(content)

            img = Image.open(output_path)
            print(f"   ✅ Сохранено: {img.width}×{img.height}, {img.mode}")

            if img.mode == 'RGBA':
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                rgb_img.save(output_path, 'JPEG', quality=100)
                print(f"   🔄 Конвертировано из RGBA в RGB")

            return True

        if isinstance(output, list):
            image_url = output[0].url if hasattr(output[0], 'url') else output[0]
        elif hasattr(output, 'url'):
            image_url = output.url
        elif isinstance(output, str):
            image_url = output
        else:
            return False

        print(f"   📥 Загрузка изображения...")
        response = requests.get(image_url, timeout=300)

        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            img = Image.open(output_path)
            print(f"   ✅ Загружено: {img.width}×{img.height}")
            return True
        else:
            raise Exception(f"Не удалось загрузить: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")
        return False


def enhance_generated_image(image_path, style_config):
    """Улучшение качества сгенерированного изображения"""
    try:
        if not style_config.get('enhance_photo', False):
            return image_path

        style_name = style_config['name']
        print(f"\n📸 УЛУЧШЕНИЕ КАЧЕСТВА ФОТО - {style_name}")

        img = Image.open(image_path)

        sharpness = style_config.get('sharpness', 1.4)
        contrast = style_config.get('contrast', 1.2)
        color = style_config.get('color', 1.2)
        saturation = style_config.get('saturation', 1.15)

        print(f"   ⚙️  Параметры улучшения:")
        print(f"      • Резкость: +{int((sharpness - 1) * 100)}%")
        print(f"      • Контраст: +{int((contrast - 1) * 100)}%")
        print(f"      • Цвет: +{int((color - 1) * 100)}%")
        print(f"      • Насыщенность: +{int((saturation - 1) * 100)}%")

        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(sharpness)

        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast)

        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(color)

        if saturation > 1.0:
            from PIL.ImageEnhance import Color as ColorEnhance
            enhancer = ColorEnhance(img)
            img = enhancer.enhance(saturation)

        img = img.filter(ImageFilter.SMOOTH_MORE)
        img = img.filter(ImageFilter.DETAIL)

        enhanced_path = image_path.replace('.jpg', '_enhanced.jpg').replace('.png', '_enhanced.jpg')
        img.save(enhanced_path, 'JPEG', quality=100, optimize=True, progressive=False)

        print(f"   ✅ Улучшение завершено!")

        return enhanced_path

    except Exception as e:
        print(f"⚠️ Ошибка улучшения изображения: {e}")
        return image_path


def upscale_for_print(image_path):
    """Увеличение изображения для печати - точно под размер книжной печати"""
    try:
        img = Image.open(image_path)
        original_width, original_height = img.size

        # ✅ УВЕЛИЧИВАЕМ ТОЧНО ДО РАЗМЕРА ПЕЧАТИ
        target_width = PRINT_WIDTH_PX
        target_height = PRINT_HEIGHT_PX

        print(f"   📐 Масштабирование для печати:")
        print(f"      Исходный: {original_width}×{original_height}")
        print(f"      Целевой: {target_width}×{target_height} ({PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см)")

        # Используем LANCZOS для максимального качества
        upscaled_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # ✅ ДОПОЛНИТЕЛЬНАЯ ОБРАБОТКА ДЛЯ ПЕЧАТИ
        enhancer = ImageEnhance.Sharpness(upscaled_img)
        upscaled_img = enhancer.enhance(1.1)

        enhancer = ImageEnhance.Contrast(upscaled_img)
        upscaled_img = enhancer.enhance(1.05)

        upscaled_path = image_path.replace('.jpg', '_upscaled.jpg').replace('.png', '_upscaled.jpg')
        upscaled_img.save(upscaled_path, 'JPEG', quality=100, optimize=True, progressive=False,
                          dpi=(PRINT_DPI, PRINT_DPI))

        print(f"   ✅ Увеличено для печати: {original_width}×{original_height} → {target_width}×{target_height}")

        return upscaled_path
    except Exception as e:
        print(f"⚠️ Ошибка увеличения: {e}")
        return image_path


def prepare_for_print_with_branding(image_path, output_path, style_name=""):
    """Подготовка для печати с брендингом IT-CUBE - КНИЖНАЯ ОРИЕНТАЦИЯ"""
    try:
        print(f"\n🖨️  ПОДГОТОВКА ДЛЯ ПЕЧАТИ С БРЕНДИНГОМ IT-CUBE (КНИЖНАЯ)")
        print(f"   🎨 Стиль: {style_name}")

        # Увеличиваем точно до размера печати
        upscaled_path = upscale_for_print(image_path)
        main_img = Image.open(upscaled_path)

        # Создаем холст точно под размер печати
        print_img = Image.new('RGB', (PRINT_WIDTH_PX, PRINT_HEIGHT_PX), (255, 255, 255))

        # Нижний отступ для брендинга (2 см)
        bottom_margin_cm = 2
        bottom_margin_px = int(bottom_margin_cm * PRINT_DPI / 2.54)
        content_height = PRINT_HEIGHT_PX - bottom_margin_px

        print(f"   📏 Размер печати: {PRINT_WIDTH_PX}×{PRINT_HEIGHT_PX} px")
        print(f"   📏 Область контента: {PRINT_WIDTH_PX}×{content_height} px")
        print(f"   📏 Нижний отступ: {bottom_margin_px} px ({bottom_margin_cm} см)")

        # Масштабируем изображение под область контента с сохранением пропорций
        img_ratio = main_img.width / main_img.height
        target_ratio = PRINT_WIDTH_PX / content_height

        if img_ratio > target_ratio:
            new_width = PRINT_WIDTH_PX
            new_height = int(PRINT_WIDTH_PX / img_ratio)
            paste_x = 0
            paste_y = (content_height - new_height) // 2
        else:
            new_height = content_height
            new_width = int(content_height * img_ratio)
            paste_x = (PRINT_WIDTH_PX - new_width) // 2
            paste_y = 0

        # ✅ УЛУЧШЕННОЕ ИЗМЕНЕНИЕ РАЗМЕРА С LANCZOS
        main_resized = main_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # ✅ ДОПОЛНИТЕЛЬНЫЕ УЛУЧШЕНИЯ ПЕРЕД ПЕЧАТЬЮ
        enhancer = ImageEnhance.Sharpness(main_resized)
        main_resized = enhancer.enhance(1.15)
        enhancer = ImageEnhance.Contrast(main_resized)
        main_resized = enhancer.enhance(1.1)
        enhancer = ImageEnhance.Brightness(main_resized)
        main_resized = enhancer.enhance(1.05)
        enhancer = ImageEnhance.Color(main_resized)
        main_resized = enhancer.enhance(1.08)
        main_resized = main_resized.filter(ImageFilter.SMOOTH_MORE)
        main_resized = main_resized.filter(ImageFilter.DETAIL)

        print_img.paste(main_resized, (paste_x, paste_y))

        # Добавляем брендинг внизу
        brand_y = PRINT_HEIGHT_PX - bottom_margin_px
        draw = ImageDraw.Draw(print_img)
        draw.rectangle([(0, brand_y), (PRINT_WIDTH_PX, PRINT_HEIGHT_PX)], fill=(255, 255, 255))
        draw.line([(0, brand_y), (PRINT_WIDTH_PX, brand_y)], fill=(6, 182, 212), width=1)

        try:
            logo_path = os.path.join('static', 'logo.png')
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                logo_size = 60
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

                print_img.paste(logo, (20, brand_y + (bottom_margin_px - logo_size) // 2),
                                logo if logo.mode == 'RGBA' else None)
                print_img.paste(logo, (PRINT_WIDTH_PX - logo_size - 20, brand_y + (bottom_margin_px - logo_size) // 2),
                                logo if logo.mode == 'RGBA' else None)

            try:
                font = ImageFont.truetype("arial.ttf", 20)
                font_small = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()
                font_small = ImageFont.load_default()

            title = "IT-Cube AI Фотобудка Якутии"
            bbox = draw.textbbox((0, 0), title, font=font)
            text_width = bbox[2] - bbox[0]
            draw.text(((PRINT_WIDTH_PX - text_width) // 2, brand_y + 10), title, fill=(6, 182, 212), font=font)

            date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
            subtitle = f"Стиль: {style_name} | {date_str}"
            bbox = draw.textbbox((0, 0), subtitle, font=font_small)
            text_width = bbox[2] - bbox[0]
            draw.text(((PRINT_WIDTH_PX - text_width) // 2, brand_y + 35), subtitle, fill=(100, 116, 139),
                      font=font_small)

        except Exception as e:
            print(f"   ⚠️  Ошибка добавления текста: {e}")

        # ✅ СОХРАНЯЕМ С МАКСИМАЛЬНЫМ КАЧЕСТВОМ ДЛЯ ПЕЧАТИ
        print_img.save(output_path, 'JPEG', quality=100, optimize=True, progressive=False, dpi=(PRINT_DPI, PRINT_DPI),
                       subsampling=0)

        file_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n✅ ПОДГОТОВКА ДЛЯ ПЕЧАТИ ЗАВЕРШЕНА")
        print(f"   🖼️  Файл: {os.path.basename(output_path)}")
        print(f"   📏 Размер: {PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см (КНИЖНАЯ)")
        print(f"   🖨️  DPI: {PRINT_DPI}")
        print(f"   🎨 Стиль: {style_name}")
        print(f"   💾 Размер файла: {file_size:.2f} MB")
        print("=" * 70)

        return True
    except Exception as e:
        print(f"\n❌ ОШИБКА ПОДГОТОВКИ ДЛЯ ПЕЧАТИ: {e}")
        return False


@app.route('/generate', methods=['POST'])
def generate():
    try:
        print("\n" + "=" * 70)
        print("🎯 ГЕНЕРАЦИЯ ИЗ ФОТО С ВЕБ-КАМЕРЫ")

        data = request.json
        optimized_image = data['optimized_image']
        style_id = data['style_id']
        style_name = data['style_name']
        gender = data.get('gender', 'male')

        # ========== НОВЫЕ ПАРАМЕТРЫ ОТ ФРОНТЕНДА ==========
        strength = data.get('strength', DEFAULT_STRENGTH)
        negative_prompt = data.get('negative_prompt', DEFAULT_NEGATIVE_PROMPT)
        positive_modifier = data.get('positive_modifier', "")
        preserve_identity = data.get('preserve_identity', True)
        age_category = data.get('age_category', 'adult')
        # ========== КОНЕЦ НОВЫХ ПАРАМЕТРОВ ==========

        selected_style = next((s for s in STYLES if s['id'] == style_id), None)
        if not selected_style:
            return jsonify({'success': False, 'error': 'Стиль не найден'}), 400

        image_path = os.path.join(app.config['UPLOAD_FOLDER'], optimized_image)
        if not os.path.exists(image_path):
            return jsonify({'success': False, 'error': 'Фото не найдено'}), 400

        model_used = selected_style.get('model', 'nano-banana')

        print(f"👤 Стиль: {style_name}")
        print(f"👫 Пол: {'Женский' if gender == 'female' else 'Мужской'}")
        print(f"📏 Формат генерации: 3:4 (книжный)")
        print(f"📏 Формат печати: {PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см (книжный)")

        # Логируем параметры возрастной адаптации
        print(f"🎂 Возрастная категория: {age_category}")
        print(f"⚙️  Strength: {strength}")
        print(f"📝 Negative prompt: {'есть' if negative_prompt else 'нет'} (длина: {len(negative_prompt)})")
        print(f"✨ Positive modifier: {'есть' if positive_modifier else 'нет'} (длина: {len(positive_modifier)})")
        print(f"🆔 Preserve identity: {preserve_identity}")

        start_time = time.time()
        output = generate_image(image_path, selected_style, gender,
                                strength, negative_prompt, positive_modifier, age_category)
        generation_time = time.time() - start_time

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        gender_suffix = "_female" if gender == 'female' else "_male"
        age_suffix = f"_{age_category}" if age_category != 'adult' else ""

        generated_filename = f"generated_{style_id}{gender_suffix}{age_suffix}_{timestamp}.jpg"
        generated_path = os.path.join(app.config['UPLOAD_FOLDER'], generated_filename)

        if not save_generated_image(output, generated_path):
            return jsonify({'success': False, 'error': 'Ошибка сохранения изображения'}), 500

        enhanced_path = enhance_generated_image(generated_path, selected_style)

        print_filename = f"print_{style_id}{gender_suffix}{age_suffix}_{timestamp}.jpg"
        print_path = os.path.join(app.config['UPLOAD_FOLDER'], print_filename)

        prepare_for_print_with_branding(enhanced_path, print_path, style_name)

        try:
            img = Image.open(enhanced_path)
            print_img = Image.open(print_path)
            print(f"\n✅ ГЕНЕРАЦИЯ ЗАВЕРШЕНА")
            print(f"   🖼️  Основное изображение: {img.width}×{img.height} пикселей")
            print(f"   🖨️  Для печати: {print_img.width}×{print_img.height} пикселей")
            print(f"   📏 Формат печати: КНИЖНЫЙ ({PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см)")
            print(f"   🖨️  DPI: {PRINT_DPI}")
            print(f"   🎂 Возрастная адаптация: {age_category}")
        except Exception as e:
            print(f"\n✅ ГЕНЕРАЦИЯ ЗАВЕРШЕНА")

        print(f"\n   ⏱️  Общее время: {generation_time:.1f} сек")
        print("=" * 70)

        return jsonify({
            'success': True,
            'generated_image': os.path.basename(enhanced_path),
            'print_image': print_filename,
            'style': style_name,
            'gender': gender,
            'age_category': age_category,
            'model_used': 'FLUX Kontext Pro' if model_used == 'flux-kontext-pro' else 'Google/Nano-Banana',
            'quality': 'Ultra-HD',
            'enhanced': selected_style.get('enhance_photo', False),
            'print_ready': True,
            'print_size': f'{PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см (книжный)',
            'dpi': PRINT_DPI,
            'has_logo': True,
            'has_branding': True,
            'orientation': 'portrait',
            'message': f'✅ {style_name} успешно создан! Готов к книжной печати {PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см!'
        })
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ ОШИБКА ГЕНЕРАЦИИ: {error_msg}")
        traceback.print_exc()

        if "429" in error_msg or "rate limit" in error_msg.lower():
            user_msg = "Достигнут лимит запросов. Подождите 60 секунд."
        elif "input_image" in error_msg.lower():
            user_msg = "Ошибка загрузки фото. Пожалуйста, попробуйте еще раз."
        else:
            user_msg = f"Ошибка генерации: {error_msg[:100]}"

        return jsonify({'success': False, 'error': user_msg}), 500


@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'Файл не найден'}), 404

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        style_name = 'AI_Art'
        for style in STYLES:
            if style['id'] in filename.lower():
                style_name = style['name']
                break

        quality = 'Print_Ready_Portrait' if filename.startswith('print_') else 'Digital'
        download_name = f"ITCube_{style_name.replace(' ', '_')}_{quality}_{PRINT_WIDTH_CM}x{PRINT_HEIGHT_CM}cm_{timestamp}.jpg"

        return send_file(file_path, as_attachment=True, download_name=download_name, mimetype='image/jpeg')
    except Exception as e:
        print(f"❌ Ошибка скачивания: {e}")
        return jsonify({'success': False, 'error': 'Ошибка скачивания'}), 500


@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'app': 'IT-Cube AI Photobooth Yakutia',
        'version': '11.0 - Portrait Print Edition with Age Adaptation',
        'models': {
            'flux': 'black-forest-labs/flux-kontext-pro',
            'nano_banana': 'google/nano-banana'
        },
        'styles_count': len(STYLES),
        'styles': [{'name': style['name'], 'model': style['model']} for style in STYLES],
        'print_quality': f'{PRINT_DPI} DPI Ultra-HD',
        'print_size': f'{PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см (portrait)',
        'orientation': 'portrait',
        'age_adaptation': {
            'enabled': True,
            'supports_negative_prompt': True,
            'supports_strength_adjustment': True,
            'default_strength': DEFAULT_STRENGTH
        },
        'timestamp': datetime.now().isoformat()
    })


@app.route('/print/<filename>')
def print_page(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'Файл не найден'}), 404

        style_name = 'AI Art'
        for style in STYLES:
            if style['id'] in filename.lower():
                style_name = style['name']
                break

        gender = 'female' if '_female' in filename else 'male'

        return render_template('print.html',
                               filename=filename,
                               style_name=style_name,
                               gender=gender,
                               print_size=f'{PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см',
                               orientation='portrait',
                               dpi=PRINT_DPI,
                               timestamp=datetime.now().strftime('%d.%m.%Y %H:%M'))
    except Exception as e:
        return jsonify({'success': False, 'error': 'Ошибка загрузки страницы печати'}), 500


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 ЗАПУСК ФОТОБУДКИ ЯКУТИИ - КНИЖНАЯ ПЕЧАТЬ EDITION")
    print("=" * 70)

    print(f"\n📏 ПАРАМЕТРЫ ПЕЧАТИ:")
    print(f"   • Размер: {PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см (КНИЖНАЯ ОРИЕНТАЦИЯ)")
    print(f"   • DPI: {PRINT_DPI}")
    print(f"   • Пиксели: {PRINT_WIDTH_PX}×{PRINT_HEIGHT_PX} px")
    print(f"   • Соотношение сторон: 2:3")

    print(f"\n🎂 ВОЗРАСТНАЯ АДАПТАЦИЯ:")
    print(f"   • Включена: ДА")
    print(f"   • Поддержка negative_prompt: ДА")
    print(f"   • Поддержка strength: ДА (по умолчанию {DEFAULT_STRENGTH})")
    print(f"   • Категории: child, adult, senior")

    print(f"\n🎯 РАСПРЕДЕЛЕНИЕ МОДЕЛЕЙ:")
    print(f"\n   🔥 FLUX KONTEXT PRO (2 стиля):")
    flux_styles = [s for s in STYLES if s.get('model') == 'flux-kontext-pro']
    for style in flux_styles:
        print(f"   •  {style['name']}")
    print(f"\n   🍌 NANO-BANANA (9 стилей):")
    nano_styles = [s for s in STYLES if s.get('model') != 'flux-kontext-pro']
    for i, style in enumerate(nano_styles, 1):
        print(f"   {i}. {style['name']}")

    print(f"\n📊  СТАТИСТИКА:")
    print(f"   • Всего стилей: {len(STYLES)}")
    print(f"   • Все стили с фиксированным aspect_ratio: 3:4 (для книжной печати)")
    print(f"   • 100% сохранение лица: ВСЕ СТИЛИ!")
    print(f"   • С улучшением фото: ВСЕ СТИЛИ!")
    print(f"   • Разрешение генерации: 3:4 (≈ 1536×2048)")
    print(f"   • Финальная печать: {PRINT_WIDTH_PX}×{PRINT_HEIGHT_PX} px ({PRINT_WIDTH_CM}×{PRINT_HEIGHT_CM} см)")
    print(f"   • Upscaling: точное масштабирование под размер печати")
    print(f"   • JPEG Quality: 100 (максимальное)")
    print(f"   • Брендинг: IT-CUBE логотип и текст внизу")

    print("\n" + "=" * 70 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)