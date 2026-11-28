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


def test_gpu_acceptance_samples_stage_memory_without_parent_cuda():
    source = Path("scripts/verify_local_gpu.py").read_text()
    assert "class NvidiaMemoryTelemetry" in source
    assert "query_nvidia_gpu(self.index)" in source
    assert '"max_used_gb"' in source
    assert '"min_free_gb"' in source
    assert "svs_telemetry.start()" in source
    assert "ace_telemetry.start()" in source
    assert "demucs_telemetry.start()" in source
    assert '"memory": svs_memory' in source
    assert '"memory": ace_memory' in source
    assert '"memory": demucs_memory' in source
    assert "torch.cuda.empty_cache" not in source


def test_gpu_acceptance_exercises_production_svc_adapter():
    source = Path("scripts/verify_local_gpu.py").read_text()
    assert "SoulXSingerEngine(device=\"cuda\").convert_voice" in source
    assert '"soulx_svc_real_render"' in source
    assert '"soulx_svc": svc_out' in source
    assert "svc_telemetry.start()" in source
    assert '"memory": svc_memory' in source


def test_gpu_acceptance_exercises_production_repaint_adapter():
    source = Path("scripts/verify_local_gpu.py").read_text()
    assert "ACEStepEngine(device=\"auto\").repaint" in source
    assert '"acestep_repaint_real_render"' in source
    assert '"task_type": "repaint"' in source
    assert '"acestep_repaint": repaint_out' in source
    assert "repaint_telemetry.start()" in source
    assert '"memory": repaint_memory' in source
