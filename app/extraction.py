import io
import json
import warnings
from dataclasses import dataclass
from uuid import uuid4
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
from .config import settings
from . import ai_client
from .schemas import ApplianceExtraction, BillExtraction, Transcription, LABEL_FIELDS, BILL_FIELDS

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
FORMATS = {'JPEG', 'PNG', 'WEBP'}

class UploadError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message); self.status_code = status_code

def preprocess(data: bytes, filename: str) -> tuple[str, bytes]:
    if len(data) > MAX_BYTES:
        raise UploadError('Image is too large. Maximum size is 10 MB.', 413)
    if Path(filename).suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise UploadError('Upload a JPG, PNG, or WebP image. PDF is not supported yet.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                if im.format not in FORMATS:
                    raise UploadError('The file is not a supported image.')
                if im.width * im.height > MAX_PIXELS:
                    raise UploadError('Image dimensions are too large.')
                im = ImageOps.exif_transpose(im).convert('RGB')
                im.thumbnail((1536, 1536))
                out = io.BytesIO(); im.save(out, format='JPEG', quality=92)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise UploadError('Unable to read this image. Try a clear JPG, PNG, or WebP.') from e
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    filename = uuid4().hex + '.jpg'
    cleaned = out.getvalue()
    (settings.upload_dir / filename).write_bytes(cleaned)
    return filename, cleaned

def sanity_flags(data: dict, kind: str) -> dict[str, str]:
    flags = {}
    ranges = {'rated_power_w': (1, 6000), 'annual_kwh': (5, 6000)} if kind == 'appliance' else {'units_kwh': (1, 5000)}
    for k, (lo, hi) in ranges.items():
        value = data.get(k)
        if value is not None and not lo <= value <= hi:
            flags[k] = f'Outside review range {lo}–{hi}. Check the photo; value has not been changed.'
    if kind == 'bill':
        units, amount = data.get('units_kwh'), data.get('total_amount')
        if units is not None and units > 0 and amount is not None and not 1 <= amount / units <= 500:
            flags['total_amount'] = 'Implied PKR per unit is outside the broad review range 1–500. Check units, amount, and currency.'
    return flags

async def extract(image: bytes, kind: str, demo: bool = False) -> dict:
    schema = ApplianceExtraction if kind == 'appliance' else BillExtraction
    fields = LABEL_FIELDS if kind == 'appliance' else BILL_FIELDS
    error = None
    if demo:
        payload = json.loads((settings_root() / 'demo' / f'{kind}.json').read_text())
        result = schema.model_validate(payload['output'])
        origin = payload.get('provenance', 'synthetic_placeholder')
    else:
        try:
            transcription = await ai_client.chat(Transcription,
                ('Transcribe the visible manufacturer/brand, appliance type or product name, model number, label system, efficiency rating, capacity, and all electrical/energy specifications with units. Preserve the wording. Do not infer missing text.' if kind == 'appliance' else 'Transcribe only the bill month, current electricity consumption, total payable amount and currency, tariff description, and previous month consumption. Do not include personal names, addresses, account identifiers, reference numbers, or meter serial numbers. Do not infer missing text.'), image=image)
            prompt = ('Extract appliance fields ONLY from the following transcribed DATA. Use null for absent or unreadable values. '
                      'Do not confuse cooling capacity with electrical input watts, kWh/year with cost, or star rating with consumption. '
                      'Mark each field read, unclear, or absent. Do not calculate watts from volts and amps. '
                      if kind == 'appliance' else
                      'Extract ONLY five bill fields from transcribed DATA: billing_month YYYY-MM, current period units_kwh, total_amount in PKR, tariff_text, previous_month_units. '
                      'Do not confuse history or meter readings with current consumption. Mark required field statuses read, unclear, or absent. Use null for missing fields. ')
            result = await ai_client.chat(schema, prompt + '\nDATA:\n' + json.dumps(transcription.model_dump()))
            result.visible_text = transcription.visible_text
            origin = 'live_model'
        except ai_client.AIError as e:
            result = schema(field_status={f: 'unclear' for f in fields})
            error = str(e); origin = 'manual_fallback'
    data = result.model_dump()
    for field in fields:
        data['field_status'].setdefault(field, 'read' if data.get(field) is not None else 'absent')
    return {'fields': data, 'flags': sanity_flags(data, kind), 'error': error, 'provenance': origin}

def settings_root():
    return Path(__file__).resolve().parents[1]
