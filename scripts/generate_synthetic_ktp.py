import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CLAIM_FOLDER = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "document_claims"
    / "claim_001_valid"
)

CLAIM_RECORD_PATH = CLAIM_FOLDER / "claim_record.json"
OUTPUT_PATH = CLAIM_FOLDER / "documents" / "ktp.png"


def load_font(
    size: int,
    bold: bool = False,
):
    font_name = "seguisb.ttf" if bold else "segoeui.ttf"
    font_path = Path("C:/Windows/Fonts") / font_name

    if font_path.exists():
        return ImageFont.truetype(
            str(font_path),
            size=size,
        )

    fallback_name = "arialbd.ttf" if bold else "arial.ttf"
    fallback_path = Path("C:/Windows/Fonts") / fallback_name

    if fallback_path.exists():
        return ImageFont.truetype(
            str(fallback_path),
            size=size,
        )

    return ImageFont.load_default()


def load_claim_record() -> dict:
    if not CLAIM_RECORD_PATH.exists():
        raise FileNotFoundError(
            f"Claim record was not found: {CLAIM_RECORD_PATH}"
        )

    with CLAIM_RECORD_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def generate_ktp(
    claim_record: dict,
    output_path: Path = OUTPUT_PATH,
) -> None:
    width = 1600
    height = 1000

    image = Image.new(
        mode="RGB",
        size=(width, height),
        color="#f4f7fb",
    )

    draw = ImageDraw.Draw(image)

    title_font = load_font(48, bold=True)
    subtitle_font = load_font(27)
    notice_font = load_font(26, bold=True)
    label_font = load_font(23, bold=True)
    value_font = load_font(31)
    footer_font = load_font(20)

    # Main card
    draw.rounded_rectangle(
        (40, 40, width - 40, height - 40),
        radius=28,
        fill="#ffffff",
        outline="#b8c8d8",
        width=3,
    )

    # Blue header
    draw.rounded_rectangle(
        (40, 40, width - 40, 170),
        radius=28,
        fill="#245d8f",
    )

    # Cover the rounded bottom corners of the header
    draw.rectangle(
        (40, 130, width - 40, 170),
        fill="#245d8f",
    )

    draw.text(
        (85, 75),
        "MOCK KTP IDENTITY RECORD",
        font=title_font,
        fill="#ffffff",
    )

    draw.text(
        (85, 195),
        "Synthetic identity document for local demonstration testing",
        font=subtitle_font,
        fill="#52667a",
    )

    # Synthetic-document notice
    draw.rounded_rectangle(
        (85, 255, width - 85, 335),
        radius=12,
        fill="#fff0f0",
        outline="#d94b4b",
        width=2,
    )

    notice_text = (
        "SYNTHETIC DOCUMENT - FOR DEMONSTRATION ONLY"
    )

    notice_box = draw.textbbox(
        (0, 0),
        notice_text,
        font=notice_font,
    )

    notice_width = notice_box[2] - notice_box[0]

    draw.text(
        (
            (width - notice_width) / 2,
            278,
        ),
        notice_text,
        font=notice_font,
        fill="#a52424",
    )

    # Test-photo placeholder
    photo_left = 100
    photo_top = 390
    photo_right = 370
    photo_bottom = 740

    draw.rounded_rectangle(
        (
            photo_left,
            photo_top,
            photo_right,
            photo_bottom,
        ),
        radius=18,
        fill="#e8eef5",
        outline="#9fb3c8",
        width=2,
    )

    photo_text = "TEST\nPHOTO"

    photo_box = draw.multiline_textbbox(
        (0, 0),
        photo_text,
        font=label_font,
        spacing=12,
        align="center",
    )

    photo_text_width = photo_box[2] - photo_box[0]
    photo_text_height = photo_box[3] - photo_box[1]

    draw.multiline_text(
        (
            photo_left
            + ((photo_right - photo_left) - photo_text_width) / 2,
            photo_top
            + ((photo_bottom - photo_top) - photo_text_height) / 2,
        ),
        photo_text,
        font=label_font,
        fill="#627d98",
        spacing=12,
        align="center",
    )

    # KTP fields
    fields = [
        (
            "IDENTITY NUMBER",
            claim_record["identity_number"],
        ),
        (
            "FULL NAME",
            claim_record["customer_name"],
        ),
        (
            "DATE OF BIRTH",
            claim_record["date_of_birth"],
        ),
        (
            "ADDRESS",
            claim_record["address"],
        ),
    ]

    field_start_x = 440
    field_start_y = 395
    row_height = 135

    for index, (label, value) in enumerate(fields):
        current_y = field_start_y + (index * row_height)

        draw.text(
            (field_start_x, current_y),
            label,
            font=label_font,
            fill="#627d98",
        )

        draw.text(
            (field_start_x, current_y + 42),
            str(value),
            font=value_font,
            fill="#102a43",
        )

        draw.line(
            (
                field_start_x,
                current_y + 100,
                width - 110,
                current_y + 100,
            ),
            fill="#d9e2ec",
            width=2,
        )

    # Footer warning
    footer_text = (
        "Fictional values. This document is not valid for "
        "identification or any official transaction."
    )

    draw.text(
        (100, height - 95),
        footer_text,
        font=footer_font,
        fill="#7b8794",
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    image.save(
        output_path,
        format="PNG",
        optimize=True,
    )


def main() -> None:
    claim_record = load_claim_record()

    generate_ktp(
        claim_record=claim_record,
    )

    print("\nSynthetic KTP generated successfully.")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
