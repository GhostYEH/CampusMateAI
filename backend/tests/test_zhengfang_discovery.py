from pathlib import Path

import pytest

from app.services.edu.adapters.zhengfang_discovery import (
    ScheduleDiscoveryError,
    ZhengfangCapabilityDiscoverer,
)
from app.services.edu.adapters.zhengfang_strategy import (
    school_config_from_dict,
    school_config_to_dict,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "edu" / "zhengfang"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_authenticated_menu_yields_only_exact_origin_personal_schedule_candidate() -> None:
    discoverer = ZhengfangCapabilityDiscoverer("https://jwxt.example.edu.cn")

    candidates = discoverer.menu_candidates(
        _load("menu_schedule.html"),
        page_url="https://jwxt.example.edu.cn/jwglxt/xtgl/index_initMenu.html",
    )

    assert [candidate.entry_path for candidate in candidates] == [
        "/jwglxt/kbcx/xskbcx_cxXsKb.html?gnmkdm=N253508"
    ]
    assert candidates[0].function_id == "N253508"
    assert candidates[0].source == "authenticated_menu"


@pytest.mark.parametrize(
    "unsafe_href",
    [
        "https://evil.example/kbcx/xskbcx.html",
        "//evil.example/kbcx/xskbcx.html",
        "javascript:fetch('/jwglxt/kbcx/xskbcx.html')",
        "http://jwxt.example.edu.cn/jwglxt/kbcx/xskbcx.html",
    ],
)
def test_menu_candidate_rejects_non_exact_https_origin(unsafe_href: str) -> None:
    discoverer = ZhengfangCapabilityDiscoverer("https://jwxt.example.edu.cn")
    html = f'<a href="{unsafe_href}">个人课表</a>'

    assert discoverer.menu_candidates(
        html,
        page_url="https://jwxt.example.edu.cn/jwglxt/xtgl/index.html",
    ) == []


def test_schedule_page_form_declares_executable_protocol_without_guessing() -> None:
    discoverer = ZhengfangCapabilityDiscoverer("https://jwxt.example.edu.cn")
    candidate = discoverer.menu_candidates(
        _load("menu_schedule.html"),
        page_url="https://jwxt.example.edu.cn/jwglxt/xtgl/index_initMenu.html",
    )[0]

    protocol = discoverer.page_protocol(
        _load("schedule_page.html"),
        page_url=f"https://jwxt.example.edu.cn{candidate.entry_path}",
        candidate=candidate,
    )

    assert protocol.entry_path == candidate.entry_path
    assert protocol.data_path == "/jwglxt/kbcx/xskbcx_cxXsKb.html?gnmkdm=N253508"
    assert protocol.method == "POST"
    assert protocol.semester_params == ("xnm", "xqm")
    assert protocol.response_format == "auto"
    assert protocol.source == "live_discovered"
    assert len(protocol.fingerprint) == 64


def test_schedule_page_without_same_origin_form_or_explicit_request_is_rejected() -> None:
    discoverer = ZhengfangCapabilityDiscoverer("https://jwxt.example.edu.cn")
    candidate = discoverer.menu_candidates(
        '<a href="/jwglxt/kbcx/personal.html">个人课表</a>',
        page_url="https://jwxt.example.edu.cn/jwglxt/index.html",
    )[0]

    with pytest.raises(ScheduleDiscoveryError, match="未声明可验证的课表数据请求"):
        discoverer.page_protocol(
            '<main><h1>个人课表</h1><a href="https://evil.example/data">加载</a></main>',
            page_url="https://jwxt.example.edu.cn/jwglxt/kbcx/personal.html",
            candidate=candidate,
        )


def test_school_config_round_trips_only_the_schedule_protocol_descriptor() -> None:
    descriptor = {
        "entry_path": "/jwglxt/kbcx/personal.html?gnmkdm=N253508",
        "data_path": "/jwglxt/kbcx/data.html?gnmkdm=N253508",
        "method": "POST",
        "semester_params": ["xnm", "xqm"],
        "response_format": "auto",
        "source": "live_discovered",
        "fingerprint": "a" * 64,
    }

    school = school_config_from_dict({
        "base_url": "https://jwxt.example.edu.cn",
        "schedule_protocol": descriptor,
    })

    assert school is not None
    assert school.schedule_protocol is not None
    assert school.schedule_protocol.to_dict() == descriptor
    assert school_config_to_dict(school)["schedule_protocol"] == descriptor
