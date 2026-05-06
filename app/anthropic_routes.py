"""
Anthropic Messages API 路由 — MiMo2API no-tools 适配层

将 Anthropic Messages API 格式请求转换为 MiMo API 调用并转换回 Anthropic 格式。

no-tools 版本：不含工具调用支持，流式实时输出 thinking + text blocks。
"""
import json
import uuid
import time
import re
import httpx
import base64 as b64
from typing import Optional, AsyncIterator

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import StreamingResponse, JSONResponse

from .anthropic import (
    convert_request as _anthropic_convert_request,
    convert_response as _anthropic_convert_response,
    stream_response as _anthropic_stream_response,
    nonstream_to_sse as _anthropic_nonstream_to_sse,
    error_response as _anthropic_error_response,
)
from .batch import (
    count_tokens as _anthropic_count_tokens,
    store_message as _anthropic_store_message,
    get_message as _anthropic_get_message,
    create_batch as _anthropic_create_batch,
    get_batch as _anthropic_get_batch,
    list_batches as _anthropic_list_batches,
    cancel_batch as _anthropic_cancel_batch,
    get_batch_results as _anthropic_get_batch_results,
    delete_batch as _anthropic_delete_batch,
    process_batch_requests as _anthropic_process_batch_requests,
)
from .batch import init_batch_storage as _anthropic_init_batch_storage
from .mimo_client import MimoClient, MimoApiError
from .config import config_manager
from .models import OpenAIMessage
from .utils import build_query_from_messages, extract_medias_from_messages, upload_media_to_mimo, upload_text_file_to_mimo
from .session_store import (
    get_or_create_session as _get_or_create_session,
    update_tokens as _update_session_tokens,
    update_fingerprint as _update_session_fingerprint,
)
from .usage_store import add_usage as _add_usage
from .routes import (
    _strip_citations, _strip_tool_result_blocks,
    _safe_flush, validate_api_key,
)

router = APIRouter()

# ─── 常量 ─────────────────────────────────────────────────────

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"

# ─── Anthropic SSE 辅助函数 ───────────────────────────────────

def _make_msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:24]}"


def _make_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _make_message_start(model: str, msg_id: str) -> str:
    return _make_sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    })


def _make_cb_start(index: int, block: dict) -> str:
    return _make_sse("content_block_start", {
        "type": "content_block_start", "index": index, "content_block": block,
    })


def _make_text_delta(index: int, text: str) -> str:
    return _make_sse("content_block_delta", {
        "type": "content_block_delta", "index": index,
        "delta": {"type": "text_delta", "text": text},
    })


def _make_thinking_delta(index: int, text: str) -> str:
    return _make_sse("content_block_delta", {
        "type": "content_block_delta", "index": index,
        "delta": {"type": "thinking_delta", "thinking": text},
    })


def _make_cb_stop(index: int) -> str:
    return _make_sse("content_block_stop", {
        "type": "content_block_stop", "index": index,
    })


def _make_message_delta(stop_reason: str = "end_turn") -> str:
    return _make_sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason},
        "usage": {"output_tokens": 0},
    })


def _make_message_stop() -> str:
    return _make_sse("message_stop", {"type": "message_stop"})


# ─── 流式转换：MiMo SSE → Anthropic SSE ───────────────────────

class _StreamState:
    """追踪 Anthropic 流式状态（no-tools 简化版）。"""
    def __init__(self):
        self.buf = ""
        self.in_think = False
        self.text_index = None
        self.think_index = None
        self.next_index = 0
        self.think_active = False
        self.text_active = False
        self.any_think = False
        self.any_text = False


async def _anthropic_stream(
    mimo_stream: AsyncIterator[dict],
    model: str,
    msg_id: str,
) -> AsyncIterator[str]:
    """
    no-tools 版本：将 MiMo 的流式事件实时转换为 Anthropic SSE 事件。

    实时解析 <think> 标签，发出 thinking → text 顺序的 content blocks。
    不含工具调用支持。
    """
    st = _StreamState()
    yield _make_message_start(model, msg_id)

    async for ev in mimo_stream:
        if ev.get("type") == "usage":
            continue
        chunk = ev.get("content", "")
        if not chunk:
            continue

        st.buf += chunk.replace("\x00", "")

        while True:
            if not st.in_think:
                oi = st.buf.find(THINK_OPEN)
                if oi != -1:
                    pre = st.buf[:oi]
                    if pre:
                        if not st.any_text:
                            idx = st.next_index
                            st.next_index += 1
                            st.text_index = idx
                            st.text_active = True
                            st.any_text = True
                            yield _make_cb_start(idx, {"type": "text", "text": ""})
                        yield _make_text_delta(st.text_index, pre)
                    st.in_think = True
                    st.buf = st.buf[oi + len(THINK_OPEN):]
                    continue

                if st.buf:
                    if not st.any_text:
                        idx = st.next_index
                        st.next_index += 1
                        st.text_index = idx
                        st.text_active = True
                        st.any_text = True
                        yield _make_cb_start(idx, {"type": "text", "text": ""})
                    yield _make_text_delta(st.text_index, st.buf)
                    st.buf = ""
                break

            else:
                ci = st.buf.find(THINK_CLOSE)
                if ci != -1:
                    think_text = st.buf[:ci]
                    if think_text:
                        if not st.any_think:
                            idx = st.next_index
                            st.next_index += 1
                            st.think_index = idx
                            st.think_active = True
                            st.any_think = True
                            yield _make_cb_start(idx, {"type": "thinking", "thinking": "", "signature": ""})
                        yield _make_thinking_delta(st.think_index, think_text)
                    if st.think_active:
                        yield _make_cb_stop(st.think_index)
                        st.think_active = False
                    st.in_think = False
                    st.buf = st.buf[ci + len(THINK_CLOSE):]
                    continue

                safe, keep = _safe_flush(st.buf)
                if safe:
                    if not st.any_think:
                        idx = st.next_index
                        st.next_index += 1
                        st.think_index = idx
                        st.think_active = True
                        st.any_think = True
                        yield _make_cb_start(idx, {"type": "thinking", "thinking": "", "signature": ""})
                    yield _make_thinking_delta(st.think_index, safe)
                st.buf = keep
                break

    # --- 流结束：处理剩余 buffer ---
    if st.buf:
        if st.in_think:
            if not st.any_think:
                idx = st.next_index
                st.next_index += 1
                st.think_index = idx
                st.think_active = True
                st.any_think = True
                yield _make_cb_start(idx, {"type": "thinking", "thinking": "", "signature": ""})
            yield _make_thinking_delta(st.think_index, st.buf)
            if st.think_active:
                yield _make_cb_stop(st.think_index)
                st.think_active = False
        else:
            if not st.any_text:
                idx = st.next_index
                st.next_index += 1
                st.text_index = idx
                st.text_active = True
                st.any_text = True
                yield _make_cb_start(idx, {"type": "text", "text": ""})
            yield _make_text_delta(st.text_index, st.buf)

    if st.think_active:
        yield _make_cb_stop(st.think_index)
        st.think_active = False
    if st.text_active:
        yield _make_cb_stop(st.text_index)
        st.text_active = False

    yield _make_message_delta("end_turn")
    yield _make_message_stop()


# ─── /v1/messages ────────────────────────────────────────────

@router.post("/v1/messages")
async def anthropic_messages(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """Anthropic Messages API 兼容端点（no-tools 版，无工具调用）。"""
    auth = authorization or (f"Bearer {x_api_key}" if x_api_key else None)
    if not validate_api_key(auth):
        raise HTTPException(
            status_code=401,
            detail=_anthropic_error_response("invalid api key", "authentication_error"),
        )

    body = await request.json()
    stream = body.get("stream", False)
    model = body.get("model", "mimo-v2-flash")
    msg_id = _make_msg_id()

    # ── 转换格式：Anthropic → OpenAI ──
    openai_body = _anthropic_convert_request(body)
    openai_messages = openai_body.get("messages", [])

    # ── 获取账号 ──
    account = config_manager.get_next_account()
    if not account:
        raise HTTPException(
            status_code=503,
            detail=_anthropic_error_response("no mimo account", "service_error"),
        )

    # ── 构建 MiMo query ──
    msgs_as_objects = []
    for m in openai_messages:
        if isinstance(m, dict):
            msgs_as_objects.append(OpenAIMessage(**m))
        else:
            msgs_as_objects.append(m)

    query = build_query_from_messages(msgs_as_objects)

    # ── 提取并上传图片/文件 ──
    query_text, base64_medias, text_files, processed_msgs = extract_medias_from_messages(msgs_as_objects)

    # 扫描 HTTP URL 图片（Anthropic source.type="url" → image_url with HTTP URL）
    http_images = []
    for m in openai_messages:
        if isinstance(m, dict) and m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        img_url = item.get("image_url", {})
                        url = img_url.get("url", "") if isinstance(img_url, dict) else str(img_url)
                        if url and (url.startswith("http://") or url.startswith("https://")):
                            http_images.append(url)

    if http_images:
        async with httpx.AsyncClient(timeout=30) as http_client:
            for url in http_images:
                try:
                    resp = await http_client.get(url)
                    if resp.status_code == 200:
                        img_b64 = b64.b64encode(resp.content).decode()
                        content_type = resp.headers.get("content-type", "image/jpeg")
                        base64_medias.append({
                            "base64": img_b64,
                            "mimeType": content_type,
                            "type": "image"
                        })
                except Exception as e:
                    print(f"[Anthropic] failed to download image URL {url}: {e}")

    # 上传到 MiMo CDN
    multi_medias = []
    if base64_medias:
        for media in base64_medias:
            media_obj = await upload_media_to_mimo(
                media["base64"], media["mimeType"], account, model
            )
            if media_obj:
                multi_medias.append(media_obj)

    if text_files:
        for tf in text_files:
            media_obj = await upload_text_file_to_mimo(
                tf["base64"], tf["filename"], tf["mimeType"], account, model
            )
            if media_obj:
                multi_medias.append(media_obj)

    # ── 会话管理 ──
    conv_id, conv_is_new = _get_or_create_session(
        account.user_id, msgs_as_objects, model,
    )

    client = MimoClient(account)

    # ═══════════════════════════════════════════════════════════
    # 流式
    # ═══════════════════════════════════════════════════════════
    if stream:
        async def _wrap():
            mimo_gen = client.stream_api(query, False, model, multi_medias=multi_medias, conversation_id=conv_id)
            async for event in _anthropic_stream(mimo_gen, model, msg_id):
                yield event

        return StreamingResponse(
            _wrap(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    # ═══════════════════════════════════════════════════════════
    # 非流式
    # ═══════════════════════════════════════════════════════════
    try:
        content, think_content, usage = await client.call_api(
            query, False, model, multi_medias=multi_medias, conversation_id=conv_id,
        )

        # 保存用量
        if usage:
            _add_usage(model, usage.get("promptTokens", 0), usage.get("completionTokens", 0))
            _update_session_tokens(account.user_id, conv_id, usage.get("promptTokens", 0))

        # 清理模型输出
        content = _strip_tool_result_blocks(content)
        content = _strip_citations(content)

        # 构建 OpenAI 格式的非流式响应
        message = {"role": "assistant", "content": content}
        if think_content:
            message["reasoning_content"] = think_content

        openai_result = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": usage.get("promptTokens", 0) if usage else 0,
                "completion_tokens": usage.get("completionTokens", 0) if usage else 0,
                "total_tokens": (usage.get("promptTokens", 0) + usage.get("completionTokens", 0)) if usage else 0,
            },
        }

        # 转换为 Anthropic 格式
        anthropic_result = _anthropic_convert_response(openai_result, model, msg_id)

        # 存储消息
        _anthropic_store_message(msg_id, anthropic_result)

        return anthropic_result

    except MimoApiError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_anthropic_error_response(f"MiMo API: {e.response_body[:200]}", "api_error"),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=_anthropic_error_response(str(e), "internal_error"),
        )


# ─── /v1/messages/count_tokens ──────────────────────────────

@router.post("/v1/messages/count_tokens")
async def anthropic_count_tokens_ep(request: Request):
    """计算 Anthropic 格式消息的 token 数（本地估算）。"""
    body = await request.json()
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return _anthropic_count_tokens(body, enc)
    except ImportError:
        return {"input_tokens": 0, "output_tokens": 0}


# ─── /v1/messages/{message_id} ──────────────────────────────

@router.get("/v1/messages/{message_id}")
async def anthropic_get_msg_ep(message_id: str):
    """查询已存储的消息。"""
    msg = _anthropic_get_message(message_id)
    if msg is None:
        raise HTTPException(
            status_code=404,
            detail=_anthropic_error_response(f"Message {message_id} not found", "not_found_error"),
        )
    return msg


# ─── Batches ────────────────────────────────────────────────

@router.post("/v1/messages/batches")
async def anthropic_create_batch_ep(request: Request):
    """创建批量任务。"""
    body = await request.json()
    requests_data = body.get("requests", [])
    model = body.get("model", "mimo-v2-flash")
    batch = _anthropic_create_batch(requests_data, model)

    async def _process_one(req):
        ob = _anthropic_convert_request(req.get("body", {}))
        msgs = ob.get("messages", [])
        msgs_objs = [OpenAIMessage(**m) if isinstance(m, dict) else m for m in msgs]
        query = build_query_from_messages(msgs_objs)

        account = config_manager.get_next_account()
        if not account:
            return _anthropic_error_response("no mimo account", "service_error")

        client = MimoClient(account)
        try:
            c, tc, usage = await client.call_api(query, False, model)
            c = _strip_citations(c)
            message = {"role": "assistant", "content": c}
            if tc:
                message["reasoning_content"] = tc
            openai_resp = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                "object": "chat.completion", "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
            ant = _anthropic_convert_response(openai_resp, model)
            return ant
        except Exception as e:
            return _anthropic_error_response(str(e)[:500], "api_error")

    import asyncio
    asyncio.create_task(_anthropic_process_batch_requests(batch["id"], _process_one))
    return batch


@router.get("/v1/messages/batches")
async def anthropic_list_batches_ep(status: str = None, limit: int = 20, after_id: str = None):
    return _anthropic_list_batches(status, min(limit, 100), after_id)


@router.get("/v1/messages/batches/{batch_id}")
async def anthropic_get_batch_ep(batch_id: str):
    b = _anthropic_get_batch(batch_id)
    if b is None:
        raise HTTPException(
            status_code=404,
            detail=_anthropic_error_response(f"Batch {batch_id} not found", "not_found_error"),
        )
    return b


@router.post("/v1/messages/batches/{batch_id}/cancel")
async def anthropic_cancel_batch_ep(batch_id: str):
    b = _anthropic_cancel_batch(batch_id)
    if b is None:
        raise HTTPException(
            status_code=404,
            detail=_anthropic_error_response(f"Batch {batch_id} not found", "not_found_error"),
        )
    return b


@router.get("/v1/messages/batches/{batch_id}/results")
async def anthropic_batch_results_ep(batch_id: str):
    results = _anthropic_get_batch_results(batch_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=_anthropic_error_response(f"Results for batch {batch_id} not found", "not_found_error"),
        )
    return StreamingResponse(
        iter([json.dumps(r, ensure_ascii=False) + "\n" for r in results]),
        media_type="application/jsonl",
        headers={"Content-Disposition": f"attachment; filename={batch_id}_results.jsonl"},
    )


@router.delete("/v1/messages/batches/{batch_id}")
async def anthropic_delete_batch_ep(batch_id: str):
    _anthropic_delete_batch(batch_id)
    return {"id": batch_id, "type": "message_batch_deleted", "object": "message_batch"}
