"""
Test the agent with a text chat in the terminal (no voice/UI).
The Sales MCP server must be running (see mcp-server/) and MCP_SERVER_URL / MCP_AUTH_TOKEN set in backend/.env.

    python -m app.cli
"""
import asyncio
import json

from .agent import SalesAgent


async def main() -> None:
    agent = SalesAgent()
    history: list[dict] = []
    print("POS Sales Agent (text test). Type 'exit' to quit.\n")
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            break
        history.append({"role": "user", "content": q})
        res = await agent.run(history)
        history.append({"role": "assistant", "content": res["answer"]})
        print(f"\nAgent: {res['answer']}")
        for c in res["tool_calls"]:
            print(f"   [tool] {c['tool']} {json.dumps(c['args'], ensure_ascii=False)} {'ok' if c['ok'] else 'ERROR'} {c['ms']}ms")
        for v in res["visuals"]:
            print(f"   [card] {v.get('title')} - {len(v.get('rows', []))} rows")
        print(f"   ({res['elapsed_ms']} ms)\n")


if __name__ == "__main__":
    asyncio.run(main())
