import re
from .base import Transformation


class BasicBlockReorder(Transformation):
    name = "block_reorder"
    version = "1.0.0"

    def apply(self, ir: str) -> str:
        blocks = self._split_blocks(ir)
        if len(blocks) <= 1:
            return ir

        header = blocks[0]
        body_blocks = blocks[1:]

        if not body_blocks:
            return ir

        rng = self._seeded_random("reorder")
        indices = list(range(len(body_blocks)))

        seed_val = rng
        for i in range(len(indices) - 1, 0, -1):
            seed_val = (seed_val * 1103515245 + 12345) & 0x7FFFFFFF
            j = seed_val % (i + 1)
            indices[i], indices[j] = indices[j], indices[i]

        reordered = [body_blocks[i] for i in indices]

        remaining_ir = "\n".join(
            [header] + reordered
        )

        tail_start = ir.find("\n}", ir.find("define"))
        if tail_start != -1:
            tail = ir[tail_start + 1:]
            remaining_ir = remaining_ir.rstrip() + "\n" + tail

        return remaining_ir

    def _split_blocks(self, ir: str) -> list:
        blocks = []
        current = []
        in_function = False

        for line in ir.split("\n"):
            if "define " in line and "@" in line:
                in_function = True

            if in_function and re.match(r"^[a-zA-Z0-9_.]+:", line.strip()):
                if current:
                    blocks.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            blocks.append("\n".join(current))

        return blocks
