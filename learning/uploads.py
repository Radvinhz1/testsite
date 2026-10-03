import io
import uuid
from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


def upload_path(instance, filename):
    return f'{instance._meta.model_name}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


def validate_text_file(file, limit=1024 * 1024):
    if not file:
        return
    if Path(file.name).suffix.lower() not in {'.py', '.cs', '.txt'} or file.size > limit:
        raise ValidationError('فایل باید py، cs یا txt و حداکثر یک مگابایت باشد.')
    file.seek(0)
    data = file.read(limit + 1)
    file.seek(0)
    try:
        decoded = data.decode('utf-8-sig')
        if '\x00' in decoded or len(data) > limit:
            raise ValueError()
    except (UnicodeDecodeError, ValueError):
        raise ValidationError('فایل باید متن معتبر UTF-8 باشد.')


def validate_pdf(file, limit=5 * 1024 * 1024):
    if not file:
        return
    if Path(file.name).suffix.lower() != '.pdf' or file.size > limit:
        raise ValidationError('فایل PDF با حداکثر حجم پنج مگابایت بارگذاری کنید.')
    try:
        file.seek(0)
        if file.read(5) != b'%PDF-':
            raise ValueError()
        file.seek(0)
        pdf = PdfReader(file)
        if pdf.is_encrypted or not len(pdf.pages):
            raise ValueError()
    except Exception as exc:
        raise ValidationError('فایل PDF معتبر و بدون رمز لازم است.') from exc
    finally:
        file.seek(0)


def validate_material(file):
    if file and Path(file.name).suffix.lower() == '.pdf':
        validate_pdf(file)
    else:
        validate_text_file(file)


def sanitize_avatar(file):
    if file.size > 2 * 1024 * 1024:
        raise ValidationError('حداکثر حجم عکس دو مگابایت است.')
    try:
        file.seek(0)
        with Image.open(file) as original:
            if original.format not in {'JPEG', 'PNG', 'WEBP'} or original.width * original.height > 16000000:
                raise ValueError()
            original.load()
            result = original.convert('RGB')
            result.thumbnail((800, 800))
            output = io.BytesIO()
            result.save(output, format='JPEG', quality=85)
        return ContentFile(output.getvalue(), name='avatar.jpg')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValidationError('عکس معتبر JPEG، PNG یا WebP با ابعاد مناسب انتخاب کنید.') from exc
