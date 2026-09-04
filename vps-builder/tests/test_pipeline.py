import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_toolchain():
    from server.compiler import get_toolchain_info
    print("=== Toolchain ===")
    info = get_toolchain_info()
    print(f"  {info.get('compiler_version', '?')}")
    print(f"  LLVM {info.get('llvm_version', '?')}")
    print(f"  Triple: {info.get('target_triple', '?')}")
    assert "clang" in info.get("compiler_version", "").lower() or info.get("compiler") == "clang"
    print("  PASS\n")


def test_compile():
    from server.compiler import BuildWorkspace, generate_ir, compile_from_ir, test_executable
    from server.cleanup import cleanup_workspace
    print("=== Compilation ===")
    bid = str(uuid.uuid4())
    ws = BuildWorkspace(bid)
    ws.create()
    try:
        ir = generate_ir(ws, "O2")
        print(f"  IR: {ir['ir_size']} bytes")
        ws.transformed_ir_path.write_text(ws.ir_path.read_text(encoding="utf-8"), encoding="utf-8")
        compile_from_ir(ws, "O2")
        r = test_executable(ws)
        print(f"  Test: exit={r['exit_code']}, passed={r['passed']}")
        assert r["passed"], f"Failed: {r}"
        print("  PASS\n")
    finally:
        cleanup_workspace(bid)


def test_transforms():
    from server.compiler import BuildWorkspace, generate_ir
    from server.transformations import TransformationEngine
    from server.cleanup import cleanup_workspace
    print("=== Transformations ===")
    bid = str(uuid.uuid4())
    ws = BuildWorkspace(bid)
    ws.create()
    try:
        generate_ir(ws, "O2")
        ir = ws.ir_path.read_text(encoding="utf-8")
        e1 = TransformationEngine(seed=42)
        t1 = e1.apply(ir)
        e2 = TransformationEngine(seed=42)
        t2 = e2.apply(ir)
        assert t1 == t2, "Not deterministic!"
        print(f"  Determinism: PASS")
        print(f"  Applied: {len(e1.applied)} transforms")
        for t in e1.applied:
            print(f"    {t['name']}: changed={t['changed']}")
        print("  PASS\n")
    finally:
        cleanup_workspace(bid)


def test_full_pipeline():
    from server.build_manager import execute_build
    print("=== Full Pipeline ===")
    r = execute_build(project="hello-world", seed=7, optimization="O2")
    assert r["success"], f"Failed: {r.get('error')}"
    m = r["manifest"]
    print(f"  SHA-256: {m['artifact_sha256'][:32]}...")
    print(f"  Size:    {m['file_size']:,} bytes")
    print(f"  .text:   {m['text_size']:,} bytes")
    print(f"  Time:    {r['elapsed_seconds']:.2f}s")
    print(f"  Test:    {m['test']['passed']}")
    print("  PASS\n")


def test_diversity():
    from server.build_manager import execute_build
    print("=== Diversity ===")
    r1 = execute_build(project="hello-world", seed=1, optimization="O2")
    r2 = execute_build(project="hello-world", seed=2, optimization="O2")
    assert r1["success"] and r2["success"]
    s1 = r1["manifest"]["artifact_sha256"]
    s2 = r2["manifest"]["artifact_sha256"]
    print(f"  Seed 1: {s1[:16]}... ({r1['manifest']['file_size']:,} bytes)")
    print(f"  Seed 2: {s2[:16]}... ({r2['manifest']['file_size']:,} bytes)")
    print(f"  Same:   {s1 == s2}")
    print("  PASS\n")


if __name__ == "__main__":
    test_toolchain()
    test_compile()
    test_transforms()
    test_full_pipeline()
    test_diversity()
    print("All tests passed!")
