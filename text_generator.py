import os
import re
from collections import Counter
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "ID")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

COUNTRY_NAMES = {"PH": "Philippines", "TH": "Thailand", "MY": "Malaysia", "ID": "Indonesia"}
COUNTRY_STYLE = {
    "PH": "durability and practicality",
    "TH": "aesthetics and design",
    "MY": "versatility and multi-purpose use",
    "ID": "trendiness and fashion-forward style",
}

TITLE_RULES = """
【Title Rules — TikTok Shop Standard】

Length:
- 80-150 total characters (keep within 150 for mobile display)
- Place core keyword within the first 30-40 characters

Forbidden Words (NEVER use):
- Marketing/promotional: "Best", "Cheap", "50% OFF", "Free Shipping", "Sale", "Limited", "Buy Now"
- Superlatives: "Number One", "Top", "Amazing", "Incredible"
- Guarantee: "100%", "Guaranteed", "Promise"

Forbidden Symbols:
- NO exclamation marks (!!), NO emojis
- NO: | - # * / @
- ONLY: letters, digits, spaces, commas

Compatibility Rule:
- Accessories MUST use "for" (e.g., "Case for iPhone" NOT "iPhone Case")

Title Structure — Modular Formula:
Build the title by filling these 3 modules in order (pick 1-3 items per module):

Module 1 — CORE KEYWORD (MUST come first):
  Product name, category name, local common name
  Examples: T-Shirt, Phone Case, Necklace, Bracelet, Yoga Pants

Module 2 — ATTRIBUTE / FEATURE (follows immediately after core):
  Material, color, style, size, function features, quantity
  Examples: Cotton, Striped, High-Waist, Breathable, 925 Silver, Adjustable, Waterproof

Module 3 — SCENE / AUDIENCE / LONG-TAIL (placed at the end):
  Target audience, season, occasion, compatibility, design traits
  Examples: for Women, Summer Top, for Travel, for Yoga, Unisex Gift, Boho Style

CORRECT example (80-150 chars):
  Men Cotton Striped T-Shirt, Breathable Casual Summer Top for Travel
  → Core=T-Shirt, Attr=Men/Cotton/Striped/Breathable, Scene=Casual Summer/for Travel

WRONG example (too long, forbidden words, core buried):
  Best Amazing Summer Top for Men Travel Cotton T-Shirt Breathable
  → Forbidden words used, core keyword not first, structure broken

Keyword Density:
- Same core keyword at most 2 times
- Total keyword density: 5%-10% of title length
"""

DESCRIPTION_RULES = """
【Selling Point Rules】
Generate exactly 5 selling points, each with:
  Line 1: emoji + One-liner core benefit (7 words max)
  Line 2: Supporting detail (8-12 words)

The 5 selling points must cover:
  1. Material / Quality — what it's made of, why it feels premium
  2. Core Function — what problem it solves, the key feature
  3. Usage Scenario — when and where to use it
  4. Style / Color Options — variety, how to match
  5. Quality / Service — guarantee, shipping, after-sales

TRENDING WORD INJECTION RULE: The "positive_keywords" list contains REAL trending search terms from TikTok. You MUST weave 2-3 of these trending words into the selling points and QA section. These words are what real buyers are searching for — using them makes your listing discoverable.

Writing principles:
  - Turn features into user benefits (not "waterproof fabric" but "rain? no worries!")
  - Use specific numbers (e.g. "4 spacious pockets", "3 stylish colors")
  - Conversational tone, like chatting with a friend
  - Naturally include trending keywords from what buyers are searching for

Good example:
🌿 Premium Canvas That Lasts
Thick fabric with waterproof coating, perfect for daily use and sudden rain!
👜 Holds Everything You Need
4 spacious pockets keep phone, wallet, keys and makeup organized!
🎨 3 Stylish Colors Available
Black beige and pink, easy to match with any outfit!

【QA Rules】
- Generate 3-5 Q&A pairs based on the product and common buyer concerns
- Answers should be concise and reassuring
- Address sizing, material care, shipping, or usage doubts

【Caution Rules】
- Based on negative review keywords, remind users of potential issues
- Frame positively — set expectations, don't scare buyers
- Keep it brief, 1-2 items max
"""

HASHTAG_RULES = """
【Hashtag Rules】
- 8-10 hashtags total
- First 2: product + category tags
- Middle 3-5: scene / style / audience tags
- Last 2-3: trending + localized tags
- All lowercase
- Reference trending tags: #fyp #foryou #fypシ #trending #style #fashion #quality #favorite
"""

MARKET_STYLE = """
【Market Style Reference - Target Country: {country}】
Style focus: {style}
"""


def _chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 2048) -> str | None:
    """Call DeepSeek chat API and return content string."""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[deepseek] API error: {e}")
        return None


def _build_title_prompt(brand: str, main_keyword: str, hot_keywords: str, crowd_keywords: str,
                        attributes: str, functions: str, selling_points: str) -> str:
    country = COUNTRY_NAMES.get(TARGET_COUNTRY, TARGET_COUNTRY)
    style = COUNTRY_STYLE.get(TARGET_COUNTRY, "trendiness and fashion")
    return f"""You are a TikTok Shop copywriting expert targeting the {country} market (style: {style}).

{TITLE_RULES}

【Product Information】
- Brand: {brand}
- Main Keyword: {main_keyword}
- Hot / Trend Keywords: {hot_keywords}
- Target Audience Keywords: {crowd_keywords}
- Product Attributes: {attributes}
- Product Functions: {functions}
- Key Selling Points: {selling_points}

CRITICAL: Each title MUST be 80-150 total characters. Verify each title is within 150 chars.
Build titles using the 3-module formula: [Core Keyword] + [Attribute/Feature Words] + [Scene/Audience Words].
Core keyword MUST be first, within the first 30-40 characters.
NEVER use forbidden words: Best, Cheap, 50% OFF, Free Shipping, Amazing, Top, Number One, Guaranteed.
NEVER use emojis, exclamation marks, or special symbols.
Accessories MUST use "for" (e.g., "Case for Phone" NOT "Phone Case").

HOT KEYWORD INJECTION RULE: You MUST incorporate hot keywords from the provided list into EVERY title. These are real trending search terms from TikTok — ignoring them means your titles won't rank. Pick the most relevant 2-3 hot keywords and weave them naturally into each title. Do NOT skip this step.

Generate exactly 3 English titles, each on its own line:

1. SEO Traffic Title (80-150 chars) — maximize TikTok search visibility, MUST include 2-3 hot keywords from the provided list
2. Conversion Title (80-150 chars) — strongest selling point + MUST include at least 1 hot keyword for trend relevance
3. Brand Tone Title (80-150 chars) — elegant brand feel + MUST include at least 1 hot keyword naturally woven in

Output format (each title on its own line, no numbering, no prefixes):
<Title 1>
<Title 2>
<Title 3>"""


def _shorten_title(brand: str, main_keyword: str, long_title: str) -> str | None:
    """Ask DeepSeek to shorten a title to under 80 characters."""
    prompt = f"""Shorten this TikTok product title to under 80 characters.
Rules: must include brand "{brand}", main keyword "{main_keyword}", a selling point, and a scene/audience word.
NO emojis, NO special symbols (| - # *).
Remove filler words while keeping the core meaning.

Long title ({len(long_title)} chars): {long_title}

Output only the shortened title (under 80 chars), nothing else."""
    content = _chat([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=128)
    if not content:
        return None
    short = content.strip()
    # Remove any quotes, numbering, or extra text
    short = re.sub(r'^["\']|["\']$', '', short)
    short = re.sub(r'^(?:\d+[\.\)]\s*|Shortened Title:\s*)', '', short).strip()
    return short if len(short) <= 80 else None


def generate_titles(
    brand: str,
    main_keyword: str,
    hot_keywords: str = "",
    crowd_keywords: str = "",
    attributes: str = "",
    functions: str = "",
    selling_points: str = "",
) -> list[str]:
    """
    Generate 3 TikTok-optimized product titles (SEO, conversion, brand tone).

    Returns: ["Title 1", "Title 2", "Title 3"], each ≤255 chars
    """
    print("[titles] generating 3 titles...")
    try:
        prompt = _build_title_prompt(
            brand, main_keyword, hot_keywords, crowd_keywords,
            attributes, functions, selling_points,
        )
        content = _chat(
            [{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=512,
        )
        if not content:
            print("[titles] API returned empty")
            return []

        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        # Remove numbering prefixes like "1." "2." "Title 1:" etc.
        cleaned = []
        for line in lines:
            line = re.sub(r"^(?:\d+[\.\)]\s*|Title\s*\d+[:\-]?\s*)", "", line).strip()
            if line and len(line) <= 255:
                cleaned.append(line)

        result = cleaned[:3]
        if len(result) < 3:
            while len(result) < 3 and cleaned:
                result.append(cleaned[len(result) % len(cleaned)])
        if not result:
            result = [f"{main_keyword} - {selling_points or 'Premium Quality'}"]

        # Enforce under 80 char limit: ask model to shorten any overlong titles
        for idx, t in enumerate(result):
            if len(t) > 80:
                short = _shorten_title(brand, main_keyword, t)
                if short and len(short) <= 80:
                    result[idx] = short

        print(f"[titles] generated {len(result)} titles")
        for i, t in enumerate(result):
            try:
                print(f"  {i+1}. [{len(t)} chars] {t[:60]}...")
            except UnicodeEncodeError:
                print(f"  {i+1}. [{len(t)} chars]")
        return result
    except Exception as e:
        print(f"[error] generate_titles failed: {e}")
        return [main_keyword]


def _build_desc_prompt(brand: str, main_keyword: str, selling_points: str,
                       positive_keywords: list[str], negative_keywords: list[str], faqs: list[str]) -> str:
    country = COUNTRY_NAMES.get(TARGET_COUNTRY, TARGET_COUNTRY)
    style = COUNTRY_STYLE.get(TARGET_COUNTRY, "trendiness and fashion")

    pos_str = ", ".join(positive_keywords) if positive_keywords else "N/A"
    neg_str = ", ".join(negative_keywords) if negative_keywords else "N/A"
    faq_str = "\n".join(f"- {q}" for q in faqs[:5]) if faqs else "N/A"

    return f"""You are a TikTok Shop copywriting expert targeting the {country} market (style: {style}).

【Product Information】
- Brand: {brand}
- Main Keyword: {main_keyword}
- Selling Points: {selling_points}
- What Buyers Love (positive keywords): {pos_str}
- What Buyers Complain About (negative keywords): {neg_str}
- Common Questions from Buyers:
{faq_str}

{DESCRIPTION_RULES}

{MARKET_STYLE.format(country=country, style=style)}

Output EXACTLY in this JSON format (no markdown, no code blocks, pure JSON):
{{
  "selling_points": [
    "emoji + One-liner (7 words max)\\nSupporting detail (8-12 words)",
    ...5 items total
  ],
  "qa": [
    "Q: question?\\nA: answer.",
    ...3-5 items
  ],
  "cautions": [
    "caution text",
    ...1-2 items
  ]
}}"""


def generate_description(
    brand: str,
    main_keyword: str,
    selling_points: str = "",
    positive_keywords: list[str] | None = None,
    negative_keywords: list[str] | None = None,
    faqs: list[str] | None = None,
) -> dict:
    """
    Generate TikTok product description with selling points, QA, and cautions.

    Returns: {"selling_points": [str, ...], "qa": [str, ...], "cautions": [str, ...]}
    """
    print("[desc] generating description...")
    try:
        prompt = _build_desc_prompt(
            brand, main_keyword, selling_points,
            positive_keywords or [], negative_keywords or [], faqs or [],
        )
        content = _chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1536,
        )
        if not content:
            print("[desc] API returned empty")
            return {"selling_points": [], "qa": [], "cautions": []}

        # Parse JSON from response (handle possible markdown wrapping)
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        import json
        result = json.loads(content)

        out = {
            "selling_points": result.get("selling_points", [])[:5],
            "qa": result.get("qa", [])[:5],
            "cautions": result.get("cautions", [])[:2],
        }
        print(f"[desc] generated {len(out['selling_points'])} selling points, "
              f"{len(out['qa'])} QA pairs, {len(out['cautions'])} cautions")
        return out
    except json.JSONDecodeError as e:
        print(f"[error] JSON parse failed: {e}")
        return {"selling_points": [], "qa": [], "cautions": []}
    except Exception as e:
        print(f"[error] generate_description failed: {e}")
        return {"selling_points": [], "qa": [], "cautions": []}


def _build_hashtag_prompt(main_keyword: str, category_keyword: str,
                           scene_keywords: str, crowd_keywords: str, market: str) -> str:
    market_styles = {
        "PH": "durability and practicality — use tags like #matibay #sulit #pangmatagalan",
        "TH": "aesthetics and design — use tags like #สวยมาก #ดีไซน์เก๋ #ของดีบอกต่อ when appropriate",
        "MY": "versatility and multi-purpose — use tags like #multipurpose #versatile #bolehpakai",
        "ID": "trendiness and fashion — use tags like #fashion #trending #kekinian #fyp",
        "US": "general trending — use tags like #fyp #foryou #trending #viral",
    }
    style_guide = market_styles.get(market, market_styles["US"])

    return f"""You are a TikTok Shop hashtag expert. Generate hashtags for a product listing targeting the {market} market.

Market style: {style_guide}

【Product Info】
- Main Keyword: {main_keyword}
- Category: {category_keyword}
- Scene Keywords: {scene_keywords}
- Audience Keywords: {crowd_keywords}

【Hashtag Rules】
- Generate exactly 8-10 hashtags
- ALL lowercase, NO spaces, NO special symbols (only letters and numbers)
- Structure:
  * First 2: product word + category word (from main_keyword and category_keyword)
  * Middle 3-5: scene / style / audience tags (from scene_keywords and crowd_keywords)
  * Last 2-3: trending + localized tags
- Include # in front of each tag
- Reference trending tags: #fyp #foryou #fypシ #trending #style #fashion #quality #favorite

Output only the hashtags separated by spaces, nothing else. Example format:
#yogaleggings #activewear #gymstyle #homeworkout #fitnesslover #womenstyle #fyp #foryou #trending"""


def generate_hashtags(
    main_keyword: str,
    category_keyword: str = "",
    scene_keywords: str = "",
    crowd_keywords: str = "",
    market: str = "US",
) -> list[str]:
    """
    Generate 8-10 TikTok-optimized hashtags.

    Returns: ["#tag1", "#tag2", ...], all lowercase with # prefix
    """
    print(f"[hashtags] generating for {main_keyword}, market={market}...")
    try:
        prompt = _build_hashtag_prompt(
            main_keyword, category_keyword, scene_keywords, crowd_keywords, market,
        )
        content = _chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=256,
        )
        if not content:
            print("[hashtags] API returned empty")
            return []

        # Parse hashtags from response
        raw = content.strip()
        # Extract all #tags
        tags = re.findall(r"#[\w]+", raw)
        # Clean: lowercase, no special chars, deduplicate
        seen = set()
        result = []
        for tag in tags:
            clean = "#" + re.sub(r"[^a-z0-9]", "", tag[1:].lower())
            if clean not in seen and len(clean) > 1:
                seen.add(clean)
                result.append(clean)

        # Limit to 10, ensure at least 5
        result = result[:10]
        if len(result) < 5:
            # Fallback: build basic hashtags from inputs
            fallback = []
            if main_keyword:
                fallback.append("#" + re.sub(r"[^a-z0-9]", "", main_keyword.lower().replace(" ", "")))
            if category_keyword:
                fallback.append("#" + re.sub(r"[^a-z0-9]", "", category_keyword.lower().replace(" ", "")))
            fallback.extend(["#fyp", "#foryou", "#trending"])
            for fb in fallback:
                if fb not in seen:
                    seen.add(fb)
                    result.append(fb)
            result = result[:10]

        print(f"[hashtags] generated {len(result)} tags: {' '.join(result[:5])}...")
        return result
    except Exception as e:
        print(f"[error] generate_hashtags failed: {e}")
        return []


def _local_extract(text: str) -> list[str]:
    """Extract meaningful English words from text (simple tokenization)."""
    # Extract all alphabetic tokens, filter short words and common stopwords
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "you", "your", "yours",
        "they", "them", "their", "theirs", "we", "us", "our", "ours",
        "this", "that", "these", "those", "it", "its", "and", "but", "or",
        "nor", "not", "so", "as", "at", "by", "for", "from", "in", "into",
        "of", "on", "onto", "to", "with", "about", "up", "out", "if",
        "very", "just", "all", "also", "more", "some", "get", "got",
    }
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    filtered = [w for w in words if w not in stopwords]
    return filtered


def extract_keywords(texts_list: list[str]) -> str:
    """
    Extract high-value commercial keywords from a list of texts.

    Returns comma-separated keyword string.
    """
    print(f"[keywords] extracting from {len(texts_list)} texts...")
    try:
        all_words = []
        for text in texts_list:
            if text:
                all_words.extend(_local_extract(text))

        if not all_words:
            print("[keywords] no words found")
            return ""

        word_counts = Counter(all_words)
        top_words = [w for w, _ in word_counts.most_common(30)]

        if not top_words:
            return ""

        # Ask DeepSeek to filter for commercially valuable keywords
        prompt = f"""You are a TikTok Shop SEO expert.

From the following list of words extracted from product reviews and competitor copy, select the most commercially valuable keywords for TikTok Shop product listing.

Words: {", ".join(top_words)}

Rules:
- Select keywords with buying intent, product relevance, or search volume potential
- Prioritize: product type words > feature words > benefit words > style/mood words
- Output only the selected keywords as a comma-separated string
- Keep 10-15 keywords max
- All lowercase"""

        content = _chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=256,
        )
        if not content:
            # Fallback: return top local words
            result = ", ".join(top_words[:15])
            print(f"[keywords] fallback: {result}")
            return result

        # Clean up the response
        keywords_str = content.strip().lower()
        # Remove any non-keyword text
        keywords_str = re.sub(r"[^a-zA-Z,\s]", "", keywords_str)
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

        result = ", ".join(keywords[:15])
        print(f"[keywords] extracted {len(keywords)} keywords")
        return result
    except Exception as e:
        print(f"[error] extract_keywords failed: {e}")
        return ""
