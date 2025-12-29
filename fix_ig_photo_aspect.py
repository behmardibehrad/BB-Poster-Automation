import os, shutil
from PIL import Image, ImageFilter

PHOTOS_DIR = os.path.expanduser("~/BB-Poster-Automation/United_States/Nyssa_Bloom/Instagram/Photos")
BACKUP_DIR = os.path.expanduser("~/BB-Poster-Automation/backups/original_photos")

TARGET_W, TARGET_H = 1080, 1350  # 4:5 canvas for IG feed
MIN_AR, MAX_AR = 0.8, 1.91

def is_aspect_ok(w: int, h: int) -> bool:
    ar = w / h
    return MIN_AR <= ar <= MAX_AR

def fit_contain(im: Image.Image, tw: int, th: int) -> Image.Image:
    im = im.copy()
    im.thumbnail((tw, th), Image.LANCZOS)
    return im

def fit_cover(im: Image.Image, tw: int, th: int) -> Image.Image:
    w, h = im.size
    scale = max(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    return im.resize((nw, nh), Image.LANCZOS)

def pad_to_4x5_blur(src_path: str, dst_path: str) -> None:
    with Image.open(src_path) as im:
        im = im.convert("RGB")

        bg = fit_cover(im, TARGET_W, TARGET_H)
        left = (bg.size[0] - TARGET_W) // 2
        top  = (bg.size[1] - TARGET_H) // 2
        bg = bg.crop((left, top, left + TARGET_W, top + TARGET_H))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=18))

        fg = fit_contain(im, TARGET_W, TARGET_H)

        canvas = bg
        x = (TARGET_W - fg.size[0]) // 2
        y = (TARGET_H - fg.size[1]) // 2
        canvas.paste(fg, (x, y))

        canvas.save(dst_path, "JPEG", quality=92, optimize=True)

def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)

    files = sorted([
        f for f in os.listdir(PHOTOS_DIR)
        if f.lower().endswith((".jpg", ".jpeg"))
    ])

    fixed = 0
    for fn in files:
        photos_path = os.path.join(PHOTOS_DIR, fn)
        backup_path = os.path.join(BACKUP_DIR, fn)

        # Ensure a backup exists (copy from PHOTOS_DIR once), but NEVER modify backup
        if not os.path.exists(backup_path):
            shutil.copy2(photos_path, backup_path)

        # Always read from BACKUP_DIR as the source of truth
        src = backup_path

        try:
            with Image.open(src) as im:
                w, h = im.size
        except Exception as e:
            print(f"[SKIP] {fn}: cannot open source backup ({e})")
            continue

        if is_aspect_ok(w, h):
            # If already valid, ensure PHOTOS_DIR has the original (optional)
            # We do nothing to avoid extra writes.
            continue

        # Overwrite ONLY the PHOTOS_DIR file, using backup as input
        tmp = photos_path + ".tmp.jpg"
        pad_to_4x5_blur(src, tmp)
        os.replace(tmp, photos_path)

        fixed += 1
        print(f"[FIXED] {fn}: source={w}x{h} -> output={TARGET_W}x{TARGET_H} (PHOTOS_DIR overwritten, backup untouched)")

    print(f"\nDone. Fixed {fixed} image(s). Backups were only read from: {BACKUP_DIR}")

if __name__ == "__main__":
    main()
