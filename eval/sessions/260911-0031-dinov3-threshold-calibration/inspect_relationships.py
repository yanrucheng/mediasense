"""Inspect relative neighbors and parameter-driven reunions of the old groups."""

from __future__ import annotations

import argparse
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
from model_evaluation_business import classify  # noqa: E402
from model_evaluation_inputs import digest, fingerprint, write_json  # noqa: E402
from model_evaluation_preview import read_encoding  # noqa: E402


def member_map(result):
    return {source: index for index, group in enumerate(result["groups"]) for source in group["members"]}


def inspect(dino_config, dino_source, sig_config, sig_source):
    import numpy as np

    de, prepared, _, dv = read_encoding(dino_config, dino_source)
    se, sp, _, sv = read_encoding(sig_config, sig_source)
    if prepared["input_fingerprint"] != sp["input_fingerprint"]:
        raise ValueError("Model inputs are not comparable")
    fine = classify(dino_config, prepared, dv)
    old = classify(sig_config, sp, sv)
    if fine != json.loads((dino_source / "preview/groups.json").read_text()) or old != json.loads((sig_source / "preview/groups.json").read_text()):
        raise ValueError("Original grouping cannot be reproduced")
    if fine["selected_inputs"] != old["selected_inputs"] or fine["bundle_selection"] != old["bundle_selection"]:
        raise ValueError("Represented inputs differ; do not compare different frames")
    points = [item["representative"] for item in fine["bundle_selection"]]
    if len(points) != fine["point_count"] or len(set(points)) != len(points):
        raise ValueError("This fixture analysis requires one distinct point per selected bundle")
    point_inputs = [fine["selected_inputs"][source] for source in points]
    matrices = {}
    for name, vectors in [("dinov3", dv), ("siglip2", sv)]:
        a = np.asarray([vectors[key] for key in point_inputs], dtype=np.float64)
        a /= np.linalg.norm(a, axis=1, keepdims=True)
        matrices[name] = np.einsum("ik,jk->ij", a, a, optimize=False)
    old_map, fine_map = member_map(old), member_map(fine)
    old_labels = np.asarray([old_map[source] for source in points])
    fine_labels = np.asarray([fine_map[source] for source in points])
    dates = np.asarray([(prepared["business"]["sources"][source]["capture_time"] or "unknown")[:10] for source in points])
    rows_by_id = {row["id"]: row for row in prepared["inputs"]}
    candidates = []
    for index, source in enumerate(points):
        candidates.append({
            "index": index, "source": source, "input_id": point_inputs[index],
            "input_path": rows_by_id[point_inputs[index]]["image_path"],
            "old_group": int(old_labels[index]) + 1, "fine_group": int(fine_labels[index]) + 1,
            "date": str(dates[index]),
            "thumbnail": str((dino_source / "preview/thumbs" / (fingerprint("input:" + point_inputs[index])[:24] + ".jpg")).resolve()),
        })
    split_groups = [i for i in range(len(old["groups"])) if len(set(fine_labels[old_labels == i])) > 1]
    queries = []

    def best(matrix, index, mask):
        eligible = np.flatnonzero(mask)
        if not len(eligible):
            return None
        chosen = int(eligible[np.argmax(matrix[index, eligible])])
        return {"index": chosen, "cosine": float(matrix[index, chosen])}

    for i in range(len(points)):
        if int(old_labels[i]) not in split_groups:
            continue
        inside = (old_labels == old_labels[i]) & (fine_labels != fine_labels[i])
        global_outside = old_labels != old_labels[i]
        local_outside = global_outside & (dates == dates[i])
        item = {"query": i, "old_group": int(old_labels[i]) + 1}
        for model, matrix in matrices.items():
            inner = best(matrix, i, inside)
            item[model] = {"inside_other_child": inner}
            for label, mask in [("outside_global", global_outside), ("outside_same_day", local_outside)]:
                outer = best(matrix, i, mask)
                item[model][label] = outer
                item[model][label + "_margin"] = inner["cosine"] - outer["cosine"] if outer is not None else None
        queries.append(item)

    def distribution(values):
        values = np.asarray(values)
        return {"pairs": len(values), "median": float(np.median(values)), "p10": float(np.quantile(values, .1)), "p90": float(np.quantile(values, .9))} if len(values) else None

    groups = []
    for index in split_groups:
        members = old_labels == index
        internal = members[:, None] & members[None, :] & (fine_labels[:, None] != fine_labels[None, :]) & np.triu(np.ones((len(points), len(points)), dtype=bool), 1)
        external = members[:, None] & ~members[None, :] & (dates[:, None] == dates[None, :])
        groups.append({
            "old_group": index + 1, "source_count": len(old["groups"][index]["members"]),
            "candidate_count": int(members.sum()), "fine_groups": sorted({int(x) + 1 for x in fine_labels[members]}),
            "cosine_distributions": {name: {"cross_child_inside": distribution(matrix[internal]), "outside_same_day": distribution(matrix[external])} for name, matrix in matrices.items()},
            "first_full_reunion": None, "first_clean_reunion": None, "first_outside_mix_before_reunion": None,
            "selected_scales": {},
        })
    sweep = []
    for scale in [.311] + [i / 100 for i in range(32, 121)]:
        config = deepcopy(dino_config)
        config["classification"]["profile"]["content_distance_scale"] = scale
        result = classify(config, prepared, dv)
        mapping = member_map(result)
        sweep.append({"scale": scale, "groups": len(result["groups"])})
        for record in groups:
            parent_members = set(old["groups"][record["old_group"] - 1]["members"])
            parts = sorted({mapping[source] for source in parent_members})
            outside = set().union(*(set(result["groups"][part]["members"]) for part in parts)) - parent_members
            state = {"scale": scale, "groups": [part + 1 for part in parts], "reunited": len(parts) == 1, "outside_source_count": len(outside)}
            if len(parts) == 1 and record["first_full_reunion"] is None:
                record["first_full_reunion"] = state
            if len(parts) == 1 and not outside and record["first_clean_reunion"] is None:
                record["first_clean_reunion"] = state
            if len(parts) > 1 and outside and record["first_outside_mix_before_reunion"] is None:
                record["first_outside_mix_before_reunion"] = state
            if scale in {.85, .9}:
                record["selected_scales"][str(scale)] = state
    summary = {"business_candidates": len(points), "split_old_groups": len(groups), "examined_candidates": len(queries), "new_inference_inputs": 0, "neighbor_margin_for_near_tie": .005, "neighbor_relations": {}}
    for model in matrices:
        summary["neighbor_relations"][model] = {}
        for scope in ["outside_same_day", "outside_global"]:
            margins = [q[model][scope + "_margin"] for q in queries if q[model][scope + "_margin"] is not None]
            summary["neighbor_relations"][model][scope] = {"queries": len(margins), "inside_ahead_over_0_005": sum(m > .005 for m in margins), "outside_ahead_over_0_005": sum(m < -.005 for m in margins), "near_ties": sum(abs(m) <= .005 for m in margins)}
    summary["reunion_scan"] = {
        "scales": "0.311, then 0.32–1.20 in 0.01 increments; not exact critical thresholds",
        "ever_clean_reunion": sum(g["first_clean_reunion"] is not None for g in groups),
        "outside_mix_before_full_reunion": sum(g["first_outside_mix_before_reunion"] is not None for g in groups),
        "selected_scales": {str(scale): {
            "groups": next(r["groups"] for r in sweep if r["scale"] == scale),
            "old_groups_cleanly_reunited": sum(g["selected_scales"][str(scale)]["reunited"] and not g["selected_scales"][str(scale)]["outside_source_count"] for g in groups),
            "old_groups_reunited_with_outsiders": sum(g["selected_scales"][str(scale)]["reunited"] and g["selected_scales"][str(scale)]["outside_source_count"] > 0 for g in groups),
        } for scale in [.85, .9]},
    }
    return {"summary": summary, "candidates": candidates, "queries": queries, "groups": groups, "sweep": sweep, "matrices": {name: value.tolist() for name, value in matrices.items()}, "input_fingerprint": prepared["input_fingerprint"], "source_vectors_sha256": {"dinov3": de["vectors_sha256"], "siglip2": se["vectors_sha256"]}}


def render(data, target):
    candidates = data["candidates"]
    blocks = []

    def photo(index, label):
        c = candidates[index]
        if not Path(c["thumbnail"]).is_file():
            raise ValueError("Missing existing candidate thumbnail")
        return f'<figure><a href="{Path(c["input_path"]).as_uri()}"><img loading="lazy" src="{Path(c["thumbnail"]).as_uri()}"></a><figcaption>{escape(label)}<br>原组 {c["old_group"]:03d} · 细组 {c["fine_group"]:03d}<br>{escape(c["date"])} · {escape(Path(c["source"]).name)}</figcaption></figure>'

    for group in data["groups"]:
        cards = []
        for query in (q for q in data["queries"] if q["old_group"] == group["old_group"]):
            i = query["query"]
            inner = query["dinov3"]["inside_other_child"]["index"]
            scope = "outside_same_day" if query["dinov3"]["outside_same_day"] else "outside_global"
            outer = query["dinov3"][scope]["index"]
            values = []
            for model in ["dinov3", "siglip2"]:
                matrix = data["matrices"][model]
                values.append(f'<tr><td>{model}</td><td>{matrix[i][inner]:.4f}</td><td>{matrix[i][outer]:.4f}</td><td>{matrix[i][inner]-matrix[i][outer]:+.4f}</td></tr>')
            cards.append('<article><div class="triplet">' + photo(i, "查询候选") + photo(inner, "DINO 最接近的原组内另一子组候选") + photo(outer, "DINO 最接近的原组外候选（" + ("同日" if scope == "outside_same_day" else "全局，无同日候选") + "）") + '</div><table><tr><th>同一图片对</th><th>查询↔组内另一子组</th><th>查询↔组外</th><th>差值</th></tr>' + ''.join(values) + '</table></article>')
        state = group["selected_scales"]
        notes = []
        for scale in ["0.85", "0.9"]:
            value = state[scale]
            notes.append(f'尺度 {scale}：落在 {len(value["groups"])} 个新组，涉及原组外 {value["outside_source_count"]} 个源媒体')
        blocks.append(f'<details class="parent"><summary>原 SigLIP 组 {group["old_group"]:03d} · {group["source_count"]} 个源媒体 · {group["candidate_count"]} 个实际候选 · DINO 原版 {len(group["fine_groups"])} 个子组</summary><p>{"；".join(notes)}。</p><details><summary>组内跨子组／同日组外的相似度分布与合并过程</summary><pre>{escape(json.dumps(group, ensure_ascii=False, indent=2))}</pre></details>{"".join(cards)}</details>')
    target.mkdir(parents=True, exist_ok=False)
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>DINOv3 分组关系核对</title><style>body{font-family:system-ui;max-width:1150px;margin:24px auto;padding:16px;background:#f4f6f8;color:#203047}header,.parent{padding:18px;background:white;margin-bottom:16px;border-radius:10px}summary{cursor:pointer;font-weight:600}p,figcaption{line-height:1.6}.triplet{display:flex;flex-wrap:wrap;gap:16px}figure{width:30%;margin:10px 0}img{width:100%;height:170px;object-fit:contain;background:#eef2f5}figcaption{font-size:12px;overflow-wrap:anywhere}article{border-top:1px solid #ccd6df;padding:16px 0}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #ccd6df}pre{white-space:pre-wrap}button{padding:10px;margin:5px}@media(max-width:650px){figure{width:100%}}</style><header><h1>子组之间是否仍比外部更接近？</h1><p>只分析 167 个实际分组候选中的已拆分部分；没有为全部 2,134 个源媒体新算向量。余弦相似度越高越近，差值为“组内另一子组 − 组外”。两行模型分数针对相同的三张图，绝对分数跨模型不直接比较。</p><p>默认组外候选限定同日；全局比较和合并过程保存在 JSON。原 SigLIP 分组含时空规则，不能当作语义真值。请看图判断：组外更近是合理的同类复现，还是错把不相关内容排在前面。只重用既有向量，不是新推理测量。</p><button onclick="document.querySelectorAll('details.parent').forEach(x=>x.open=true)">展开全部</button><button onclick="document.querySelectorAll('details.parent').forEach(x=>x.open=false)">收起全部</button></header>'''
    (target / "index.html").write_text(page + ''.join(blocks) + '</html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    dino = Path('eval/sessions/260910-2212-dinov3-vitb16-512')
    sig = Path('eval/sessions/260910-1717-siglip2-so400m-512')
    data = inspect(json.loads((dino / 'config-mps.json').read_text()), dino / 'outputs/mps', json.loads((sig / 'config-mps.json').read_text()), sig / 'outputs/mps')
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / 'relationships.json', data)
    render(data, args.output / 'preview')
    write_json(args.summary, {**data['summary'], 'input_fingerprint': data['input_fingerprint'], 'source_vectors_sha256': data['source_vectors_sha256'], 'detail': str(args.output / 'relationships.json'), 'detail_sha256': digest(args.output / 'relationships.json'), 'preview': str((args.output / 'preview/index.html').resolve())})
    print(json.dumps(data['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
