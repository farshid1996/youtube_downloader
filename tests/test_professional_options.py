from pathlib import Path

import pytest

import engine


def base_settings(tmp_path):
    return {
        "folder": str(tmp_path),
        "mode": "MP4 video",
        "quality": "Best available",
        "bitrate": "192",
    }


def option_value(args, flag):
    return args[args.index(flag) + 1]


def test_professional_options_are_passed_as_individual_arguments(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "DATA", tmp_path)
    settings = base_settings(tmp_path)
    settings.update({
        "network_preference": "IPv4 only",
        "extractor_retries": 7,
        "file_access_retries": 6,
        "socket_timeout": 75,
        "http_chunk_size": "8M",
        "format_selector": "bv*+ba/b",
        "output_template": "%(uploader)s/%(title)s [%(id)s].%(ext)s",
        "date_after": "20250101",
        "date_before": "20261231",
        "match_title": "tutorial|review",
        "min_filesize": "10M",
        "max_filesize": "2G",
        "extractor_args": "youtube:player_client=default",
        "sponsorblock": "Mark all segments",
        "subtitles": True,
        "auto_subs": True,
        "embed_subs": True,
        "thumbnail": True,
        "embed_thumbnail": True,
        "write_description": True,
        "write_info_json": True,
        "write_comments": True,
        "restrict_filenames": True,
        "sleep_interval": 1,
        "max_sleep_interval": 4,
    })
    url = "https://www.youtube.com/watch?v=example"
    args = engine.arguments(url, settings)

    assert args[-2:] == ["--", url]
    assert option_value(args, "--extractor-retries") == "7"
    assert option_value(args, "--file-access-retries") == "6"
    assert option_value(args, "--socket-timeout") == "75"
    assert option_value(args, "--http-chunk-size") == "8M"
    assert option_value(args, "-f") == "bv*+ba/b"
    assert option_value(args, "-o") == settings["output_template"]
    assert option_value(args, "--dateafter") == "20250101"
    assert option_value(args, "--datebefore") == "20261231"
    assert option_value(args, "--match-title") == "tutorial|review"
    assert option_value(args, "--min-filesize") == "10M"
    assert option_value(args, "--max-filesize") == "2G"
    assert option_value(args, "--extractor-args") == "youtube:player_client=default"
    assert option_value(args, "--max-sleep-interval") == "4"
    assert "--force-ipv4" in args
    assert "--embed-subs" in args
    assert "--embed-thumbnail" in args
    assert "--write-description" in args
    assert "--write-info-json" in args
    assert "--write-comments" in args
    assert "--write-auto-subs" in args
    assert "--sponsorblock-mark" in args and option_value(args, "--sponsorblock-mark") == "all"
    assert "--restrict-filenames" in args
    assert "--" in args
    assert not any("shell=True" in str(arg) for arg in args)


@pytest.mark.parametrize("updates", [
    {"output_template": "../outside/%(title)s.%(ext)s"},
    {"date_after": "20250230"},
    {"date_after": "20261231", "date_before": "20250101"},
    {"match_title": "["},
    {"min_filesize": "ten megabytes"},
    {"min_filesize": "2G", "max_filesize": "100M"},
    {"sleep_interval": 0, "max_sleep_interval": 5},
    {"sleep_interval": 8, "max_sleep_interval": 3},
])
def test_professional_options_reject_invalid_input(tmp_path, updates):
    settings = base_settings(tmp_path)
    settings.update(updates)
    with pytest.raises(ValueError):
        engine.arguments("https://www.youtube.com/watch?v=example", settings)


def test_output_template_may_create_subfolders_but_not_escape_destination(tmp_path):
    settings = base_settings(tmp_path)
    settings["output_template"] = "%(uploader)s/%(title)s [%(id)s].%(ext)s"
    args = engine.arguments("https://www.youtube.com/watch?v=example", settings)
    assert option_value(args, "-o") == settings["output_template"]
