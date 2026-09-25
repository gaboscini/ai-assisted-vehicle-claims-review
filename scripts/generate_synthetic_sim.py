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
OUTPUT_PATH = CLAIM_FOLDER / "documents" / "sim.png"


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
    line_end_x: int,
    label_font,
    value_font,
) -> None:
    draw.text(
        (x, y),
        label,
        font=label_font,
        fill="#52705d",
    )

    draw.text(
        (x, y + 42),
        value,
        font=value_font,
        fill="#102a43",
    )

    draw.line(
        (
            x,
            y + 100,
            line_end_x,
            y + 100,
        ),
        fill="#d4e2d8",
        width=2,
    )


def generate_sim(
    claim_record: dict,
    output_path: Path = OUTPUT_PATH,
) -> None:
    width = 1600
    height = 1000

    image = Image.new(
        mode="RGB",
        size=(width, height),
        color="#f4f8f5",
    )

    draw = ImageDraw.Draw(image)

    title_font = load_font(48, bold=True)
    subtitle_font = load_font(27)
    notice_font = load_font(26, bold=True)
    label_font = load_font(23, bold=True)
    value_font = load_font(31)
    footer_font = load_font(20)

    # Main document
    draw.rounded_rectangle(
        (40, 40, width - 40, height - 40),
        radius=28,
        fill="#ffffff",
        outline="#adc4b4",
        width=3,
    )

    # Green header
    draw.rounded_rectangle(
        (40, 40, width - 40, 170),
        radius=28,
        fill="#356c4b",
    )

    draw.rectangle(
        (40, 130, width - 40, 170),
        fill="#356c4b",
    )

    draw.text(
        (85, 75),
        "MOCK SIM DRIVER LICENCE RECORD",
        font=title_font,
        fill="#ffffff",
    )

    draw.text(
        (85, 195),
        (
            "Synthetic driver licence document "
            "for local demonstration testing"
        ),
        font=subtitle_font,
        fill="#52667a",
    )

    # Synthetic-document warning
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

    # Test photo placeholder
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
        fill="#e8f0ea",
        outline="#98b6a1",
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

    photo_text_width = (
        photo_box[2] - photo_box[0]
    )

    photo_text_height = (
        photo_box[3] - photo_box[1]
    )

    draw.multiline_text(
        (
            photo_left
            + (
                (photo_right - photo_left)
                - photo_text_width
            )
            / 2,
            photo_top
            + (
                (photo_bottom - photo_top)
                - photo_text_height
            )
            / 2,
        ),
        photo_text,
        font=label_font,
        fill="#52705d",
        spacing=12,
        align="center",
    )

    # SIM fields
    field_x = 440
    line_end_x = width - 110
    field_start_y = 395
    row_height = 135

    fields = [
        (
            "SIM NUMBER",
            claim_record["sim_number"],
        ),
        (
            "DRIVER NAME",
            claim_record["customer_name"],
        ),
        (
            "LICENCE CLASS",
            claim_record["sim_class"],
        ),
        (
            "EXPIRATION DATE",
            claim_record["sim_expiration_date"],
        ),
    ]

    for index, (label, value) in enumerate(fields):
        draw_field(
            draw,
            label=label,
            value=str(value),
            x=field_x,
            y=field_start_y
            + (index * row_height),
            line_end_x=line_end_x,
            label_font=label_font,
            value_font=value_font,
        )

    # Footer
    footer_text = (
        "Fictional values. This document is not "
        "valid as a driver licence or for any "
        "official transaction."
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

    generate_sim(
        claim_record=claim_record,
    )

    print(
        "\nSynthetic SIM generated successfully."
    )
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
