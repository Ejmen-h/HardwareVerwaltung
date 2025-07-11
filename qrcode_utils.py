import os
import qrcode
from database import get_db_path

def generate_qr(data: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    qr_dir = os.path.join(os.path.dirname(get_db_path()), "qrcodes")
    os.makedirs(qr_dir, exist_ok=True)

    qr_path = os.path.join(qr_dir, f"{data}.png")
    img.save(qr_path)
