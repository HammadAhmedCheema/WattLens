"""Local Ollama client for appliance vision extraction and LLM energy reduction analysis.
Communicates directly with Ollama's HTTP API (no external openai library required).
Includes full DEMO_MODE fallback.
"""
import os
import json
import base64
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

# Configuration via environment variables
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "phi3:latest")
VISION_MODEL = os.environ.get("VISION_MODEL", "llava")
DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() in ("true", "1", "yes")

# Canned data for DEMO_MODE
CANNED_APPLIANCES = [
    {"name": "Air Conditioner (1.5 Ton)", "watts": 1500},
    {"name": "Refrigerator", "watts": 150},
    {"name": "Washing Machine", "watts": 500},
    {"name": "Electric Iron", "watts": 1000},
    {"name": "Ceiling Fan 1", "watts": 75},
    {"name": "Ceiling Fan 2", "watts": 75},
    {"name": "Ceiling Fan 3", "watts": 75},
    {"name": "Ceiling Fan 4", "watts": 75},
]

CANNED_EXPLANATION = (
    "Your baseline energy consumption is significant, mainly driven by your Air Conditioner (1500W) "
    "and Electric Iron (1000W). By strategically reducing non-essential cooling hours during peak midday "
    "and scheduling laundry during off-peak windows, your home comfortably achieves the targeted reduction. "
    "Critical loads such as your refrigerator and baseline ventilation remain uninterrupted. "
    "This balanced plan keeps your living spaces comfortable while substantially lowering your monthly utility expenses."
)

CANNED_TIPS = [
    "Pre-cool your living space with the AC before peak tariff hours, then switch to ceiling fans to maintain air circulation.",
    "Iron clothes in batches rather than heating up the 1000W iron daily for single garments.",
    "Ensure your refrigerator coils are dust-free and seals are tight to maintain peak efficiency."
]


def _call_ollama_generate(model: str, prompt: str, images: Optional[List[str]] = None, timeout: int = 30) -> Optional[str]:
    """Calls Ollama /api/generate endpoint using urllib (zero external dependencies)."""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }
    if images:
        payload["images"] = images

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "")
    except Exception as e:
        print(f"[Ollama Error] Failed calling {url} with model {model}: {e}")
        return None


def extract_appliances(image_bytes_list: List[bytes]) -> Dict[str, Any]:
    """Extracts appliance name and wattage from image labels using Ollama vision model,
    or returns canned data in DEMO_MODE.
    """
    if DEMO_MODE:
        return {
            "appliances": CANNED_APPLIANCES,
            "source": "demo_mode",
            "message": "Loaded 5 appliance types from demo dataset."
        }

    if not image_bytes_list:
        return {
            "appliances": [],
            "source": "error",
            "message": "No images provided for extraction."
        }

    # Encode images to base64 for Ollama
    base64_images = [base64.b64encode(img).decode("utf-8") for img in image_bytes_list]

    system_prompt = (
        "Read appliance datasheets/labels. Return ONLY valid JSON: "
        '{"appliances":[{"name":str,"watts":number}]}. '
        "If watts is missing but volts and amps are shown, use volts*amps. "
        "Omit unreadable items. No prose."
    )

    raw_response = _call_ollama_generate(
        model=VISION_MODEL,
        prompt=system_prompt,
        images=base64_images,
        timeout=30
    )

    if not raw_response:
        # Fallback gracefully to manual entry message
        return {
            "appliances": [],
            "source": "fallback",
            "message": "Vision model did not return data or timed out. Please enter appliance details manually below."
        }

    # Parse JSON, stripping markdown code fences
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
        appliances = parsed.get("appliances", [])
        valid_appliances = []
        for a in appliances:
            if isinstance(a, dict) and "name" in a and "watts" in a:
                try:
                    valid_appliances.append({
                        "name": str(a["name"]).strip(),
                        "watts": float(a["watts"])
                    })
                except (ValueError, TypeError):
                    continue
        return {
            "appliances": valid_appliances if valid_appliances else [],
            "source": "ollama_vision",
            "message": f"Successfully extracted {len(valid_appliances)} appliance(s)."
        }
    except Exception as e:
        print(f"[Ollama JSON Parse Error] {e} on text:\n{cleaned}")
        return {
            "appliances": [],
            "source": "fallback",
            "message": "Could not parse JSON from vision model. You can easily add appliance rows manually below."
        }


def analyze_and_plan(appliances: List[Dict[str, Any]], target_units: float, baseline_units: float, need: float, calc_plan_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Uses Ollama text model to analyze consumption habits, reduction feasibility,
    and generate custom insights & tips.
    Falls back safely if model call times out or DEMO_MODE is active.
    """
    if DEMO_MODE:
        return {
            "explanation": CANNED_EXPLANATION,
            "tips": CANNED_TIPS
        }

    # Construct prompt for the LLM energy advisor
    summary_lines = []
    for item in calc_plan_items:
        old_h = item.get("old_hours", 0)
        new_h = item.get("new_hours", 0)
        saved = item.get("units_saved", 0)
        summary_lines.append(
            f"- {item['name']}: {item['watts']}W, usage reduced from {old_h}h/day to {new_h}h/day, saving {saved} units/month"
        )
    items_text = "\n".join(summary_lines)

    prompt = (
        f"You are an expert electricity consultant for WattWise. Analyze the following electricity reduction plan:\n"
        f"Baseline monthly units: {baseline_units} kWh\n"
        f"Target monthly units: {target_units} kWh\n"
        f"Reduction needed: {need} kWh\n"
        f"Proposed appliance adjustments:\n{items_text}\n\n"
        f"Requirements:\n"
        f"1. Return 4 to 6 friendly, realistic sentences analyzing the reduction strategy and impact. Use ONLY the figures provided.\n"
        f"2. Provide exactly 3 actionable, impactful tips to help the household maintain this target.\n"
        f"3. Return ONLY valid JSON in this exact structure with no surrounding markdown or text:\n"
        f'{{"explanation": "4-6 sentences here", "tips": ["Tip 1", "Tip 2", "Tip 3"]}}'
    )

    raw_response = _call_ollama_generate(
        model=TEXT_MODEL,
        prompt=prompt,
        timeout=30
    )

    if not raw_response:
        return {
            "explanation": (
                f"Your baseline consumption is {baseline_units} kWh/month, and your goal is {target_units} kWh/month. "
                f"The plan targets a total reduction of {need} kWh by adjusting high-draw non-essential appliances. "
                f"Essential equipment remains untouched to preserve comfort and necessity. "
                f"Following these revised hours will bring your billing reliably into target range."
            ),
            "tips": [
                "Shift high-wattage appliance usage away from peak tariff hours.",
                "Utilize natural ventilation and ceiling fans to ease AC load.",
                "Ensure seals on cooling appliances are airtight to minimize phantom load."
            ]
        }

    # Clean markdown if present
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
        explanation = parsed.get("explanation", CANNED_EXPLANATION)
        tips = parsed.get("tips", CANNED_TIPS)
        if not isinstance(tips, list):
            tips = CANNED_TIPS
        return {
            "explanation": explanation,
            "tips": tips
        }
    except Exception as e:
        print(f"[Ollama Explanation Parse Error]: {e}")
        return {
            "explanation": (
                f"Your baseline consumption is {baseline_units} kWh/month. To meet your target of {target_units} kWh/month, "
                f"the plan reduces daily runtime on high-wattage devices while leaving essential appliances unchanged. "
                f"This optimizes your power usage efficiently and saves approximately {round(baseline_units - target_units, 2)} units."
            ),
            "tips": CANNED_TIPS
        }
