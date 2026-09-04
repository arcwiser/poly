import re
from .base import Transformation


class FunctionReorder(Transformation):
    name = "function_reorder"
    version = "1.0.0"

    def apply(self, ir: str) -> str:
        functions = self._extract_functions(ir)
        if len(functions) <= 1:
            return ir

        preamble = ir[:ir.find("define ")] if "define " in ir else ""
        rng = self._seeded_random("func_reorder")

        indices = list(range(len(functions)))
        seed_val = rng
        for i in range(len(indices) - 1, 0, -1):
            seed_val = (seed_val * 1103515245 + 12345) & 0x7FFFFFFF
            j = seed_val % (i + 1)
            indices[i], indices[j] = indices[j], indices[i]

        reordered = [functions[i] for i in indices]

        return preamble + "\n\n".join(reordered)

    def _extract_functions(self, ir: str) -> list:
        functions = []
        current_func = []
        brace_depth = 0
        in_function = False

        for line in ir.split("\n"):
            if "define " in line and "@" in line:
                in_function = True
                current_func = [line]
                brace_depth = line.count("{") - line.count("}")
                continue

            if in_function:
                current_func.append(line)
                brace_depth += line.count("{") - line.count("}")

                if brace_depth <= 0:
                    functions.append("\n".join(current_func))
                    current_func = []
                    in_function = False

        return functions
