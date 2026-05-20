"""
Image Generator V2 — Replace AceData Nano Banana 2 with:
  - Seedream 5.0 (Doubao) for 9 product photos (img2img, one batch call)
  - Qwen wan2.7-image for 3 detail module images (B1/B3 img2img, B2 text2img)
  - Pillow for vertical stitching of detail modules into final long image
"""

import os
import io
import time
import json
import base64
import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# API Config
# ============================================================

# Seedream 5.0 (Doubao ARK)
SEEDREAM_API_KEY = os.getenv("SEEDREAM_API_KEY", "ark-f7d9dad0-a23f-4e55-abcf-8615a732eda8-706d7")
SEEDREAM_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
SEEDREAM_MODEL = "doubao-seedream-5-0-260128"

# Qianwen wan2.7-image (DashScope)
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-a67c79a66a8147dcba80f0c8d9351289")
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
QWEN_MODEL = "wan2.7-image"


# ============================================================
# Helpers
# ============================================================

def _download_image(url: str, max_retries: int = 3) -> Image.Image | None:
    """Download an image from URL with retries."""
    import tempfile, subprocess
    for attempt in range(max_retries):
        try:
            # Try curl first (bypasses some CDN blocks)
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp_path = tmp.name
            tmp.close()
            subprocess.run(
                ["curl", "-s", "-o", tmp_path, "--max-time", "60", url],
                timeout=65, check=True,
            )
            if os.path.getsize(tmp_path) > 1000:
                img = Image.open(tmp_path).convert("RGB")
                img.load()
                os.unlink(tmp_path)
                return img
            os.unlink(tmp_path)
        except Exception:
            pass
        # Fallback to requests
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:
            pass
        if attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
    return None


def _image_to_base64_url(image_path: str) -> str | None:
    """Read an image file and return a data: URL string."""
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        # Detect mime type from extension
        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}
        mime = mime_map.get(ext, "image/jpeg")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"[error] Cannot encode {image_path}: {e}")
        return None


# ============================================================
# A — Seedream 5.0: 9 product photos (img2img)
# ============================================================

def generate_product_photos(
    reference_image_path: str,
    product_name: str = "",
    brand: str = "",
    selling_points: str = "",
    num_images: int = 9,
) -> list[dict]:
    """
    Generate 9 product photos via Seedream 5.0 img2img in one batch call.

    Args:
        reference_image_path: path to the reference product image
        product_name: product name for prompt context
        brand: brand name
        selling_points: key selling points for prompt context
        num_images: number of images to generate (default 9)

    Returns:
        list of dicts: [{"type": "白底图"|"场景图"|"细节图"|"多角度图"|"模特图",
                         "url": str, "image": PIL.Image}, ...]
    """
    print(f"\n[Seedream] Generating {num_images} product photos from reference...")

    ref_b64 = _image_to_base64_url(reference_image_path)
    if not ref_b64:
        print("[Seedream] Failed to encode reference image")
        return []

    product_desc = product_name or "product"
    brand_desc = f" for {brand}" if brand else ""
    sp_desc = f". Key features: {selling_points}" if selling_points else ""

    prompt = (
        f"Professional e-commerce product photography of this EXACT {product_desc}{brand_desc} shown in the reference image. "
        f"CRITICAL: EVERY image MUST feature THIS EXACT PRODUCT prominently centered. "
        f"DO NOT generate unrelated objects, people without the product, or empty scenes. "
        f"The product must be clearly visible and the main subject in EVERY single image. "
        f"Generate {num_images} varied product shots: "
        f"2-3 pure white background studio shots (front and angled views, product fills 80% of frame), "
        f"2-3 lifestyle scene shots (product placed in elegant minimalist settings like marble surface, wooden table, silk fabric — NO people), "
        f"2-3 macro close-up detail shots (texture, material, craftsmanship, product fills entire frame), "
        f"1-2 model shots (product worn/used by model, but product remains focal point). "
        f"All images: commercial grade, soft studio lighting, clean composition, high detail, consistent warm tone{sp_desc}."
    )

    payload = {
        "model": SEEDREAM_MODEL,
        "prompt": prompt,
        "image": ref_b64,
        "sequential_image_generation": "auto",
        "sequential_image_generation_options": {"max_images": num_images},
        "response_format": "url",
        "size": "2K",
        "watermark": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SEEDREAM_API_KEY}",
    }

    try:
        print(f"  [Seedream] Calling API (size=2K, max_images={num_images})...")
        resp = requests.post(SEEDREAM_URL, headers=headers, json=payload, timeout=300)
        if resp.status_code >= 400:
            print(f"  [Seedream] HTTP {resp.status_code}: {resp.text[:500]}")
            return []

        # Response may be SSE stream (because stream=true in the original example)
        # But we set stream=false (default), so it should be plain JSON
        data = resp.json()
        print(f"  [Seedream] Response keys: {list(data.keys())}")

        images = data.get("data", [])
        if not images:
            # Try alternative response format
            if "images" in data:
                images = data["images"]
            elif "results" in data:
                images = data["results"]

        if not images:
            print(f"  [Seedream] No images in response. Full response preview: {json.dumps(data, ensure_ascii=False)[:500]}")
            return []

        print(f"  [Seedream] Got {len(images)} images from API")

        results = []
        for i, img_data in enumerate(images):
            url = img_data.get("url", "")
            if not url:
                continue

            print(f"  [Seedream] Downloading image {i+1}/{len(images)}...")
            pil_img = _download_image(url)

            results.append({
                "index": i,
                "url": url,
                "image": pil_img,
            })

        print(f"  [Seedream] Done: {len(results)}/{num_images} images generated")
        return results

    except requests.exceptions.Timeout:
        print("[Seedream] Request timed out (300s)")
        return []
    except Exception as e:
        print(f"[Seedream] Error: {e}")
        import traceback
        traceback.print_exc()
        return []


# ============================================================
# B — Qianwen wan2.7-image: 3 detail module images
# ============================================================

def _call_qwen(
    prompt: str,
    reference_image_path: str | None = None,
    n: int = 1,
    size: str = "2K",
) -> list[Image.Image]:
    """
    Call Qianwen wan2.7-image API via direct HTTP request.

    Qwen wan2.7-image uses DashScope multimodal generation endpoint.
    img2img: include reference image in content
    text2img: text-only content

    Args:
        prompt: text prompt (English)
        reference_image_path: optional reference image for img2img mode
        n: number of images
        size: image size

    Returns:
        list of PIL Images
    """
    print(f"  [Qwen] {'img2img' if reference_image_path else 'text2img'} mode, n={n}")

    url = f"{QWEN_BASE_URL}/services/aigc/multimodal-generation/generation"

    # Build content list
    content_list = [{"text": prompt}]

    # For img2img, prepend reference image
    if reference_image_path:
        ref_b64 = _image_to_base64_url(reference_image_path)
        if ref_b64:
            content_list.insert(0, {"image": ref_b64})
            print(f"  [Qwen] Reference image encoded ({len(ref_b64)} chars)")

    payload = {
        "model": QWEN_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": content_list,
                }
            ]
        },
        "parameters": {
            "n": n,
            "size": size,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {QWEN_API_KEY}",
    }

    try:
        print(f"  [Qwen] POST {url}...")
        resp = requests.post(url, headers=headers, json=payload, timeout=300)

        if resp.status_code >= 400:
            print(f"  [Qwen] HTTP {resp.status_code}: {resp.text[:500]}")
            return []

        data = resp.json()
        print(f"  [Qwen] Response keys: {list(data.keys())}")

        # Parse response
        images = []
        output = data.get("output", {})
        choices = output.get("choices", [])

        for i, choice in enumerate(choices):
            # Try different response formats
            message = choice.get("message", {})
            content = message.get("content", [])

            for item in content:
                img_url = item.get("image", "") or item.get("url", "")
                if img_url:
                    print(f"  [Qwen] Choice {i} image URL: {img_url[:80]}...")
                    pil_img = _download_image(img_url)
                    if pil_img:
                        images.append(pil_img)

        # Also check for direct data[].url format
        if not images:
            data_list = data.get("data", [])
            for item in data_list:
                img_url = item.get("url", "")
                if img_url:
                    print(f"  [Qwen] data.url: {img_url[:80]}...")
                    pil_img = _download_image(img_url)
                    if pil_img:
                        images.append(pil_img)

        print(f"  [Qwen] Got {len(images)} image(s)")
        return images

    except requests.exceptions.Timeout:
        print("  [Qwen] Request timed out (300s)")
        return []
    except Exception as e:
        print(f"  [Qwen] Error: {e}")
        import traceback
        traceback.print_exc()
        return []


# Unified style suffix appended to every Qianwen prompt
STYLE_SUFFIX = (
    "Consistent style: premium editorial e-commerce, warm ivory beige and soft charcoal color palette, "
    "generous negative space, elegant serif typography, lots of breathing room, clean modern layout. "
    "All text MUST be English only. 2K resolution commercial grade."
)


def generate_detail_module_b1(
    white_bg_image_path: str,
    brand: str = "",
    product_name: str = "",
    tagline: str = "",
) -> Image.Image | None:
    """
    B1: Hero banner — emotional opening with full-width product visual.
    Brand name + product name + tagline + trust icons.
    img2img, reference = white background product photo.
    """
    print("\n[Qwen B1] Hero banner...")

    brand_name = brand.upper() if brand else "BRAND"
    product = product_name or "Product"
    tag = tagline or "Designed for everyday elegance"

    prompt = (
        f"E-commerce detail page SECTION 1 — EMOTIONAL HERO. "
        f"A full-width product hero shot, product centered in warm ivory background, "
        f"soft studio lighting, elegant shadows, product fills 60% of frame. "
        f"Left-aligned text overlay: '{brand_name}' in small uppercase serif, "
        f"'{product}' in large bold serif below, "
        f"'{tag}' in elegant thin italic underneath. "
        f"Bottom strip: 4 small trust icons in a row — "
        f"'Premium Quality' 'Fast Shipping' 'Easy Returns' 'Secure Checkout'. "
        f"Thin divider line at very bottom. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=white_bg_image_path, n=1)
    return images[0] if images else None


def generate_detail_module_b2(
    reference_image_path: str,
    features: list[dict],
) -> Image.Image | None:
    """
    B2: Quick feature scan — 4 features in a compact 2x2 grid.
    Each card = icon + keyword + 3 highlight data bullets.
    img2img with product photo reference.
    """
    print("\n[Qwen B2] Quick feature overview (rich)...")

    emojis = ["✦", "♢", "◆", "◇"]
    feature_lines = []
    data_bullets = [
        "✓ Premium grade materials",
        "✓ Precision 15+ quality checks",
        "✓ 2-year quality promise",
        "✓ 10,000+ happy customers",
    ]
    for i, f in enumerate(features[:4]):
        emoji = emojis[i]
        title = f.get("title", "FEATURE")
        desc = f.get("desc", "")
        bullet = data_bullets[i]
        feature_lines.append(f"Card {i+1}: {emoji} '{title}' | {desc} | {bullet}")
    features_text = "\n".join(feature_lines)

    prompt = (
        f"E-commerce detail page SECTION 2 — FEATURE HIGHLIGHTS. "
        f"A compact 2x2 grid of 4 feature cards, 2 cards per row. "
        f"EACH CARD layout (top to bottom): a small elegant icon, "
        f"a bold 3-5 word keyword title below the icon, "
        f"a brief 4-6 word description line, "
        f"and 2 micro data nuggets with tiny checkmarks (like '✓ 15+ quality checks' '✓ 2yr promise'). "
        f"The EXACT 4 features:\n{features_text}\n"
        f"All 4 cards equally sized, clean grid spacing. "
        f"Background: warm beige. Cards have soft rounded corners and subtle shadow. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=reference_image_path, n=1)
    return images[0] if images else None


def generate_single_feature_deep(
    reference_image_path: str,
    title: str = "",
    description: str = "",
    index: int = 1,
) -> Image.Image | None:
    """
    B3~B6: Single feature deep-dive card. Rich content:
    Top half = product close-up photo, bottom half = big headline + multi-line
    explanation + 3 bullet data points.
    """
    print(f"\n[Qwen B{index+2}] Deep feature #{index} — {title[:30]}...")

    t = title or "Premium Quality"
    d = description or "Crafted with finest materials."

    prompt = (
        f"E-commerce detail page FEATURE DEEP-DIVE #{index}. "
        f"TOP 45%: A full-width beautiful close-up product photo of this product, "
        f"showing the specific detail relevant to the feature, soft warm studio lighting, "
        f"shallow depth of field, macro lens feel. "
        f"BOTTOM 55%: Warm beige text panel. Layout from top to bottom: "
        f"1) Large bold headline '{t}' in elegant serif font (dark charcoal). "
        f"2) A horizontal thin gold divider line. "
        f"3) Rich feature explanation (3-4 detailed sentences): "
        f"'{d}. This carefully crafted detail ensures lasting quality and comfort. "
        f"Each piece undergoes rigorous inspection before reaching you. "
        f"A truly premium experience designed for those who appreciate fine craftsmanship.' "
        f"Ample breathing space between sections. Text is the hero here — make it readable and substantial. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=reference_image_path, n=1)
    return images[0] if images else None


def generate_comparison_card(
    reference_image_path: str,
    product_name: str = "",
) -> Image.Image | None:
    """
    B7: Comparison card — Left side "Ordinary Products" pain points,
    Right side "Our {product}" solutions, highlighting our advantages.
    """
    print("\n[Qwen B7] Comparison card...")

    product = product_name or "Our Product"

    prompt = (
        f"E-commerce detail page SECTION — WHY CHOOSE US. "
        f"LAYOUT: Header 'WHY {product.upper()}?' in large bold serif at top. "
        f"Below: TWO columns side by side. "
        f"LEFT COLUMN (45%): 'ORDINARY PRODUCTS' as header in muted gray. "
        f"Below: red X marks with pain points — "
        f"'✗ Inconsistent quality' '✗ Rough unfinished edges' "
        f"'✗ Artificial fragrance' '✗ One-size, uncomfortable' "
        f"'✗ No quality guarantee'. "
        f"RIGHT COLUMN (55%): 'OUR {product.upper()}' as header in elegant gold. "
        f"Below: green checkmarks with solutions — "
        f"'✓ 100% genuine Indian sandalwood, naturally fragrant' "
        f"'✓ Each bead hand polished to silky finish' "
        f"'✓ Adjustable elastic fits all wrists comfortably' "
        f"'✓ Premium 2-year quality promise included' "
        f"'✓ Over 10,000 happy customers worldwide'. "
        f"Bottom: a thin divider line. "
        f"Colors: left side muted cool gray tones, right side warm gold & beige tones. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=reference_image_path, n=1)
    return images[0] if images else None


def generate_detail_module_b3(
    reference_image_path: str,
    material_desc: str = "",
    specs_d: dict | None = None,
) -> Image.Image | None:
    """
    B3: Material & Craft — left text + right detail photo.
    Deep dive into materials and workmanship.
    img2img with detail product photo reference.
    """
    print("\n[Qwen B3] Material & Craft...")

    mat = material_desc or "Crafted with premium materials for lasting quality."
    specs_text = ""
    if specs_d:
        specs_text = " | ".join(f"{k}: {v}" for k, v in list(specs_d.items())[:4])

    prompt = (
        f"E-commerce detail page SECTION 3 — MATERIAL & CRAFT. "
        f"LEFT 40%: text panel on warm beige — header 'MATERIAL & CRAFT' in bold serif, "
        f"body text '{mat}', below it key specs '{specs_text}' in small elegant type. "
        f"RIGHT 60%: a large macro detail photo of the product, showing fine texture, "
        f"material grain, craftsmanship details, soft studio lighting, shallow depth of field. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=reference_image_path, n=1)
    return images[0] if images else None


def generate_detail_module_b4(
    reference_image_path: str,
    scene_descriptions: list[str] | None = None,
) -> Image.Image | None:
    """
    B4: Usage Scenes — 2-3 lifestyle scene cards in a row.
    Helps user visualize product in their life.
    img2img with scene product photo reference.
    """
    print("\n[Qwen B4] Lifestyle scenes...")

    scenes = scene_descriptions or ["Daily Commute", "Office Style", "Weekend Casual"]
    scene_lines = []
    for i, s in enumerate(scenes[:3]):
        scene_lines.append(f"Scene {i+1}: {s}")
    scene_text = "\n".join(scene_lines)

    prompt = (
        f"E-commerce detail page SECTION 4 — LIFESTYLE SCENES. "
        f"A header 'IN EVERY MOMENT' in elegant serif at top. "
        f"Below: 3 horizontal scene cards in a row, each a lifestyle photo of the product "
        f"in a real setting: {scene_text}. "
        f"Under each photo: a small text label naming the scene. "
        f"Photos should feel real, warm natural lighting, candid moments. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=reference_image_path, n=1)
    return images[0] if images else None


def generate_detail_module_b5(
    reference_image_path: str,
    brand: str = "",
) -> Image.Image | None:
    """
    B5: Gift & Added Value — gift packaging, color options, personalization.
    img2img with scene/model photo reference.
    """
    print("\n[Qwen B5] Gift & Added Value...")

    brand_name = brand.upper() if brand else "BRAND"

    prompt = (
        f"E-commerce detail page SECTION 5 — GIFT & VALUE. "
        f"LEFT HALF: a beautifully arranged gift box photo, elegant packaging, "
        f"ribbon detail, with label 'PERFECT GIFTS' in elegant serif. "
        f"RIGHT HALF: text on warm beige — 'ALSO AVAILABLE IN' header, "
        f"showing color/material variants as small swatch circles with names below. "
        f"A warm, gift-worthy premium feel. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=reference_image_path, n=1)
    return images[0] if images else None


def generate_detail_module_b11(
    specs: dict | None = None,
) -> Image.Image | None:
    """
    B11: Specifications — clean spec table.
    text2img (no reference needed).
    """
    print("\n[Qwen B11] Specifications...")

    specs_text = ""
    if specs:
        spec_lines = [f"• {k}: {v}" for k, v in specs.items()]
        specs_text = "\n".join(spec_lines)
    else:
        specs_text = "• Material: Premium\n• Weight: Lightweight\n• Care: Easy maintenance"

    prompt = (
        f"E-commerce detail page SECTION — SPECIFICATIONS. "
        f"'SPECIFICATIONS' as a large bold serif header. "
        f"Below: a clean, well-spaced specification list on warm beige: "
        f"{specs_text}. "
        f"Each spec in elegant typography, label bold, value in refined thin font. "
        f"Easy to scan, lots of white space. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=None, n=1)
    return images[0] if images else None


def generate_detail_module_b12(
    brand: str = "",
    product_name: str = "",
) -> Image.Image | None:
    """
    B12: FAQ — 3-4 common questions and answers.
    text2img (no reference needed).
    """
    print("\n[Qwen B12] FAQ...")

    product = product_name or "this product"
    b = brand or "our brand"

    prompt = (
        f"E-commerce detail page SECTION — FREQUENTLY ASKED QUESTIONS. "
        f"'FAQ' as a large bold serif header. "
        f"Below: 3 question-answer pairs in an elegant accordion-like layout on warm beige: "
        f"Q1: 'Is {product} suitable for sensitive skin?' "
        f"A1: 'Absolutely. All materials are hypoallergenic and tested for safety.' "
        f"Q2: 'How do I care for {product}?' "
        f"A2: 'Keep dry, avoid harsh chemicals, store in the included pouch.' "
        f"Q3: 'What if I am not satisfied?' "
        f"A3: 'We offer a 30-day no-questions-asked return policy.' "
        f"Q4: 'Is it gift-ready?' "
        f"A4: 'Yes! Each piece comes in an elegant gift box, perfect for gifting.' "
        f"Each QA pair: question in bold serif, answer in refined thin font below. "
        f"Generous spacing between pairs. A thin divider line between each QA. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=None, n=1)
    return images[0] if images else None


def generate_detail_module_b13(
    brand: str = "",
) -> Image.Image | None:
    """
    B13: CTA — SHOP NOW + brand + bottom assurance strip.
    text2img (no reference needed).
    """
    print("\n[Qwen B13] CTA...")

    brand_name = brand.upper() if brand else "BRAND"

    prompt = (
        f"E-commerce detail page SECTION — CALL TO ACTION. "
        f"Full-width dark charcoal background strip. "
        f"Center vertically: large elegant 'SHOP NOW' text with a subtle golden glow or underline effect. "
        f"Below: '{brand_name}' in refined smaller serif font. "
        f"Very bottom edge: 'Free Shipping | Easy Returns | Secure Checkout' in micro text. "
        f"Clean, powerful, no clutter. The final nudge. "
        f"{STYLE_SUFFIX}. Aspect ratio 3:4 portrait."
    )

    images = _call_qwen(prompt, reference_image_path=None, n=1)
    return images[0] if images else None


# ============================================================
# C — Pillow: vertical stitching
# ============================================================

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a sans-serif font, falling back gracefully."""
    font_paths = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/seguisb.ttf"),
        ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Helvetica.ttc"),
    ]
    idx = 1 if bold else 0
    for pair in font_paths:
        if os.path.exists(pair[idx]):
            try:
                return ImageFont.truetype(pair[idx], size)
            except Exception:
                continue
    return ImageFont.load_default()


def stitch_detail_long_image(
    b1=None, b2=None, b3=None, b4=None, b5=None, b6=None,
    b7=None, b8=None, b9=None, b10=None, b11=None,
    b12=None, b13=None,
    target_width: int = 1080,
) -> Image.Image | None:
    """
    Vertically stitch B1~B11 into a complete detail page long image.
    All images resized to target_width, missing ones skipped.
    """
    print("\n[Pillow] Stitching detail long image...")

    all_images = [b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13]
    pieces = []
    for i, img in enumerate(all_images):
        if img is None:
            print(f"  [Pillow] B{i+1} is None, skipping")
            continue
        ratio = target_width / img.width
        new_h = int(img.height * ratio)
        resized = img.resize((target_width, new_h), Image.LANCZOS)
        pieces.append(resized)
        print(f"  [Pillow] B{i+1}: {resized.size}")

    if not pieces:
        print("[Pillow] No images to stitch")
        return None

    total_h = sum(p.height for p in pieces)
    result = Image.new("RGB", (target_width, total_h), (255, 255, 255))

    y = 0
    for p in pieces:
        result.paste(p, (0, y))
        y += p.height

    print(f"[Pillow] Done: {result.size}")
    return result


# ============================================================
# Main — generate all images
# ============================================================

def generate_all_images(
    reference_image_path: str,
    product_name: str = "",
    brand: str = "",
    selling_points: list[str] | None = None,
    scene_descriptions: list[str] | None = None,
    tagline: str = "",
    material_desc: str = "",
    specs_d: dict | None = None,
) -> dict:
    """
    Generate ALL images for a product: 9 product photos + 3 detail modules + 1 long detail page.

    Args:
        reference_image_path: path to the reference product image
        product_name: product name
        brand: brand name
        selling_points: list of 3-5 selling point strings (emoji + title)
        scene_descriptions: list of scene descriptions for B3
        tagline: emotional tagline for B1 hero banner
        material_desc: material description for B2 quality section
        specs_d: specifications dict for B3 specs section

    Returns:
        dict with keys:
            "product_photos": list of dicts (type, url, image)
            "detail_b1": PIL Image or None
            "detail_b2": PIL Image or None
            "detail_b3": PIL Image or None
            "detail_long": PIL Image or None (B1+B2+B3 stitched)
            "status": str
    """
    sp_list = selling_points or []
    sp_text = ", ".join(sp_list[:5]) if sp_list else ""

    result = {
        "product_photos": [],
        "detail_b1": None,
        "detail_b2": None,
        "detail_b3": None,
        "detail_b4": None,
        "detail_b5": None,
        "detail_b6": None,
        "detail_long": None,
        "status": "",
    }

    if not reference_image_path or not os.path.exists(reference_image_path):
        result["status"] = "Reference image not found."
        return result

    # ---- Step 1: Generate 9 product photos ----
    print("=" * 60)
    print("STEP 1: Generating 9 product photos via Seedream 5.0")
    print("=" * 60)

    product_photos = generate_product_photos(
        reference_image_path=reference_image_path,
        product_name=product_name,
        brand=brand,
        selling_points=sp_text,
        num_images=9,
    )
    result["product_photos"] = product_photos

    if not product_photos:
        result["status"] = "Failed to generate product photos."
        return result

    # Assign each product photo a role
    # Strategy: img0=white bg, img1-3=scenes, img4-5=details, img6-7=angles, img8=model
    n = len(product_photos)
    imgs = [p["image"] for p in product_photos if p["image"]]

    def _get_img(idx, fallback_idx=0):
        if idx < len(imgs):
            return imgs[idx]
        return imgs[fallback_idx] if imgs else None

    white_bg_img = _get_img(0)
    scene_imgs = [imgs[i] for i in [1, 2, 3] if i < len(imgs)]
    detail_imgs = [imgs[i] for i in [4, 5] if i < len(imgs)]
    model_img = _get_img(8, n-1)

    # Fill gaps
    if not scene_imgs:
        scene_imgs = [imgs[i] for i in range(min(3, len(imgs)))]
    if not detail_imgs:
        detail_imgs = [imgs[i] for i in range(min(2, len(imgs)))]

    # Save reference images to temp files
    import tempfile
    def _save_temp(img, prefix):
        if img is None:
            return None
        t = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, prefix=prefix)
        img.save(t.name, format="JPEG", quality=95)
        t.close()
        return t

    tmp_white = _save_temp(white_bg_img, "tk_white_")
    tmp_model = _save_temp(model_img, "tk_model_")

    # B2~B5 each needs a different reference image
    ref_images = [white_bg_img] + scene_imgs + detail_imgs  # up to 6 refs
    ref_temps = [_save_temp(img, f"tk_ref{i}_") for i, img in enumerate(ref_images) if img]

    def _get_ref(i):
        """Get the i-th unique reference image temp path."""
        if i < len(ref_temps) and ref_temps[i]:
            return ref_temps[i].name
        return tmp_white.name if tmp_white else None

    # ---- Step 2: Generate 4 detail module images ----
    print("\n" + "=" * 60)
    print("STEP 2: Generating 4 detail module images via Qianwen")
    print("=" * 60)

    # B1: Main visual (img2img with white bg) — now includes tagline
    result["detail_b1"] = generate_detail_module_b1(
        white_bg_image_path=tmp_white.name,
        brand=brand,
        product_name=product_name,
        tagline=tagline if tagline else "",
    )

    # B2: Quick feature scan — use the full selling points text
    # Build 4 feature cards each with short keyword + micro description
    b2_features = []
    for i in range(0, min(len(sp_list), 8), 2):
        title = sp_list[i] if i < len(sp_list) else ""
        desc = sp_list[i+1] if i+1 < len(sp_list) else ""
        if title:
            b2_features.append({"title": title[:30], "desc": desc[:60]})
    # Ensure 4 features
    defaults = [
        {"title": "PREMIUM QUALITY", "desc": "Finest materials and craftsmanship"},
        {"title": "VERSATILE DESIGN", "desc": "Perfect for any occasion or style"},
        {"title": "LIGHTWEIGHT COMFORT", "desc": "All-day wear without fatigue"},
        {"title": "TRUSTED BY THOUSANDS", "desc": "Loved by customers worldwide"},
    ]
    while len(b2_features) < 4:
        b2_features.append(defaults[len(b2_features)])

    result["detail_b2"] = generate_detail_module_b2(
        reference_image_path=_get_ref(0),
        features=b2_features,
    )

    # B3: Material & Craft — deep dive (img2img with detail photo)
    result["detail_b3"] = generate_detail_module_b3(
        reference_image_path=_get_ref(1),
        material_desc=material_desc if material_desc else "",
        specs_d=specs_d if specs_d else None,
    )

    # B4: Lifestyle Scenes — 2-3 scene cards (img2img with scene photo)
    result["detail_b4"] = generate_detail_module_b4(
        reference_image_path=_get_ref(2),
        scene_descriptions=scene_descriptions,
    )

    # B5: Gift & Added Value (img2img with scene/model photo)
    result["detail_b5"] = generate_detail_module_b5(
        reference_image_path=_get_ref(3),
        brand=brand,
    )

    # B6: Specs + CTA (img2img with model photo)
    result["detail_b6"] = generate_detail_module_b6(
        reference_image_path=tmp_model.name if tmp_model else _get_ref(0),
        specs=specs_d if specs_d else None,
        brand=brand,
    )

    # Cleanup temp files
    try:
        for t in [tmp_white, tmp_model] + ref_temps:
            if t:
                os.unlink(t.name)
    except OSError:
        pass

    # ---- Step 3: Stitch detail long image ----
    print("\n" + "=" * 60)
    print("STEP 3: Stitching detail long image (B1+B2+B3+B4+B5+B6)")
    print("=" * 60)

    result["detail_long"] = stitch_detail_long_image(
        b1=result["detail_b1"],
        b2=result["detail_b2"],
        b3=result["detail_b3"],
        b4=result["detail_b4"],
        b5=result["detail_b5"],
        b6=result["detail_b6"],
    )

    # Build status
    n_photos = len(product_photos)
    status_parts = [f"  Product photos: {n_photos}/9 generated"]
    for i in range(1, 7):
        key = f"detail_b{i}"
        ok = result.get(key) is not None
        status_parts.append(f"  Detail B{i}: {'OK' if ok else 'FAILED'}")
    status_parts.append(f"  Detail long image: {'OK' if result['detail_long'] is not None else 'FAILED'}")
    result["status"] = "\n".join(status_parts)

    return result


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("DETAIL-ONLY TEST — 13-section detail page")
    print("=" * 60)

    import pathlib
    base = pathlib.Path("C:/Users/周潇雨/Desktop/tk_listing_agent")
    v3_dir = base / "test_output_v3"
    ref_img = str((base / "木.png").resolve())

    def _load_or_ref(paths, fallback):
        for p in paths:
            if p.exists():
                return Image.open(str(p)).convert("RGB")
        return Image.open(fallback).convert("RGB") if fallback else None

    white_bg = _load_or_ref([v3_dir / "product_01.jpg"], ref_img)
    detail1 = _load_or_ref([v3_dir / "product_05.jpg"], ref_img)
    detail2 = _load_or_ref([v3_dir / "product_06.jpg"], ref_img)
    scene1  = _load_or_ref([v3_dir / "product_02.jpg"], ref_img)
    scene2  = _load_or_ref([v3_dir / "product_03.jpg"], ref_img)
    model   = _load_or_ref([v3_dir / "product_09.jpg"], ref_img)

    import tempfile
    def _save_temp(img, prefix):
        t = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, prefix=prefix)
        img.save(t.name, format="JPEG", quality=95)
        t.close()
        return t

    tref = [
        _save_temp(white_bg, "tk_ref0_"),
        _save_temp(detail1, "tk_ref1_"),
        _save_temp(detail2, "tk_ref2_"),
        _save_temp(scene1, "tk_ref3_"),
        _save_temp(scene2, "tk_ref4_"),
        _save_temp(model, "tk_ref5_"),
    ]

    def _ref(i):
        return tref[i].name if i < len(tref) and tref[i] else tref[0].name

    sp_lst = [
        "NATURAL SANDALWOOD",
        "Genuine Indian sandalwood, naturally fragrant for years, calming aroma",
        "HAND POLISHED FINISH",
        "Each bead individually hand polished to silky smooth satin finish",
        "ADJUSTABLE ELASTIC FIT",
        "Flexible elastic cord fits 15-20cm wrists, easy slip-on, secure hold",
        "AUTHENTIC ZEN STYLE",
        "Minimalist Tibetan-inspired design for meditation, yoga & daily elegance",
    ]

    brand = "ZEN & SOUL"
    product = "Wooden Bead Bracelet"
    tagline = "Find your inner peace"
    material_desc = "Genuine Indian sandalwood beads, hand polished, naturally aromatic. Each bracelet unique with natural wood grain. Reinforced elastic for durability."
    scenes = ["Meditation & Yoga", "Daily Office Wear", "Weekend Casual"]
    specs_d = {
        "Material": "Genuine Sandalwood", "Bead Size": "8mm diameter",
        "Wrist Size": "Adjustable 15-20cm", "Weight": "~20g",
        "Care": "Keep dry, avoid chemicals",
    }

    sp_pairs = []
    for i in range(0, len(sp_lst), 2):
        sp_pairs.append((sp_lst[i], sp_lst[i+1] if i+1 < len(sp_lst) else ""))

    print("\n--- B1 Hero ---")
    b1 = generate_detail_module_b1(white_bg_image_path=_ref(0), brand=brand, product_name=product, tagline=tagline)

    print("\n--- B2 Feature Overview ---")
    b2_features = [{"title": sp_pairs[i][0][:30], "desc": sp_pairs[i][1][:60]} for i in range(4)]
    b2 = generate_detail_module_b2(reference_image_path=_ref(0), features=b2_features)

    print("\n--- B3~B6 Deep Features ---")
    refs_for_features = [_ref(1), _ref(2), _ref(3), _ref(4)]
    b3 = generate_single_feature_deep(reference_image_path=refs_for_features[0], title=sp_pairs[0][0], description=sp_pairs[0][1], index=1)
    b4 = generate_single_feature_deep(reference_image_path=refs_for_features[1], title=sp_pairs[1][0], description=sp_pairs[1][1], index=2)
    b5 = generate_single_feature_deep(reference_image_path=refs_for_features[2], title=sp_pairs[2][0], description=sp_pairs[2][1], index=3)
    b6 = generate_single_feature_deep(reference_image_path=refs_for_features[3], title=sp_pairs[3][0], description=sp_pairs[3][1], index=4)

    print("\n--- B7 Comparison ---")
    b7 = generate_comparison_card(reference_image_path=_ref(1), product_name=product)

    print("\n--- B8 Material & Craft ---")
    b8 = generate_detail_module_b3(reference_image_path=_ref(1), material_desc=material_desc, specs_d=specs_d)

    print("\n--- B9 Lifestyle Scenes ---")
    b9 = generate_detail_module_b4(reference_image_path=_ref(3), scene_descriptions=scenes)

    print("\n--- B10 Gift & Value ---")
    b10 = generate_detail_module_b5(reference_image_path=_ref(4), brand=brand)

    print("\n--- B11 Specifications ---")
    b11 = generate_detail_module_b11(specs=specs_d)

    print("\n--- B12 FAQ ---")
    b12 = generate_detail_module_b12(brand=brand, product_name=product)

    print("\n--- B13 CTA ---")
    b13 = generate_detail_module_b13(brand=brand)

    print("\n--- Stitching ---")
    all_b = [b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13]
    detail_long = stitch_detail_long_image(
        b1=b1, b2=b2, b3=b3, b4=b4, b5=b5, b6=b6,
        b7=b7, b8=b8, b9=b9, b10=b10, b11=b11,
        b12=b12, b13=b13,
    )

    import os as _os
    out_dir = str(base / "test_output_v5")
    _os.makedirs(out_dir, exist_ok=True)

    names = ["b1_hero", "b2_features", "b3_feat1", "b4_feat2", "b5_feat3", "b6_feat4",
             "b7_compare", "b8_material", "b9_scenes", "b10_gift",
             "b11_specs", "b12_faq", "b13_cta"]
    for i, img in enumerate(all_b):
        if img:
            fname = f"{out_dir}/{names[i]}.jpg"
            img.save(fname, quality=95)
            print(f"Saved: {fname}")

    if detail_long:
        detail_long.save(f"{out_dir}/detail_long_final.jpg", quality=95)
        print(f"Saved: {out_dir}/detail_long_final.jpg")

    for t in tref:
        try: _os.unlink(t.name)
        except: pass

    print(f"\nDone! Outputs: {out_dir}")
