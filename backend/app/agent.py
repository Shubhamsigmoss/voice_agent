"""
Sales Agent
===========
User question -> LLM (Groq gpt-oss-120b) -> MCP tools -> MSSQL -> short answer.

This is the "local orchestration" pattern: we fetch the tool list from the
MCP server, pass it to the LLM as function schemas, and when the LLM asks
for a tool we call the MCP server and send the result back. Sales data
stays under our control.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from openai import APIError, AsyncOpenAI

from mcp import Client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from .config import settings
from .dates import date_reference, now_local

log = logging.getLogger("agent")

HIDDEN_VISUAL_TOOLS = {"list_outlets", "get_data_availability", "search_help", "list_help_topics"}   # results of these tools are not shown as cards in the UI


def build_system_prompt(selected_outlet: dict | None) -> str:
    ref = "\n".join(f"- {k}: {v}" for k, v in date_reference().items())
    now = now_local()
    outlet_line = (
        f"The user has selected outlet '{selected_outlet['name']}' (outlet_id={selected_outlet['id']}). "
        "Use this outlet_id unless the user clearly asks about another outlet or all outlets."
        if selected_outlet
        else "No outlet selected: use outlet_id=0 (all outlets) unless the user names an outlet; "
        "then call list_outlets to find its id."
    )
    if settings.as_of_date:
        time_line = (
            f"Real current date and time: {now:%A, %d %B %Y, %H:%M} ({settings.timezone}).\n"
            f"TEST MODE: the sales database only has data up to {settings.as_of_date}, so for SALES questions "
            f"'today' means {settings.as_of_date} and all relative dates below are based on it. "
            "If the user asks for the actual date or time, give the REAL current date and mention that "
            f"reports are running in test mode with {settings.as_of_date} as today."
        )
    else:
        time_line = f"Current local date and time: {now:%A, %d %B %Y, %H:%M} ({settings.timezone})."
    support = (f"For anything the help library does not cover, tell the user to contact support: {settings.support_contact}."
               if settings.support_contact else
               "For anything the help library does not cover, tell the user to contact their POS support team.")
    return f"""You are the AI assistant inside the POS software used by {settings.restaurant_name}, a restaurant.
You help staff and owners with two things, using ONLY the tools provided:
  A. SALES DATA: sales, items, orders, bills, payments, taxes, reports (tools that read the POS database).
  B. USING THE POS APP: how to do something in the software, and problems or errors in it (search_help).

{time_line}
Business day starts at {settings.business_day_start_hour:02d}:00 - bills before that belong to the previous business day.
Use these precomputed business dates (YYYY-MM-DD) when the user says relative dates:
{ref}
In a sales context the Hindi word "kal" means yesterday. If a month is named without a year, use the most recent such month that is not in the future.

{outlet_line}

General rules:
1. Reply in the SAME language as the user's latest message. English question -> English. Hindi in Devanagari -> Hindi.
   Hinglish in Roman script -> Hinglish in Roman script. Never switch to Hindi for an English question.
2. Your reply is READ ALOUD. No markdown symbols (no **, #, tables, bullet characters), no emojis.
3. Short follow-ups ("and for HSR?", "same for last week", "it's a product sale report", "still not working")
   refer to the previous messages: combine them with the conversation and answer.
4. Only decline topics that are clearly unrelated to the restaurant, its sales or the POS software.
5. If something is ambiguous (e.g. which outlet), make a sensible assumption and mention it briefly.

A. Sales data rules:
6. Never guess or invent numbers. Always call a tool. If a report returns no sales, call get_data_availability and tell
   the user no sales were found for that period and up to which date data is available.
   If a tool result starts with ERROR, the data could NOT be read: do not say there were no sales. Say the report could
   not be loaded because of a system/database error, and do not retry the same call more than once.
7. Pick the most specific tool: date-wise/trend -> get_daily_sales; "how much" -> get_sales_summary; comparisons ->
   compare_sales; day-by-day item/product sales -> get_item_sales_by_date. For a report the user names (product/item
   sale report, GST/tax report, billing, settlement, settlement variance, cash declaration, discarded bills/orders/items,
   KOT cancel, hourly orders) use run_pos_report so numbers match the POS software. "Product" means a menu item.
8. A table/chart is shown on screen separately, so answer in 1-3 short sentences with the key numbers only.
   Write money like "Rs 1,25,430" (Indian grouping, no paise).

B. POS app help rules:
9. For "how do I...", "where is...", "what does this error mean", "X is not working" questions, call search_help with a
   short ENGLISH query describing the task or problem (translate Hindi/Hinglish first), e.g. "add new menu item".
10. Answer ONLY from the returned help text. Never invent menu names, button names, settings or steps, and never use
   general knowledge about other POS software. Use the exact names from the help text.
11. Give the steps as numbered lines, one step per line ("1. Open ...", "2. Click ..."), at most 8 steps, and end with
   the name of the help article you used, e.g. "(From: Items and menu)".
12. If search_help finds nothing relevant, say plainly that there is no guide for this yet. You may call list_help_topics
   to suggest related topics. {support}
13. For a problem that is unclear, ask ONE short question first (the exact error message, or which screen it happens on),
   unless the help text already covers it. If the user says the steps did not help, suggest the next step in the help
   text or the support contact."""


def _tool_text(result) -> str:
    return "".join(getattr(c, "text", "") for c in (result.content or []))


def _parse_report(result) -> dict | None:
    data = result.structured_content
    if not data:
        try:
            data = json.loads(_tool_text(result))
        except (ValueError, TypeError):
            return None
    if isinstance(data, dict) and set(data.keys()) == {"result"}:   # SDK wrapper
        data = data["result"]
    return data if isinstance(data, dict) else None


_http_client = None  # one shared HTTP connection pool to the MCP server (the SDK does not close a client we pass in)
_http_loop = None     # the event loop that pool belongs to (a pool must not be reused from another loop)


def mcp_client(target: Any) -> Client:
    """MCP client for the Sales MCP server. A URL gets the bearer token; an in-process server (tests) is used directly."""
    global _http_client, _http_loop
    if isinstance(target, str):
        loop = asyncio.get_running_loop()
        if _http_client is None or _http_loop is not loop or _http_client.is_closed:
            _http_loop = loop
            headers = {"Authorization": f"Bearer {settings.mcp_auth_token}"} if settings.mcp_auth_token else None
            _http_client = create_mcp_http_client(headers=headers)
        return Client(streamable_http_client(target, http_client=_http_client), read_timeout_seconds=settings.mcp_timeout_seconds)
    return Client(target)


class SalesAgent:
    def __init__(self, mcp_target: Any | None = None, llm: AsyncOpenAI | None = None):
        # mcp_target: MCP server URL (default) or an MCPServer object for tests
        self.mcp_target = mcp_target or settings.mcp_server_url
        self.llm = llm or AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key or "missing-key")

    async def _complete(self, messages: list[dict], tools: list[dict], allow_tools: bool = True):
        extra: dict[str, Any] = {}
        if settings.llm_reasoning_effort and "gpt-oss" in settings.llm_model:
            extra["reasoning_effort"] = settings.llm_reasoning_effort
        kwargs: dict[str, Any] = dict(
            model=settings.llm_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=1024,
            extra_body=extra or None,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto" if allow_tools else "none"
        last_exc: Exception | None = None
        for _attempt in range(2):   # gpt-oss occasionally produces an invalid tool call -> retry once
            try:
                return await self.llm.chat.completions.create(**kwargs)
            except APIError as exc:
                last_exc = exc
                log.warning("LLM error (retrying once): %s", exc)
        raise last_exc  # type: ignore[misc]

    async def list_outlets(self) -> list[dict]:
        async with mcp_client(self.mcp_target) as client:
            res = await client.call_tool("list_outlets", {})
            report = _parse_report(res) or {}
            return report.get("rows", [])

    async def run(
        self,
        history: list[dict],
        selected_outlet: dict | None = None,
        forced_outlet_id: int | None = None,
    ) -> dict[str, Any]:
        """
        history: [{"role": "user"|"assistant", "content": "..."}], last item = new question
        selected_outlet: {"id": 2, "name": "Koramangala"} from the UI dropdown
        forced_outlet_id: outlet from the user's login/role (user cannot see other outlets)
        """
        started = time.perf_counter()
        visuals: list[dict] = []
        calls: list[dict] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        rounds = 0

        async with mcp_client(self.mcp_target) as client:
            tool_list = (await client.list_tools()).tools
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": (t.description or "")[:1000],
                        "parameters": t.input_schema,
                    },
                }
                for t in tool_list
            ]
            outlet_tools = {t.name for t in tool_list if "outlet_id" in (t.input_schema or {}).get("properties", {})}

            messages: list[dict] = [{"role": "system", "content": build_system_prompt(selected_outlet)}]
            messages += [{"role": m["role"], "content": m["content"]} for m in history[-10:]]

            answer = ""
            for round_no in range(settings.max_tool_rounds + 1):
                allow_tools = round_no < settings.max_tool_rounds
                resp = await self._complete(messages, tools, allow_tools=allow_tools)
                rounds += 1
                u = getattr(resp, "usage", None)
                if u is not None:
                    usage["prompt_tokens"] += int(getattr(u, "prompt_tokens", 0) or 0)
                    usage["completion_tokens"] += int(getattr(u, "completion_tokens", 0) or 0)
                msg = resp.choices[0].message

                if not msg.tool_calls:
                    answer = (msg.content or "").strip()
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
                            for tc in msg.tool_calls
                        ],
                    }
                )

                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}") or {}
                    except json.JSONDecodeError:
                        args = {}
                    if forced_outlet_id is not None and name in outlet_tools:
                        args["outlet_id"] = forced_outlet_id

                    t0 = time.perf_counter()
                    try:
                        res = await client.call_tool(name, args)
                        is_error = bool(res.is_error)
                        content = _tool_text(res)
                        report = None if is_error else _parse_report(res)
                    except Exception as exc:   # MCP/protocol error
                        is_error, content, report = True, f"Tool call failed: {exc}", None

                    calls.append({"tool": name, "args": args, "ok": not is_error, "ms": int((time.perf_counter() - t0) * 1000)})
                    log.debug("tool %s %s -> %s", name, args, "ERROR " + content[:200] if is_error else "ok")

                    if report and name not in HIDDEN_VISUAL_TOOLS:
                        report["tool"] = name
                        extras = report.pop("extra_reports", None) or []
                        visuals.append(report)
                        for ex in extras:
                            ex.setdefault("period", report.get("period"))
                            ex.setdefault("outlet", report.get("outlet"))
                            visuals.append(ex)

                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": ("ERROR: " if is_error else "") + content[:12000]})

        if not answer:
            answer = "Sorry, I could not find an answer to that. Please try rephrasing your question."

        return {
            "answer": answer,
            "visuals": visuals[-4:],          # at most 4 cards
            "tool_calls": calls,
            "model": settings.llm_model,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "llm_rounds": rounds,
            "usage": {**usage, "total_tokens": usage["prompt_tokens"] + usage["completion_tokens"]},
        }
