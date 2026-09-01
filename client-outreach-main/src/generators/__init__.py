"""Script-generation models and provider abstraction."""

from generators.base import ScriptProvider, ScriptProviderError
from generators.bridge import generate_script_from_candidate
from generators.models import Scene, ScriptSegment, ShortScript
from generators.script_generator import build_provider, generate_script
from generators.strategy_director import StrategyDirector

__all__ = [
    "Scene",
    "ScriptProvider",
    "ScriptProviderError",
    "ScriptSegment",
    "ShortScript",
    "StrategyDirector",
    "build_provider",
    "generate_script",
    "generate_script_from_candidate",
]