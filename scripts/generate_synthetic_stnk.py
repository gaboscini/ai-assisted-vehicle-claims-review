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
OUTPUT_PATH = CLAIM_FOLDER / "documents" / "stnk.png"


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
    fallback_path = (
        Path("C:/Windows/Fonts")
        / fallback_name
    )

    if fallback_path.exists():
        return ImageFont.truetype(
            str(fallback_path),
            size=size,
        )

    return ImageFont.load_default()


def load_claim_record() -> dict:
    if not CLAIM_RECORD_PATH.exists():
        raise FileNotFoundError(
            f"Claim record was not found: "
            f"{CLAIM_RECORD_PATH}"
        )

    with CLAIM_RECORD_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def draw_field(
    draw: ImageDraw.ImageDraw,
    *,
    label: str,
    value: str,
    x: int,
    y: int,
    field_width: int,
    label_font,
    value_font,
) -> None:
    draw.text(
        (x, y),
        label,
        font=label_font,
        fill="#66547a",
    )

    draw.text(
        (x, y + 40),
        value,
        font=value_font,
        fill="#102a43",
    )

    draw.line(
        (
            x,
            y + 96,
            x + field_width,
            y + 96,
        ),
        fill="#dfd6e8",
        width=2,
    )


def generate_stnk(
    claim_record: dict,
    output_path: Path = OUTPUT_PATH,
) -> None:
    vehicle = claim_record["vehicle"]

    width = 1700
    height = 1120

    image = Image.new(
        mode="RGB",
        size=(width, height),
        color="#f8f5fa",
    )

    draw = ImageDraw.Draw(image)

    title_font = load_font(48, bold=True)
    subtitle_font = load_font(27)
    notice_font = load_font(26, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(29)
    footer_font = load_font(20)

    # Main document
    draw.rounded_rectangle(
        (40, 40, width - 40, height - 40),
        radius=28,
        fill="#ffffff",
        outline="#c8bad2",
        width=3,
    )

    # Header
    draw.rounded_rectangle(
        (40, 40, width - 40, 170),
        radius=28,
        fill="#67477d",
    )

    draw.rectangle(
        (40, 130, width - 40, 170),
        fill="#67477d",
    )

    draw.text(
        (85, 75),
        "MOCK STNK VEHICLE REGISTRATION RECORD",
        font=title_font,
        fill="#ffffff",
    )

    draw.text(
        (85, 195),
        (
            "Synthetic vehicle registration document "
            "for local demonstration testing"
        ),
        font=subtitle_font,
        fill="#52667a",
    )

    # Synthetic warning
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

    notice_width = (
        notice_box[2] - notice_box[0]
    )

    draw.text(
        (
            (width - notice_width) / 2,
            278,
        ),
        notice_text,
        font=notice_font,
        fill="#a52424",
    )

    # Two-column field layout
    left_x = 100
    right_x = 900
    field_width = 700
    start_y = 390
    row_height = 145

    left_fields = [
        (
            "REGISTERED OWNER",
            claim_record["customer_name"],
        ),
        (
            "PLATE NUMBER",
            vehicle["plate_number"],
        ),
        (
            "VEHICLE MAKE",
            vehicle["make"],
        ),
        (
            "VEHICLE MODEL",
            vehicle["model"],
        ),
    ]

    right_fields = [
        (
            "VEHICLE YEAR",
            str(vehicle["year"]),
        ),
        (
            "CHASSIS NUMBER",
            vehicle["chassis_number"],
        ),
        (
            "ENGINE NUMBER",
            vehicle["engine_number"],
        ),
        (
            "REGISTRATION EXPIRATION DATE",
            vehicle[
                "registration_expiration_date"
            ],
        ),
    ]

    for index, (label, value) in enumerate(
        left_fields
    ):
        draw_field(
            draw,
            label=label,
            value=str(value),
            x=left_x,
            y=start_y + (index * row_height),
            field_width=field_width,
            label_font=label_font,
            value_font=value_font,
        )

    for index, (label, value) in enumerate(
        right_fields
    ):
        draw_field(
            draw,
            label=label,
            value=str(value),
            x=right_x,
            y=start_y + (index * row_height),
            field_width=field_width,
            label_font=label_font,
            value_font=value_font,
        )

    footer_text = (
        "Fictional values. This document is not "
        "valid as a vehicle registration record "
        "or for any official transaction."
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

    generate_stnk(
        claim_record=claim_record,
    )

    print(
        "\nSynthetic STNK generated successfully."
    )
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
