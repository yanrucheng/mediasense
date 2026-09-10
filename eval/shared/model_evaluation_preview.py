"""Static, offline thumbnails and a reviewable tree; no quality score or service."""

from html import escape
import json
from pathlib import Path
import struct

from PIL import Image

from model_evaluation import inference_fingerprint
from model_evaluation_hierarchy import leaf_members, linear_hierarchical
from model_evaluation_inputs import (
    digest,
    fingerprint,
    fixture_roots,
    outside,
    validate_inputs,
    write_json,
)


def read_encoding(config: dict, output: Path) -> tuple[dict, dict, list[dict], dict]:
    encoded = json.loads((output / "encoding.json").read_text())
    if encoded["status"] != "encoded" or encoded[
        "inference_fingerprint"
    ] != inference_fingerprint(config):
        raise ValueError(
            "This preview requires the exact completed encoding configuration"
        )
    for filename, key in (
        ("rows.json", "rows_sha256"),
        ("vectors.f32", "vectors_sha256"),
    ):
        if digest(output / filename) != encoded[key]:
            raise ValueError(f"Retained encoding changed: {filename}")
    prepared = validate_inputs(config, Path(encoded["inputs_manifest"]))
    rows = json.loads((output / "rows.json").read_text())
    if [row["id"] for row in rows] != [row["id"] for row in prepared["inputs"]]:
        raise ValueError("Retained row identities lost correspondence")
    successful = [row for row in rows if row["state"] == "encoded"]
    if [row["vector_row"] for row in successful] != list(range(len(successful))):
        raise ValueError("Vector row indices must be complete, unique, and ordered")
    dimensions = config["model"]["dimensions"]
    payload = (output / "vectors.f32").read_bytes()
    if len(payload) != len(successful) * dimensions * 4:
        raise ValueError("Vector file length differs from the accounted rows")
    vectors = {
        row["id"]: values
        for row, values in zip(
            successful, struct.iter_unpack(f"<{dimensions}f", payload), strict=True
        )
    }
    for source, outcome in zip(prepared["inputs"], rows, strict=True):
        expected = "encoded" if source["state"] == "ready" else "input_failed"
        if outcome["state"] != expected:
            raise ValueError("Encoding does not account for every prepared input")
    return encoded, prepared, rows, vectors


def render_html(
    target: Path,
    tree: dict,
    prepared: dict,
    encoded: dict,
    *,
    title: str,
    classification: dict | None,
) -> None:
    """Rendering can also show a plainly labeled unclassified input review."""
    target.mkdir(parents=True, exist_ok=False)
    (target / "thumbs").mkdir()
    records = {row["id"]: row for row in prepared["inputs"]}
    members = leaf_members(tree)
    available = {row["id"] for row in prepared["inputs"] if row["state"] == "ready"}
    if set(members) != available or len(members) != len(available):
        raise ValueError("Preview tree must cover every ready input exactly once")
    for identity in members:
        with Image.open(records[identity]["image_path"]) as opened:
            image = opened.convert("RGB")
        image.thumbnail((280, 210))
        image.save(target / "thumbs" / f"{identity.replace(':', '-')}.jpg", quality=85)
        image.close()

    def thumb(identity, small=False):
        return f'<img class="{"small" if small else "photo"}" loading="lazy" src="thumbs/{identity.replace(":", "-")}.jpg" alt="{escape(records[identity]["source"], quote=True)}">'

    def card(identity):
        row = records[identity]
        source = escape(row["source"])
        frame = (
            f" · {row['pts_seconds']:.6f} s · frame {row['frame_index']}"
            if row["kind"] == "video"
            else ""
        )
        source_url = (Path(prepared["source_root"]) / row["source"]).as_uri()
        return (
            f'<article class="card" data-input-id="{identity}"><a href="{Path(row["image_path"]).as_uri()}" target="_blank">{thumb(identity)}</a>'
            f"<p>{escape(Path(row['source']).name)}<br><small>{identity}{frame}</small></p>"
            f'<a class="source" href="{source_url}" target="_blank" title="{source}">打开源图片／视频</a><details><summary>来源路径</summary><small>{source}</small></details></article>'
        )

    def branch(node, label, root=False):
        identities = leaf_members(node)
        sample = (
            [
                identities[index]
                for index in sorted(
                    {round(i * (len(identities) - 1) / 3) for i in range(4)}
                )
            ]
            if identities
            else []
        )
        overview = "".join(thumb(identity, True) for identity in sample)
        body = (
            '<div class="grid">'
            + "".join(card(identity) for identity in node["members"])
            + "</div>"
            if "members" in node
            else "".join(
                branch(child, f"{label}.{index:03d}")
                for index, child in enumerate(node["children"], 1)
            )
        )
        return f'<details class="group" {"open" if root else ""}><summary><strong>{label}</strong><span>{len(identities)} 个输入</span><span class="overview">{overview}</span></summary>{body}</details>'

    failures = [row for row in prepared["inputs"] if row["state"] == "failed"]
    failure_html = "".join(
        f"<li><b>{escape(row['id'])}</b> · {escape(row['source'])} · 位置 {row['fraction']}<pre>{escape(row.get('error', ''))}</pre></li>"
        for row in failures
    )
    performance = encoded.get("performance", {})
    seconds = performance.get("encoding_seconds", 0)
    fps = performance.get("inputs_per_second")
    peak = performance.get("peak_process_rss_bytes")
    metrics = (
        f"编码 {seconds:.2f} s · {fps:.3f} 输入/s · 峰值进程 RSS {peak / 2**30:.3f} GiB · 加载 {performance['model_load_seconds']:.2f} s"
        if fps is not None and peak is not None
        else "编码指标尚未完成"
    )
    method = (
        escape(json.dumps(classification, ensure_ascii=False, indent=2))
        if classification
        else "尚未选择分类算法；此页只供检查输入，不是 Hierarchical 分类结果。"
    )
    review_status = (
        "待人工验收 · 分类质量由人判断"
        if classification
        else "尚未分类 · 此页仅核对编码输入，不是 Hierarchical 分类结果"
    )
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
:root{{font-family:system-ui,sans-serif;color:#1e293b;background:#f3f5f8}}body{{max-width:1440px;margin:28px auto;padding:0 22px}}h1{{font-size:28px;margin-bottom:8px}}p{{line-height:1.5}}header{{background:white;border-radius:12px;padding:24px;margin-bottom:20px}}.pending{{color:#8a4b08}}.stats{{font-size:18px;font-weight:600}}button{{padding:9px 16px;background:#223d5c;color:white;border:0;border-radius:6px;cursor:pointer;margin:4px 8px 16px 0}}details.group{{border:1px solid #cbd5e1;border-radius:8px;background:white;margin:10px 0;padding:10px}}.group>.group{{margin-left:18px}}summary{{cursor:pointer}}.group>summary{{display:flex;gap:18px;align-items:center;min-height:52px;list-style:disclosure-closed}}.group>summary:before{{content:"▸"}}.group[open]>summary:before{{content:"▾"}}.overview{{display:flex;gap:5px;margin-left:auto}}.small{{width:68px;height:48px;object-fit:contain;background:#edf1f5;border-radius:4px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px;padding:16px 2px}}.card{{border:1px solid #dbe1e9;border-radius:8px;padding:10px;min-width:0}}.photo{{width:100%;height:180px;object-fit:contain;background:#f3f5f8}}.card p{{font-size:13px;overflow-wrap:anywhere;margin:8px 0}}small,.source{{font-size:12px;overflow-wrap:anywhere}}a{{color:#245b93}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.failures{{border-left:4px solid #bc5a25;padding:8px 20px;background:#fff7ed}}@media(max-width:600px){{.small{{width:38px;height:36px}}.group>summary{{gap:7px}}body{{padding:0 10px}}}}
</style><header><h1>{escape(title)}</h1><p class="pending">{review_status}</p>
<p class="stats">{prepared["source_count"]} 个源媒体 · {len(records)} 个计划输入 · {len(members)} 个可查看 · {len(failures)} 个失败 · 遗漏 0</p>
<p>{metrics}</p><p>点击组展开全部成员，点击缩略图查看模型实际输入。组摘要中的小图仅用于浏览。素材含缩小图片和稀疏代理视频。</p>
<details><summary>方法与统计口径</summary><pre>{method}</pre><p>编码重新执行，缓存命中 0；计时含读取、预处理、计算、结果取回和同步，不含抽帧及预览。RSS 仅编码进程，含模型加载，不含子进程，不与 GPU 分配相加。</p></details></header>
<button onclick="document.querySelectorAll('details.group').forEach(x=>x.open=true)">展开所有组</button><button onclick="document.querySelectorAll('details.group').forEach(x=>x.open=false)">收起所有组</button>
{branch(tree, "全部输入", True)}<section class="failures"><h2>失败与遗漏</h2><p>{len(failures)} 个已记录失败输入；没有未交代的输入。</p><ul>{failure_html}</ul></section></html>"""
    (target / "index.html").write_text(page, encoding="utf-8")


def preview(config: dict, output: Path, summary_path: Path) -> dict:
    output = outside(output, *fixture_roots(config))
    parameters = config["classification"]
    if (
        parameters["status"] != "confirmed"
        or parameters.get("algorithm") != "legacy_linear_hierarchical_visual"
    ):
        raise ValueError(
            "The candidate LinearHierarchicalCluster port has not been selected and confirmed"
        )
    encoded, prepared, rows, vectors = read_encoding(config, output)
    algorithm_path = Path(__file__).with_name("model_evaluation_hierarchy.py")
    classifier_id = fingerprint(
        {
            "parameters": {
                key: value
                for key, value in parameters.items()
                if key not in {"status", "confirmation"}
            },
            "implementation_sha256": digest(algorithm_path),
        }
    )
    if config["baseline_ref"]:
        baseline = json.loads(Path(config["baseline_ref"]).read_text())
        if (
            baseline["input_fingerprint"] != prepared["input_fingerprint"]
            or baseline["classification_fingerprint"] != classifier_id
        ):
            raise ValueError(
                "Candidate and baseline must share inputs and classification; rerun the baseline for a changed recipe"
            )
    records = [row for row in prepared["inputs"] if row["id"] in vectors]
    tree = linear_hierarchical(records, vectors, parameters)
    members = leaf_members(tree)
    if len(members) != len(vectors) or set(members) != set(vectors):
        raise ValueError("Classification omitted or duplicated inputs")
    model_label = config["model"]["model_id"].split("/")[-1]
    render_html(
        output / "preview",
        tree,
        prepared,
        encoded,
        title=f"本地模型评测 · {model_label}",
        classification=parameters,
    )
    write_json(output / "preview/tree.json", tree)
    summary = {
        "status": "completed_with_input_failures"
        if encoded["counts"]["input_failures"]
        else "completed",
        "human_acceptance": "待人工验收",
        "baseline_ref": config["baseline_ref"],
        "encoding_summary": str((output / "encoding.json").resolve()),
        "preview": str((output / "preview/index.html").resolve()),
        "input_fingerprint": prepared["input_fingerprint"],
        "source_fingerprint": prepared["source_fingerprint"],
        "classification": parameters,
        "classification_fingerprint": classifier_id,
        "classification_code_sha256": digest(algorithm_path),
        "preview_code_sha256": digest(Path(__file__)),
        "counts": {**encoded["counts"], "classified": len(members), "omitted": 0},
        "performance": encoded["performance"],
        "environment": encoded["environment"],
        "code": encoded["code"],
        "effective_encoder": encoded["effective_encoder"],
        "embedding_identity": encoded["embedding_identity"],
    }
    write_json(summary_path, summary)
    return summary
