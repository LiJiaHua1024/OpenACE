from pathlib import Path


def test_gpu_acceptance_exercises_openace_soulx_adapter_not_upstream_example_only():
    source = Path("scripts/verify_local_gpu.py").read_text(encoding="utf-8")
    assert "SoulXSingerEngine(device=\"cuda\").render_score" in source
    assert "OpenACE local GPU acceptance" in source
    assert 'lyric="你"' in source
    assert 'lyric="好"' in source
    assert "--target_metadata_path" not in source
    assert '"--control",' not in source
    assert "preprocessing cache integration" in source
    assert "ACEStepEngine(device=\"auto\").vocal_to_bgm" in source
    assert "ace_verify.toml" not in source
    assert '"task_type": "complete"' in source


def test_gpu_acceptance_prefers_nvml_before_torch_cuda_fallback():
    source = Path("scripts/verify_local_gpu.py").read_text(encoding="utf-8")
    nvml = source.index("query_nvidia_gpu(0)")
    torch_fallback = source.index("import torch")
    assert nvml < torch_fallback
    assert "may create a CUDA" in source
