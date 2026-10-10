import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
# Local secrets are ignored by Git; environment variables take precedence.
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
ALLOWED_MODELS = {'qwen/qwen3-vl-8b-instruct'}

@dataclass(frozen=True)
class Settings:
    model_name: str = os.getenv('MODEL_NAME', 'qwen/qwen3-vl-8b-instruct')
    api_key: str = __import__('dataclasses').field(default_factory=lambda: os.getenv('OPENROUTER_API_KEY', ''), repr=False)
    api_url: str = 'https://openrouter.ai/api/v1/chat/completions'
    timeout: float = float(os.getenv('AI_TIMEOUT', '90'))
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///wattlens.db')
    upload_dir: Path = Path(os.getenv('UPLOAD_DIR', 'uploads'))
    demo_mode: bool = os.getenv('DEMO_MODE', '0') == '1'

    def __post_init__(self):
        if self.model_name not in ALLOWED_MODELS:
            raise ValueError('MODEL_NAME must be qwen/qwen3-vl-8b-instruct.')
        if self.timeout <= 0:
            raise ValueError('OLLAMA_TIMEOUT must be positive.')

settings = Settings()
