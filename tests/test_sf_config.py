"""sf/config.py: profile override wins even when config.json pins a profile."""

from __future__ import annotations

import json

from seohead.sf.config import apply_profile, load_config


def test_load_config_does_not_preexpand_profile(tmp_path):
    p = tmp_path / "config.json"
    with p.open("w", encoding="utf-8") as stream:
        json.dump({"profile": "lite"}, stream)
    cfg = load_config(str(p))
    # profile recorded, but exports NOT yet collapsed to lite (so an override can win)
    assert cfg["profile"] == "lite"
    assert "Sitemaps:Orphan URLs" in cfg["exports"]["tabs"]
    # override to full -> full export set; collapse to lite -> orphan tab gone
    cfg["profile"] = "full"
    assert "Sitemaps:Orphan URLs" in apply_profile(cfg)["exports"]["tabs"]
    cfg["profile"] = "lite"
    assert "Sitemaps:Orphan URLs" not in apply_profile(cfg)["exports"]["tabs"]
