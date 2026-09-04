import re
from .base import Transformation


class IRRestructure(Transformation):
    name = "ir_restructure"
    version = "1.0.0"

    def apply(self, ir: str) -> str:
        lines = ir.split("\n")
        result = []
        counter = 0

        for line in lines:
            modified = line

            rng = self._seeded_random(f"restructure_{counter}")
            counter += 1

            if "declare " in line and "declare" == line.strip().split()[0]:
                if rng % 2 == 0:
                    modified = line.replace(
                        "declare ",
                        "declare dso_local ",
                        1
                    )

            if "store" in line and "i32" in line:
                if rng % 3 == 0:
                    modified = line.strip()
                    if not modified.endswith(", align 4"):
                        modified = modified + ", align 4"

            result.append(modified)

        return "\n".join(result)
