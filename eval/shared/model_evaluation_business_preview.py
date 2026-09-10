"""Offline business review: groups, source membership and candidate video frames."""

from collections import Counter
from html import escape
import json
from pathlib import Path

from PIL import Image, ImageOps

from model_evaluation_business import check_baseline, classify
from model_evaluation_inputs import (
    digest,
    fingerprint,
    fixture_roots,
    outside,
    write_json,
)
from model_evaluation_preview import read_encoding


def render_business(
    target: Path, prepared: dict, result: dict, encoded: dict, config: dict
) -> dict:
    target.mkdir(parents=True, exist_ok=False)
    thumbs = target / "thumbs"
    thumbs.mkdir()
    sources = prepared["business"]["sources"]
    source_root = Path(prepared["source_root"])
    rows = {row["id"]: row for row in prepared["inputs"]}
    by_source = {}
    for row in rows.values():
        by_source.setdefault(row["source"], []).append(row)
    images = {}
    failures = []

    def thumbnail(key, path, transpose=False):
        if key in images:
            return images[key]
        name = fingerprint(key)[:24] + ".jpg"
        try:
            with Image.open(path) as opened:
                if transpose:
                    opened = ImageOps.exif_transpose(opened)
                image = opened.convert("RGB")
            image.thumbnail((320, 240))
            image.save(thumbs / name, quality=85)
            image.close()
        except OSError as error:
            failures.append({"key": key, "error": str(error)})
            images[key] = None
            return None
        images[key] = "thumbs/" + name
        return images[key]

    def input_image(identity):
        row = rows[identity]
        return thumbnail("input:" + identity, row["image_path"])

    def photo(src, alt, small=False):
        if not src:
            return '<div class="placeholder">无可用缩略图</div>'
        return f'<img class="{"small" if small else "photo"}" loading="lazy" src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}">'

    def selected_image(source):
        identity = result["selected_inputs"].get(source)
        if identity:
            return input_image(identity)
        if sources[source]["kind"] == "image":
            return thumbnail("source:" + source, source_root / source, transpose=True)
        return None

    source_cards = []

    def source_card(source, roles):
        source_cards.append(source)
        identity = result["selected_inputs"].get(source)
        candidates = by_source.get(source, [])
        roles = " · ".join(roles)
        explanation = (
            "本次已编码；缩略图来自实际模型输入"
            if identity
            else "本次未成功编码；图片缩略图仅供展开核对"
        )
        if not sources[source]["visual_requested"]:
            explanation = "初始素材组的展开成员，未请求编码；缩略图仅供核对"
        frame_html = []
        for row in candidates:
            if row["kind"] != "video":
                continue
            selected = row["id"] == identity
            stamp = (
                "容器探测"
                if row["sample_time_seconds"] is None
                else f"请求位置 {row['sample_time_seconds']:.6f} s"
            )
            if row["state"] == "ready":
                body = f'<a href="{Path(row["image_path"]).as_uri()}" target="_blank">{photo(input_image(row["id"]), row["id"])}</a>'
            else:
                body = f'<div class="error">抽帧失败：{escape(row.get("error", "unknown"))}</div>'
            frame_html.append(
                f'<article class="frame {"chosen" if selected else ""}" data-input-id="{row["id"]}"><strong>{"✓ 选中关键帧" if selected else "候选帧"}</strong><p>{stamp}</p>{body}</article>'
            )
        actual_link = (
            f'<a href="{Path(rows[identity]["image_path"]).as_uri()}" target="_blank">打开实际编码输入</a>'
            if identity
            else ""
        )
        details = (
            f'<details class="frames"><summary>视频候选帧与失败（{len(candidates)}）</summary><div class="grid">{"".join(frame_html)}</div><p>位置为业务 producer 的请求 seek 时间；实际解码 PTS 未暴露，不冒充精确帧时间。</p></details>'
            if frame_html
            else ""
        )
        meta = sources[source]
        meta_text = (
            f"时间：{meta['capture_time'] or '缺失'} · GPS：{meta['gps'] or '缺失'}"
        )
        return f'''<article class="source-card" data-source="{escape(source, quote=True)}">
<div class="source-top">{photo(selected_image(source), source)}<div><strong>{escape(Path(source).name)}</strong><p class="role">{roles}</p><p>{escape(explanation)}</p><p><a href="{(source_root / source).as_uri()}" target="_blank">打开源图片／视频</a> {actual_link}</p><small>{escape(source)}<br>{escape(meta_text)}</small></div></div>{details}</article>'''

    bundle_for = {
        member: bundle
        for bundle in prepared["business"]["bundles"]
        for member in bundle["members"]
    }
    group_html = []
    for index, group in enumerate(result["groups"], 1):
        representative = group["representative_path"]
        highlights = []
        for role, paths in [
            ("代表", [representative]),
            ("边界", group["boundary_paths"]),
            ("差异较大", group["outlier_paths"]),
        ]:
            for source in paths:
                highlights.append(
                    f"<figure>{photo(selected_image(source), source, True)}<figcaption>{role} · {escape(Path(source).name)}</figcaption></figure>"
                )
        cards = []
        for source in group["members"]:
            roles = []
            if source == representative:
                roles.append("组代表")
            if source in group["boundary_paths"]:
                roles.append("组边界")
            if source in group["outlier_paths"]:
                roles.append("差异较大样本")
            if source in group["conflict_paths"]:
                roles.append("比较依据不一致")
            bundle = bundle_for.get(source)
            if bundle and source == bundle["representative"]:
                roles.append("初始素材组优先代表")
            cards.append(source_card(source, roles))
        group_html.append(f'''<details class="group" data-group="{escape(group["group_id"], quote=True)}"><summary><span class="group-title">组 {index:03d} · {len(group["members"])} 个源媒体</span><div class="highlights">{"".join(highlights)}</div></summary>
<p class="note">限制：{escape("；".join(group["qualifications"]) or "未记录额外限制")}。代表仅替代阅读，不证明全部成员相同。</p>
<details><summary>分组依据与初始素材组</summary><pre>{escape(json.dumps({"basis": group["basis"], "initial_bundles": sorted({bundle_for[s]["id"] for s in group["members"] if s in bundle_for})}, ensure_ascii=False, indent=2))}</pre></details>
{"".join(cards)}</details>''')
    exception_cards = "".join(
        source_card(source, ["未进入视觉分组"]) for source in result["exceptions"]
    )
    failed_inputs = [row for row in rows.values() if row["state"] == "failed"]
    failure_list = "".join(
        f"<li>{escape(row['source'])} · {row['sample_time_seconds']}<pre>{escape(row.get('error', ''))}</pre></li>"
        for row in failed_inputs
    )
    if sorted(source_cards) != sorted(sources):
        raise ValueError("Preview must contain every source exactly once")
    performance = encoded["performance"]
    runtime = encoded["runtime"]
    effective = encoded.get("effective_encoder", {})
    device = str(effective.get("device", runtime["device"])).upper()
    precision = str(effective.get("precision", runtime["precision"]))
    title = config["model"]["model_id"].split("/")[-1]
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MediaSense 业务基线 · {escape(title)}</title>
<style>
:root{{font-family:system-ui,sans-serif;color:#203047;background:#eff3f7}}body{{max-width:1320px;margin:24px auto;padding:0 20px}}header,.panel{{background:white;padding:22px;border-radius:12px;margin-bottom:18px}}h1{{font-size:27px;margin:0 0 8px}}h2{{font-size:20px}}p{{line-height:1.6}}.pending,.role{{color:#925506}}.stats{{font-size:18px;font-weight:650}}button{{padding:10px 16px;border:0;border-radius:6px;color:white;background:#254c70;cursor:pointer;margin:0 8px 12px 0}}details{{margin:10px 0}}summary{{cursor:pointer}}.group{{background:white;border:1px solid #c7d3e0;border-radius:9px;padding:16px;margin-bottom:14px}}.group>summary{{font-weight:600}}.group-title{{font-size:19px}}.highlights{{display:flex;flex-wrap:wrap;gap:14px;margin:12px 0 0}}figure{{margin:0;width:175px}}figcaption{{font-size:11px;overflow-wrap:anywhere;font-weight:400}}.small{{width:175px;height:110px;object-fit:contain;background:#edf1f5;border-radius:5px}}.source-card{{border-top:1px solid #dce3ec;padding:14px 0}}.source-top{{display:flex;gap:18px;align-items:flex-start}}.photo{{width:240px;height:170px;object-fit:contain;background:#edf1f5;border-radius:5px}}.placeholder{{width:180px;min-height:80px;padding:20px;background:#edf1f5;box-sizing:border-box}}small{{overflow-wrap:anywhere;color:#5f6d7e}}a{{color:#226a9f;margin-right:12px}}.grid{{display:flex;flex-wrap:wrap;gap:14px}}.frame{{max-width:270px;padding:12px;border:1px solid #c7d3e0;border-radius:7px}}.chosen{{border:3px solid #287a65;background:#f0faf5}}.error{{color:#9b3e20;overflow-wrap:anywhere;font-size:12px}}.note{{color:#5f6d7e;font-size:13px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}@media(max-width:680px){{.source-top{{display:block}}.photo{{width:100%;height:200px}}body{{padding:0 10px}}figure{{width:120px}}.small{{width:120px;height:85px}}}}
</style><header><h1>MediaSense 业务分组与代表选择</h1><p>{escape(title)} · {escape(device)} · {escape(precision)} · batch {runtime["batch_size"]}</p><p class="pending">技术执行已完成 · 待人工质量验收</p>
<p class="stats">{len(sources)} 个源媒体 → {result["point_count"]} 个分组候选 → {len(result["groups"])} 个组</p>
<p>{encoded["counts"]["encoded"]} 个图片／帧成功编码 · {len(failed_inputs)} 个输入准备失败 · {len(result["exceptions"])} 个源未进入视觉分组 · 未交代遗漏 0</p>
<p>加载 {performance["model_load_seconds"]:.2f} s · 编码 {performance["encoding_seconds"]:.2f} s · {performance["inputs_per_second"]:.3f} 输入/s · 编码进程峰值 RSS {performance["peak_process_rss_bytes"] / 2**30:.3f} GiB（不含子进程）</p>
<p>请检查：组内是否混入不同内容、组代表是否合适、视频选中帧是否遗漏有用画面。展开组看全部源成员，展开视频看全部已请求候选帧。</p>
<details><summary>固定方法与性能口径</summary><pre>{escape(json.dumps(config["classification"], ensure_ascii=False, indent=2))}</pre><p>时间／位置／视觉边界与组首比较；复用 MediaSense 业务函数。层级是实际成员关系。编码含读取、预处理、计算、取回与同步，抽帧与预览不计入速度；无向量缓存命中。素材含缩小图片与稀疏视频代理。</p></details></header>
<button id="expand" onclick="document.querySelectorAll('details.group').forEach(x=>x.open=true)">展开所有组</button><button id="collapse" onclick="document.querySelectorAll('details.group').forEach(x=>x.open=false)">收起所有组</button>
{"".join(group_html)}<section class="panel"><h2>未进入视觉分组的源媒体</h2>{exception_cards or "<p>无</p>"}</section>
<section class="panel"><details id="failures"><summary>输入准备失败明细（{len(failed_inputs)}）</summary><ul>{failure_list}</ul></details><p>失败输入仍归属原媒体；源媒体可能由同组其他成员代表。未请求编码不等于读取或质量验证通过。</p></section></html>"""
    (target / "index.html").write_text(page, encoding="utf-8")
    return {
        "source_cards": len(source_cards),
        "thumbnails": len([value for value in images.values() if value]),
        "thumbnail_failures": failures,
        "external_resources": 0,
    }


def preview(config: dict, output: Path, summary_path: Path) -> dict:
    outside(output, *fixture_roots(config))
    outside(summary_path, *fixture_roots(config))
    encoded, prepared, rows, vectors = read_encoding(config, output)
    identity = check_baseline(config, prepared)
    result = classify(config, prepared, vectors)
    render = render_business(output / "preview", prepared, result, encoded, config)
    write_json(output / "preview/groups.json", result)
    failures = encoded["counts"]["input_failures"]
    summary = {
        "status": "completed_with_input_failures" if failures else "completed",
        "human_acceptance": "待人工验收",
        "baseline_ref": config.get("baseline_ref"),
        "classification_fingerprint": identity,
        "input_fingerprint": prepared["input_fingerprint"],
        "source_fingerprint": prepared["source_fingerprint"],
        "classification": config["classification"],
        "counts": {
            **encoded["counts"],
            "groups": len(result["groups"]),
            "business_points": result["point_count"],
            "grouped_sources": result["grouped_sources"],
            "ungrouped_sources": len(result["exceptions"]),
            "omitted": 0,
        },
        "performance": encoded["performance"],
        "environment": encoded["environment"],
        "code": encoded["code"],
        "business_code": config["inputs"]["business_code"],
        "effective_encoder": encoded["effective_encoder"],
        "embedding_identity": encoded["embedding_identity"],
        "encoding_summary": str((output / "encoding.json").resolve()),
        "preview": str((output / "preview/index.html").resolve()),
        "preview_checks": render,
        "result_sha256": digest(output / "preview/groups.json"),
        "preparation_failures_by_kind": dict(
            Counter(
                row["kind"] for row in prepared["inputs"] if row["state"] == "failed"
            )
        ),
    }
    write_json(summary_path, summary)
    return summary
