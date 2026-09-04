import re
from .base import Transformation


class ArithmeticRestructure(Transformation):
    name = "arithmetic_restructure"
    version = "1.0.0"

    def apply(self, ir: str) -> str:
        lines = ir.split("\n")
        result = []
        counter = 0

        for line in lines:
            modified = line

            mul_pattern = r"mul i32 (\w+), (\d+)"
            m = re.search(mul_pattern, modified)
            if m:
                val, factor = m.group(1), int(m.group(2))
                rng = self._seeded_random(f"mul_{val}_{factor}_{counter}")
                counter += 1

                if rng % 2 == 0 and factor > 1:
                    bits = factor.bit_length()
                    modified = modified.replace(
                        m.group(0),
                        f"shl i32 {val}, {bits}"
                    )

            add_pattern = r"add i32 (\w+), (\d+)"
            m = re.search(add_pattern, modified)
            if m:
                val, imm = m.group(1), int(m.group(2))
                rng = self._seeded_random(
                    f"add_imm_{val}_{imm}_{counter}"
                )
                counter += 1

                if rng % 2 == 0 and imm > 0:
                    modified = modified.replace(
                        m.group(0),
                        f"add i32 {val}, {imm}"
                    )

            result.append(modified)

        return "\n".join(result)
