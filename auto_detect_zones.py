"""
Auto-detect template zones by scanning *edge margins* — the pure background
strips on left/right sides are unaffected by text/images in the content area.
"""
import sys
from statistics import median_low
from PIL import Image, ImageDraw, ImageFont

# ---------- config ----------
TEMPLATE_PATH = "template_v2.jpg"
OUTPUT_PATH = "template_v2_auto_zones.jpg"

# The 4 background colours
PALETTE = {
    "white": (255, 255, 255),   # #FFFFFF
    "cream": (249, 246, 240),   # #F9F6F0
    "dark":  (44, 44, 44),      # #2C2C2C
    "beige": (245, 242, 235),   # #F5F2EB
}

# Expected top-to-bottom colour sequence of 9 zones
ZONE_COLOUR_SEQ = [
    "white",   # zone1 — title
    "white",   # zone2 — main image
    "cream",   # zone3 — description
    "dark",    # zone4 — colours
    "beige",   # zone5 — selling points
    "cream",   # zone6 — pain points
    "white",   # zone7 — scenes
    "beige",   # zone8 — specs
    "dark",    # zone9 — footer
]

ZONE_NAMES = [
    "zone1_title", "zone2_main_img", "zone3_desc",
    "zone4_colors", "zone5_selling", "zone6_pain",
    "zone7_scenes", "zone8_specs", "zone9_footer",
]

# Column ranges to sample for pure background (left + right edges)
EDGE_LEFT  = (0, 80)
EDGE_RIGHT = (-80, None)  # None = rightmost


def colour_dist(a: tuple, b: tuple) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def classify_colour(rgb: tuple) -> str:
    best_name, best_dist = "white", float("inf")
    for name, ref in PALETTE.items():
        d = colour_dist(rgb, ref)
        if d < best_dist:
            best_dist, best_name = d, name
    return best_name


def edge_median_colour(img: Image.Image, y: int) -> tuple:
    """Return median RGB from left + right edge strips of row y."""
    pixels = img.load()
    w = img.width
    samples = []
    # left edge
    for x in range(EDGE_LEFT[0], min(EDGE_LEFT[1], w)):
        samples.append(pixels[x, y])
    # right edge
    r_start = EDGE_RIGHT[0] if EDGE_RIGHT[0] >= 0 else w + EDGE_RIGHT[0]
    for x in range(r_start, w):
        samples.append(pixels[x, y])
    # median per channel
    rs = sorted(s[0] for s in samples)
    gs = sorted(s[1] for s in samples)
    bs = sorted(s[2] for s in samples)
    n = len(samples)
    return (rs[n // 2], gs[n // 2], bs[n // 2])


def scan_rows(img: Image.Image):
    """Return (labels, medians) for every row using edge-median colour."""
    h = img.height
    labels = []
    medians = []
    for y in range(h):
        mc = edge_median_colour(img, y)
        medians.append(mc)
        labels.append(classify_colour(mc))
    return labels, medians


def merge_runs(labels: list[str], min_run: int = 8) -> list[tuple[int, int, str]]:
    """Merge adjacent same-label rows, then absorb short runs into neighbours."""
    # 1. raw runs
    runs = []
    start = 0
    for y in range(1, len(labels)):
        if labels[y] != labels[start]:
            runs.append((start, y, labels[start]))
            start = y
    runs.append((start, len(labels), labels[start]))

    # 2. absorb short runs (< min_run px) into the longer neighbour
    merged = []
    for i, (s, e, lbl) in enumerate(runs):
        if e - s >= min_run or i == 0 or i == len(runs) - 1:
            merged.append([s, e, lbl])
        else:
            # absorb into the most recent entry in merged
            merged[-1][1] = e  # extend previous
    return [(s, e, lbl) for s, e, lbl in merged]


def collapse_to_sequence(
    runs: list[tuple[int, int, str]], expected_seq: list[str]
) -> list[dict]:
    """
    Map the detected colour runs onto the expected 9-zone sequence.
    Handles same-colour adjacent zones via complexity analysis.
    """
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    pixels = img.load()
    w = img.width

    def row_complexity(y: int) -> float:
        """Mean per-pixel deviation from row median across a centered sample strip."""
        cx = w // 2
        samples = [pixels[x, y] for x in range(cx - 120, cx + 120, 2)]
        n = len(samples)
        rs = sorted(s[0] for s in samples)
        gs = sorted(s[1] for s in samples)
        bs = sorted(s[2] for s in samples)
        med = (rs[n // 2], gs[n // 2], bs[n // 2])
        return sum(colour_dist(s, med) for s in samples) / n

    # Build a complexity curve
    print("[detect] computing complexity curve...")
    complexities = [row_complexity(y) for y in range(img.height)]

    # Group expected seq into blocks of same colour
    blocks = []
    i = 0
    while i < len(expected_seq):
        lbl = expected_seq[i]
        j = i
        while j < len(expected_seq) and expected_seq[j] == lbl:
            j += 1
        blocks.append((lbl, j - i))
        i = j

    # Match detected runs to expected blocks
    zones = []
    run_idx = 0

    for block_idx, (expected_lbl, count) in enumerate(blocks):
        if run_idx >= len(runs):
            # Fill remaining with equal splits
            if zones:
                remaining_h = img.height - (zones[-1]["y"] + zones[-1]["height"])
                per_zone = remaining_h // (9 - len(zones))
                cur_y = zones[-1]["y"] + zones[-1]["height"]
                for k in range(9 - len(zones)):
                    zones.append({"y": cur_y, "height": per_zone, "bg": expected_seq[len(zones)]})
                    cur_y += per_zone
            break

        s, e, detected_lbl = runs[run_idx]

        if detected_lbl == expected_lbl:
            # Match — may need to split if count > 1
            run_idx += 1
        else:
            # Mismatch — try next run
            print(f"  [warn] block {block_idx}: expected {expected_lbl}×{count}, "
                  f"got {detected_lbl} at y={s}-{e}")
            # Use the expected label but detected bounds
            run_idx += 1

        if count == 1:
            zones.append({"y": s, "height": e - s, "bg": expected_lbl})
        else:
            # Split a same-colour run into `count` pieces
            # Use complexity curve to find the best split point
            sub = _split_by_complexity(s, e, count, complexities)
            for y0, y1 in sub:
                zones.append({"y": y0, "height": y1 - y0, "bg": expected_lbl})

    # Assign names
    for i, z in enumerate(zones[:9]):
        z["name"] = ZONE_NAMES[i] if i < len(ZONE_NAMES) else f"zone{i+1}"

    return zones[:9]


def _split_by_complexity(
    y_start: int, y_end: int, count: int, complexities: list[float]
) -> list[tuple[int, int]]:
    """Split a y-range into `count` sub-ranges using complexity peaks/drops."""
    if count <= 1:
        return [(y_start, y_end)]

    # Smooth the complexity curve in this range
    window = 8
    smooth = []
    for y in range(y_start, y_end):
        lo = max(y_start, y - window)
        hi = min(y_end, y + window + 1)
        smooth.append(sum(complexities[lo:hi]) / (hi - lo))

    # For count=2, find the biggest step in smoothed complexity
    if count == 2:
        best_y = y_start + (y_end - y_start) // 2  # default: midpoint
        best_step = 0
        for i in range(15, len(smooth) - 15):
            step = abs(smooth[i + 1] - smooth[i - 1])
            if step > best_step:
                best_step = step
                best_y = y_start + i
        if best_step > 1.5:
            return [(y_start, best_y), (best_y, y_end)]

    # Fallback: proportional split
    total = y_end - y_start
    parts = []
    for i in range(count):
        p0 = y_start + round(total * i / count)
        p1 = y_start + round(total * (i + 1) / count)
        parts.append((p0, p1))
    return parts


def draw_markers(img: Image.Image, zones: list[dict]) -> Image.Image:
    marked = img.copy()
    draw = ImageDraw.Draw(marked)
    w = marked.width
    cols = ["#FF0000", "#CC0000", "#FF3333", "#FF6666", "#FF4444",
            "#DD0000", "#FF2222", "#EE0000", "#FF1111"]
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    for i, z in enumerate(zones):
        y0, h = z["y"], z["height"]
        y1 = y0 + h
        c = cols[i % len(cols)]
        draw.rectangle([(0, y0), (w - 1, y1 - 1)], outline=c, width=2)
        label = f"  {z['name']}  [{h}px | {z['bg']}]"
        tb = draw.textbbox((0, 0), label, font=font)
        draw.rectangle([(2, y0 + 2), (tb[2] + 8, y0 + tb[3] + 6)], fill=c)
        draw.text((5, y0 + 4), label, font=font, fill=(255, 255, 255))
    return marked


# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("Auto-Detect Template Zones  v2 (edge-margin scan)")
    print("=" * 55)

    img = Image.open(TEMPLATE_PATH).convert("RGB")
    print(f"\nImage: {img.width}×{img.height}")

    labels, medians = scan_rows(img)

    print("[detect] merging colour runs...")
    runs = merge_runs(labels)
    print(f"[detect] {len(runs)} runs after merge:")
    for s, e, lbl in runs:
        print(f"  y={s:4d} → {e:4d}  ({e - s:4d} px)  {lbl}")

    print("\n[detect] mapping to expected 9-zone sequence...")
    zones = collapse_to_sequence(runs, ZONE_COLOUR_SEQ)

    print(f"\n{'='*55}")
    print(f"DETECTED ZONES  ({len(zones)} zones)")
    print(f"{'='*55}")
    print(f"{'Name':<22} {'y':>5}  {'height':>6}  {'end':>5}  {'bg'}")
    print("-" * 55)
    for z in zones:
        print(f"{z['name']:<22} {z['y']:5d}  {z['height']:6d}  "
              f"{z['y'] + z['height']:5d}  {z['bg']}")

    print(f"\n{'='*55}")
    print("Copy into image_generator.py:")
    print(f"{'='*55}")
    print("TEMPLATE_ZONES_REFERENCE: dict[str, dict[str, int]] = {")
    for z in zones:
        print(f'    "{z["name"]}": {{"y": {z["y"]}, "height": {z["height"]}}},')
    print("}")

    marked = draw_markers(img, zones)
    marked.save(OUTPUT_PATH, quality=90)
    print(f"\n[output] {OUTPUT_PATH} saved")
