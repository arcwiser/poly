import subprocess
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional


def analyze_binary(
    executable_path: Path,
    ir_path: Optional[Path] = None,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    metrics["sha256"] = _sha256(executable_path)
    metrics["file_size"] = executable_path.stat().st_size

    sections = _readelf_sections(executable_path)
    metrics["sections"] = sections
    metrics["section_count"] = len(sections)
    metrics["text_size"] = sections.get(".text", {}).get("size", 0)
    metrics["rodata_size"] = sections.get(".rodata", {}).get("size", 0)
    metrics["data_size"] = sections.get(".data", {}).get("size", 0)
    metrics["bss_size"] = sections.get(".bss", {}).get("size", 0)

    metrics["symbol_count"] = _readelf_symbols(executable_path)
    metrics["dynamic_symbols"] = _readelf_dynsyms(executable_path)

    elf_info = _elf_header_info(executable_path)
    metrics["architecture"] = elf_info.get("arch", "unknown")
    metrics["endianness"] = elf_info.get("endian", "unknown")

    if ir_path and ir_path.exists():
        ir = ir_path.read_text(encoding="utf-8")
        metrics["ir_size"] = len(ir.encode())
        metrics["ir_lines"] = len(ir.splitlines())
        metrics["function_count_ir"] = _ir_function_count(ir)
        metrics["basic_block_count_ir"] = _ir_basic_block_count(ir)
        metrics["instruction_count_ir"] = _ir_instruction_count(ir)
        metrics["string_constants"] = _ir_string_constants(ir)

    return metrics


def compare_binaries(
    metrics_a: Dict[str, Any],
    metrics_b: Dict[str, Any],
) -> Dict[str, Any]:
    cmp: Dict[str, Any] = {}
    cmp["identical"] = metrics_a.get("sha256") == metrics_b.get("sha256")

    for key in ("file_size", "text_size", "symbol_count", "rodata_size"):
        a = metrics_a.get(key, 0)
        b = metrics_b.get(key, 0)
        cmp[f"{key}_a"] = a
        cmp[f"{key}_b"] = b
        cmp[f"{key}_diff"] = abs(a - b)

    sz_a = metrics_a.get("file_size", 0)
    sz_b = metrics_b.get("file_size", 0)
    cmp["size_ratio"] = min(sz_a, sz_b) / max(sz_a, sz_b) if max(sz_a, sz_b) > 0 else 1.0

    sect_diff = {}
    all_sects = set(metrics_a.get("sections", {})) | set(metrics_b.get("sections", {}))
    for s in all_sects:
        sa = metrics_a.get("sections", {}).get(s, {}).get("size", 0)
        sb = metrics_b.get("sections", {}).get(s, {}).get("size", 0)
        sect_diff[s] = {"a": sa, "b": sb, "diff": abs(sa - sb), "same": sa == sb}
    cmp["section_differences"] = sect_diff

    for key in ("ir_size", "function_count_ir", "basic_block_count_ir", "instruction_count_ir"):
        a = metrics_a.get(key, 0)
        b = metrics_b.get(key, 0)
        cmp[f"{key}_a"] = a
        cmp[f"{key}_b"] = b
        cmp[f"{key}_diff"] = abs(a - b)

    return cmp


def byte_similarity(path_a: Path, path_b: Path) -> float:
    a, b = path_a.read_bytes(), path_b.read_bytes()
    mlen = min(len(a), len(b))
    maxlen = max(len(a), len(b))
    if maxlen == 0:
        return 1.0
    return sum(1 for i in range(mlen) if a[i] == b[i]) / maxlen


# ── internal helpers ────────────────────────────────────────

def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _readelf_sections(p: Path) -> Dict[str, Any]:
    sections = {}
    try:
        r = subprocess.run(["readelf", "-S", str(p)], capture_output=True, text=True, timeout=10)
        for line in r.stdout.split("\n"):
            m = re.match(r"\s*\[\s*\d+\]\s+(\S+)\s+\S+\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)", line)
            if m:
                sections[m.group(1)] = {"size": int(m.group(3), 16), "offset": int(m.group(2), 16)}
    except Exception:
        pass
    if not sections:
        try:
            r = subprocess.run(["objdump", "-h", str(p)], capture_output=True, text=True, timeout=10)
            for line in r.stdout.split("\n"):
                m = re.match(r"\s*\d+\s+(\S+)\s+[0-9a-fA-F]+\s+[0-9a-fA-F]+\s+([0-9a-fA-F]+)", line)
                if m:
                    sections[m.group(1)] = {"size": int(m.group(2), 16)}
        except Exception:
            pass
    return sections


def _count_elf_syms(p: Path, sym_type: str = ".symtab") -> int:
    try:
        r = subprocess.run(["readelf", "-s", str(p)], capture_output=True, text=True, timeout=10)
        count = 0
        in_section = False
        for line in r.stdout.split("\n"):
            if sym_type in line:
                in_section = True
                continue
            if in_section:
                parts = line.split()
                if len(parts) >= 3 and parts[1].startswith("0"):
                    count += 1
                elif line.strip() == "" or "Node" in line:
                    break
        return count
    except Exception:
        return 0


def _readelf_symbols(p: Path) -> int:
    return _count_elf_syms(p, ".symtab")


def _readelf_dynsyms(p: Path) -> int:
    return _count_elf_syms(p, ".dynsym")


def _elf_header_info(p: Path) -> Dict[str, str]:
    info = {}
    try:
        r = subprocess.run(["readelf", "-h", str(p)], capture_output=True, text=True, timeout=10)
        for line in r.stdout.split("\n"):
            if "Machine:" in line:
                info["arch"] = line.split("Machine:")[1].strip()
            elif "Class:" in line:
                info["class"] = line.split("Class:")[1].strip()
            elif "Data:" in line:
                info["endian"] = line.split("Data:")[1].strip()
    except Exception:
        pass
    return info


def _ir_function_count(ir: str) -> int:
    return len(re.findall(r"define\s+.*@(\w+)\s*\(", ir))


def _ir_basic_block_count(ir: str) -> int:
    count = 0
    for line in ir.split("\n"):
        s = line.strip()
        if s and s.endswith(":") and not s.startswith(";") and not s.startswith("declare") and "(" not in s:
            count += 1
    return max(count, 1)


def _ir_instruction_count(ir: str) -> int:
    count = 0
    in_function = False
    for line in ir.split("\n"):
        s = line.strip()
        if "define " in s and "@" in s:
            in_function = True
            continue
        if in_function:
            if s.startswith("}"):
                in_function = False
                continue
            if s and not s.startswith(";") and not s.endswith(":") and s not in ("", "}"):
                count += 1
    return count


def _ir_string_constants(ir: str) -> int:
    return len(re.findall(r'c"[^"]*"', ir))
