"""MediaGenerator 单元测试。"""

from src.media_gen import MediaGenerator


def test_strip_emoji():
    mg = MediaGenerator()
    result = mg._strip_emoji("🏦 Financial Report")
    assert "Financial Report" in result
    assert mg._strip_emoji("Normal text") == "Normal text"
    result2 = mg._strip_emoji("📊 Charts 📈")
    assert "Charts" in result2


def test_strip_md():
    mg = MediaGenerator()
    assert mg._strip_md("**bold**") == "bold"
    assert mg._strip_md("*italic*") == "italic"
    assert mg._strip_md("`code`") == "code"
    assert mg._strip_md("[link](https://example.com)") == "link"
    assert mg._strip_md("__underline__") == "underline"


def test_clean_for_tts():
    mg = MediaGenerator()
    text = "## Heading\n**bold** and *italic* with [link](url)"
    result = mg._clean_for_tts(text)
    assert "##" not in result
    assert "**" not in result
    assert "[link]" not in result


def test_split_text_for_tts():
    mg = MediaGenerator()
    # Short text should return single chunk
    short = "Hello world."
    chunks = mg._split_text_for_tts(short, max_chars=100)
    assert len(chunks) == 1
    assert chunks[0] == short

    # Text exceeding max_chars should be split
    long_text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = mg._split_text_for_tts(long_text, max_chars=30)
    assert len(chunks) > 1
    # All content should be preserved
    combined = "".join(chunks)
    assert "First" in combined
    assert "Third" in combined


def test_generate_audio_falls_back_to_edge_when_elevenlabs_key_missing(monkeypatch, tmp_path):
    import src.media_gen as media_gen_module

    mg = MediaGenerator()
    output_file = tmp_path / "briefing.mp3"
    monkeypatch.setattr(media_gen_module, "ELEVENLABS_API_KEY", "")

    def fake_edge(text, output_file_arg, language, voice_name):
        assert text == "hello"
        assert output_file_arg == str(output_file)
        assert language == "en"
        assert voice_name is None
        return str(output_file)

    monkeypatch.setattr(mg, "generate_audio_edge", fake_edge)

    assert mg.generate_audio("hello", output_file=str(output_file), language="en", tts_engine="elevenlabs") == str(
        output_file
    )


def test_merge_binary_files_removes_parts(tmp_path):
    part1 = tmp_path / "part1.mp3"
    part2 = tmp_path / "part2.mp3"
    output = tmp_path / "merged.mp3"
    part1.write_bytes(b"abc")
    part2.write_bytes(b"def")

    MediaGenerator._merge_binary_files([str(part1), str(part2)], str(output))

    assert output.read_bytes() == b"abcdef"
    assert not part1.exists()
    assert not part2.exists()
