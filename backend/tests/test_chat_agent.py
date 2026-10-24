import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import chat_agent
from agent.chat_agent import ChatUnavailable, ask


class FakeLLM(GenericFakeChatModel):
    seen: list = []

    def bind_tools(self, tools, **kw):
        return self

    def _generate(self, messages, *a, **kw):
        self.seen.append(list(messages))
        return super()._generate(messages, *a, **kw)


def tool_call(name, args=None, i=0):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": f"c{i}"}])


def fake(*msgs):
    return FakeLLM(messages=iter(msgs), seen=[])


def test_ask_returns_answer_and_tools_used(items):
    llm = fake(tool_call("get_kpis", {"project": "Project A"}), AIMessage(content="1 blocked"))
    r = ask(items, "how many blocked?", [], "Project A", llm=llm)
    assert r == {"answer": "1 blocked", "tools_used": ["get_kpis"]}


def test_ask_raises_when_no_llm(items, monkeypatch):
    monkeypatch.setattr(chat_agent, "_get_llm", lambda: None)
    with pytest.raises(ChatUnavailable):
        ask(items, "hi", [])


def test_history_trimmed_to_last_10(items):
    llm = fake(AIMessage(content="ok"))
    hist = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(30)]
    ask(items, "new", hist, llm=llm)
    msgs = llm.seen[0]
    assert [m.content for m in msgs[1:]] == [f"m{i}" for i in range(20, 30)] + ["new"]


def test_system_prompt_mentions_selected_project(items):
    llm = fake(AIMessage(content="ok"))
    ask(items, "hi", [], "Project B", llm=llm)
    assert "Project B" in llm.seen[0][0].content


def test_tool_call_limit_stops_runaway_loop(items):
    llm = FakeLLM(messages=(tool_call("list_projects", i=i) for i in range(100)), seen=[])
    r = ask(items, "loop", [], llm=llm)
    assert "couldn't finish" in r["answer"] and len(r["tools_used"]) <= 6
