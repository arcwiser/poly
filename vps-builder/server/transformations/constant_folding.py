import re
from .base import Transformation


class ConstantExpressionTransform(Transformation):
    name = "constant_expr"
    version = "1.0.0"

    def apply(self, ir: str) -> str:
        lines = ir.split("\n")
        result = []
        counter = 0

        for line in lines:
            modified = line

            if "ret i32 0" in line:
                rng = self._seeded_random(f"ret_{counter}")
                counter += 1
                if rng % 2 == 0:
                    modified = line.replace(
                        "ret i32 0",
                        "ret i32 (i32 0)"
                    )

            if re.search(r"add i32 (\d+), (\d+)", modified):
                m = re.search(r"add i32 (\d+), (\d+)", modified)
                if m:
                    a, b = int(m.group(1)), int(m.group(2))
                    rng = self._seeded_random(f"add_{a}_{b}_{counter}")
                    counter += 1
                    if rng % 3 == 0:
                        modified = modified.replace(
                            m.group(0),
                            f"add i32 ({a} + {b})"
                        )

            result.append(modified)

        return "\n".join(result)
