from pathlib import Path


def test_gpu_acceptance_exercises_openace_soulx_adapter_not_upstream_example_only():
    source = Path("scripts/verify_local_gpu.py").read_text(encoding="utf-8")
    assert "SoulXSingerEngine(device=\"cuda\").render_score" in source
    assert "OpenACE local GPU acceptance" in source
    assert '(60, "你")' in source
    assert '(62, "好")' in source
    assert '(60, "歌")' in source
    assert "--target_metadata_path" not in source
    assert '"--control",' not in source
    assert "preprocessing cache integration" in source
    assert "ACEStepEngine(device=\"auto\").vocal_to_bgm" in source
    assert "ace_verify.toml" not in source
    assert '"task_type": "complete"' in source
    assert 'duration=vocal_info.frames / float(vocal_info.samplerate)' in source


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


def test_gpu_acceptance_reports_rendered_vocal_alignment_measurement():
    source = Path("scripts/verify_local_gpu.py").read_text()
    assert "vocal_alignment_measurements(vocal_out, project, track.sorted_notes())" in source
    assert '"alignment": alignment' in source
    assert 'first_voiced_onset_s' in source
    assert 'pitch_transition_s' in source



def test_gpu_acceptance_repaint_range_is_derived_and_outputs_are_nonsilent():
    source = Path("scripts/verify_local_gpu.py").read_text()
    assert "bgm_seconds = bgm_info.frames / float(bgm_info.samplerate)" in source
    assert "start_s=repaint_start" in source
    assert "end_s=repaint_end" in source
    assert "start_s=2.0" not in source
    assert '"peak": round(peak, 6)' in source
    assert "peak < 1e-5" in source
    assert "silent or too short for real GPU acceptance" in source
