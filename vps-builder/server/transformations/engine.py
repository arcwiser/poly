from typing import List, Dict, Any, Optional
import logging

from .base import Transformation
from .constant_folding import ConstantExpressionTransform
from .block_reorder import BasicBlockReorder
from .arithmetic_restructure import ArithmeticRestructure
from .function_reorder import FunctionReorder
from .ir_restructure import IRRestructure

logger = logging.getLogger(__name__)

AVAILABLE_TRANSFORMATIONS = {
    "constant_expr": ConstantExpressionTransform,
    "block_reorder": BasicBlockReorder,
    "arithmetic_restructure": ArithmeticRestructure,
    "function_reorder": FunctionReorder,
    "ir_restructure": IRRestructure,
}

DEFAULT_TRANSFORMATIONS = [
    "constant_expr",
    "block_reorder",
    "arithmetic_restructure",
]


class TransformationEngine:
    def __init__(
        self,
        seed: int,
        enabled: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.seed = seed
        self.config = config or {}
        self.enabled_names = enabled or DEFAULT_TRANSFORMATIONS
        self.applied: List[Dict[str, Any]] = []
        self._transforms: List[Transformation] = []

        for name in self.enabled_names:
            if name not in AVAILABLE_TRANSFORMATIONS:
                logger.warning(f"Unknown transformation: {name}")
                continue

            cls = AVAILABLE_TRANSFORMATIONS[name]
            transform_config = self.config.get(name, {})
            instance = cls(seed=seed, config=transform_config)
            self._transforms.append(instance)

    def apply(self, ir: str) -> str:
        result = ir
        self.applied = []

        for transform in self._transforms:
            logger.info(
                f"Applying transformation: {transform.name} "
                f"v{transform.version}"
            )
            before = result
            result = transform.apply(result)

            applied_info = transform.describe()
            applied_info["ir_size_before"] = len(before.encode())
            applied_info["ir_size_after"] = len(result.encode())
            applied_info["changed"] = before != result
            self.applied.append(applied_info)

            if before == result:
                logger.info(f"  {transform.name}: no changes")
            else:
                logger.info(f"  {transform.name}: modified IR")

        return result

    def describe_pipeline(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "enabled_transformations": self.enabled_names,
            "applied": self.applied,
            "total_transformations": len(self._transforms),
        }
