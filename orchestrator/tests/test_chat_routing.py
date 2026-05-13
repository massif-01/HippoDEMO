from __future__ import annotations

from pathlib import Path

from orchestrator import main
from orchestrator.adapters.project_cortex import ProjectCortexAgentAdapter
from orchestrator.models import SkillRecord
from orchestrator.store import OrchestratorStore


def test_chat_route_sends_office_execution_to_hippo_agent():
    assert main._chat_route_for_message("帮我预约一个腾讯会议") == "hippo_agent"
    assert main._chat_route_for_message("预约飞书会议，明天下午三点") == "hippo_agent"
    assert main._chat_route_for_message("写一份飞书文档总结刚才会议") == "hippo_agent"
    assert main._chat_route_for_message("给投资人发邮件") == "hippo_agent"
    assert main._chat_route_for_message("@followup 执行这个 SOP") == "hippo_agent"


def test_chat_route_keeps_general_and_cua_work_on_manus():
    assert main._chat_route_for_message("帮我规划一下产品路线") == "manus"
    assert main._chat_route_for_message("让 CUA 操作本机打开浏览器") == "manus"
    assert main._chat_route_for_message("让 CUA 在本机发邮件") == "manus"
    assert main._chat_route_for_message("在 sandbox 里跑一下代码") == "manus"
    assert main._chat_route_for_message("用 browser 查资料") == "manus"


def test_chat_route_does_not_route_passive_meeting_mentions_to_hippo_agent():
    assert main._chat_route_for_message("腾讯会议这个产品怎么样") == "manus"
    assert main._chat_route_for_message("飞书文档和 notion 有什么区别") == "manus"


def test_skill_input_resolves_at_mentioned_skill(tmp_path, monkeypatch):
    markdown = tmp_path / "FollowUpSkill.md"
    markdown.write_text("# FollowUpSkill\n\nSend follow-up notes.", encoding="utf-8")
    store = OrchestratorStore()
    store.state.skills = [
        SkillRecord(
            id="skill_followup",
            name="FollowUpSkill",
            description="Follow up after meetings",
            path=str(markdown),
        )
    ]
    monkeypatch.setattr(main, "store", store)

    payload = main._hippo_agent_skill_input("@FollowUpSkill 执行这个 SOP")

    assert "Selected Hippo Skill: FollowUpSkill" in payload
    assert "Send follow-up notes" in payload


def test_project_cortex_agent_sse_parser_handles_dify_events():
    adapter = ProjectCortexAgentAdapter()

    parsed = adapter._sse_from_buffer(
        {
            "data": '{"event":"agent_thought","id":"thought_1","tool":"mail","observation":"ok"}',
        }
    )

    assert parsed is not None
    assert parsed["event"] == "agent_thought"
    assert parsed["data"]["tool"] == "mail"
