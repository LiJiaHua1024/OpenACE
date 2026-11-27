# Truthful render progress QA

Visible Chrome 1272×837, fixture backend restarted with 8s delay; repo unchanged.

Passed: two vocal jobs showed FIFO running+queued. Running job immediately moved beyond initial 5% to truthful coarse `fixture vocal synthesis stage` at 12%, remained coarse rather than fake-smooth, then reported `applying expression and breath post-processing` 84%, `writing acoustic diagnostic` 92%, and completed 100%. Percent text appeared (`running · 12/84/92%`, `completed · 100%`). Live elapsed increased visibly 0→9s; queued card showed increasing queued time and `FIFO #1`. After first completion, queued job advanced to running 12%. Cancel running still worked, status canceled/progress preserved 12%, output null. Reload retained completed/canceled states. Jobs panel contained within right sidebar; console/network clean.

Evidence: `render_progress_results.json`, screenshots 01–04.
