from mddocx import MarkdownWord, PerformanceConfig, RenderConfig

converter = MarkdownWord(RenderConfig(performance=PerformanceConfig(enabled=True, track_memory=True)))
converter.render_file("phase3_demo.md", "phase3_profiled.docx")
print(converter.last_stats.to_json())
