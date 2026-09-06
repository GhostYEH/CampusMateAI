from app.digital_human_static import cache_control_for_asset, resolve_digital_human_assets_dir


def test_resolves_checked_in_unity_webgl_build() -> None:
    assets = resolve_digital_human_assets_dir()

    assert assets.name == "digital-human"
    assert assets.parent.name == "public"
    assert (assets / "index.html").is_file()
    assert (assets / "mobile.html").is_file()


def test_cache_policy_keeps_shell_revalidatable_and_build_cached() -> None:
    assert cache_control_for_asset("mobile.html") == "no-cache"
    assert cache_control_for_asset("index.html") == "no-cache"
    assert cache_control_for_asset("Build/digital-human.wasm") == "public, max-age=86400"
