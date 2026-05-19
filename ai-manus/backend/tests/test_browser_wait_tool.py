import asyncio

from app.domain.models.tool_result import ToolResult
from app.domain.services.tools.browser import BrowserToolkit


def run(coro):
    return asyncio.run(coro)


class FakeBrowser:
    async def view_page(self) -> ToolResult:
        return ToolResult(success=True)


def test_browser_wait_is_registered_and_invokable():
    toolkit = BrowserToolkit(FakeBrowser())
    tool = toolkit.get_tool("browser_wait")

    assert tool is not None

    result = run(tool.ainvoke({"id": "wait_1", "args": {"seconds": 0}}))

    assert result.name == "browser_wait"
    assert result.artifact.success is True
    assert result.artifact.message == "Waited 0 seconds"
