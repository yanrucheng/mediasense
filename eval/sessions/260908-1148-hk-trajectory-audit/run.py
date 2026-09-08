"""Read-only reconstruction of the exact 2026-09-08 HK Agent trajectory.

Prints compact metrics to stdout. Does not run MediaSense, contact providers,
write databases, read historical caption bodies, or rewrite source media.
"""

import collections
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

SESSIONS_ROOT = Path('/Users/chengyanru/.codex/sessions/2026/09/08')
SESSION_IDS = [
    '01a07d01-3958-73a3-aca5-19cc5cc8882c',
    '01a07ec4-2697-7921-873e-07764288c7e6',
    '01a07ec4-db61-72f2-af79-69c5405381a9',
    '01a07ed0-86a0-7312-94ba-748e62747fe2',
]
WORKSPACE = Path('/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e')
FIXTURE = Path('/Users/chengyanru/Downloads/ai-album-hk-representative-v1')
RESULT_ID = '876d5056651a2f836364865796f07819ac9c329534819c8b13759127abb62204'
PLAN_START_LINE = 135  # First review call in the final continuation.


def counted(values):
    return dict(sorted(collections.Counter(values).items()))


def database(relative_path):
    connection = sqlite3.connect((WORKSPACE / relative_path).as_uri() + '?mode=ro', uri=True)
    connection.execute('PRAGMA query_only=ON')
    return connection


def result(item):
    value = item.get('result') or {}
    return value.get('structuredContent', {})


def main():
    sessions, events, seen = [], [], set()
    for sid in SESSION_IDS:
        path, = SESSIONS_ROOT.glob('*' + sid + '.jsonl')
        raw = path.read_bytes()
        rows = [json.loads(line) for line in raw.splitlines()]
        sessions.append({'id': sid, 'file': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                         'first': rows[0]['timestamp'], 'last': rows[-1]['timestamp'], 'rows': rows})
        for line, row in enumerate(rows, 1):
            payload = row.get('payload', {})
            if payload.get('type') == 'item_completed' and payload['item']['id'] not in seen:
                seen.add(payload['item']['id'])
                events.append({'session': sid, 'line': line, 'item': payload['item']})

    for previous, current in zip(sessions, sessions[1:]):
        assert current['rows'][0]['payload']['forked_from_id'] == previous['id']
    mcp = [event for event in events if event['item']['type'] == 'McpToolCall']
    reads = [event for event in mcp if event['item']['tool'] == 'mediasense.precheck.read']

    def added_json(filename):
        for event in events:
            change = event['item'].get('changes', {}).get(filename)
            if change and change['type'] == 'add':
                return json.loads(change['content'])
        raise KeyError(filename)

    main_manifest = added_json('/tmp/mediasense-hk-review-manifest.json')
    boundary_manifest = added_json('/tmp/mediasense-hk-boundary-manifest.json')
    candidate = added_json('/tmp/mediasense-hk-plan-candidate.json')
    image_events = [event for event in events if event['item']['type'] == 'ImageView']
    opened = [unquote(urlparse(event['item']['path']).path) for event in image_events]
    direct = {path for path in opened if '/precheck/_artifacts/' in path}
    entry_images = {item['image'] for item in main_manifest}
    boundary_images = {item['image'] for item in boundary_manifest}
    all_images = direct | entry_images | boundary_images
    assert len(opened) == len(set(opened))

    sealed_path = WORKSPACE / 'precheck/_results/sealed' / (RESULT_ID + '.json')
    sealed_bytes = sealed_path.read_bytes()
    sealed = json.loads(sealed_bytes)
    assert sealed['result']['ref'] == 'precheck-result:' + RESULT_ID
    derivations = collections.defaultdict(set)
    for relation in sealed['relationships']:
        if relation['relation'] == 'derived_from':
            derivations[relation['origin']].add(relation['member']['target']['ref'])
    image_sources = collections.defaultdict(set)
    for evidence in sealed['evidence']:
        view = evidence['view']
        path = view.get('access', {}).get('locator', {}).get('value')
        if path in all_images:
            image_sources[path].update(derivations[view['ref']])
    assert all(image_sources[path] for path in all_images)
    visual_source_refs = set().union(*image_sources.values())
    scopes = {relation['member']['target']: relation['member']['scope']
              for relation in sealed['relationships'] if relation['relation'] == 'accounts_for'}
    assert all(scopes[ref] == 'source_media' for ref in visual_source_refs)

    with database('precheck/work.sqlite3') as connection:
        config = json.loads(connection.execute('SELECT execution_config_json FROM precheck_runs').fetchone()[0])
        work = connection.execute('SELECT capability,producer_identity,status,attempt_count,output_json FROM work_records').fetchall()
        run_count = connection.execute('SELECT count(*) FROM precheck_runs').fetchone()[0]
    groups = [json.loads(row[4])['group'] for row in work if row[0] == 'adaptive-compression-group']
    coordinates = []
    coordinate_producers = collections.Counter()
    for capability, _, status, _, output in work:
        if capability in ('source-metadata', 'gpx-location-candidate') and status == 'succeeded':
            for observation in json.loads(output)['observations']:
                if observation['name'] in ('gps_coordinates', 'gpx_coordinates') and observation['status'] == 'available':
                    value = observation['value']
                    coordinates.append((value['latitude'], value['longitude']))
                    coordinate_producers[capability] += 1

    with database('geo/journal.sqlite3') as connection:
        geo_rows = connection.execute('SELECT request_id,state,result_json FROM geo_operation_journal').fetchall()
    assert len(geo_rows) == 1
    geo = json.loads(geo_rows[0][2])
    attempts = sealed['execution_boundary']['audit']['attempts']
    assert len(attempts) == len(geo['attempts'])
    fields = ('input_coordinate', 'provider', 'operation', 'status', 'provider_requests')
    assert all(all(left[key] == right[key] for key in fields) for left, right in zip(attempts, geo['attempts']))
    per_coordinate = collections.Counter(json.dumps(attempt['input_coordinate'], sort_keys=True) for attempt in attempts)
    geo_sources = {ref for attempt in attempts for ref in attempt['source_set']['source_item_refs']}

    resolved_rows, resolved, resolved_media, exposed_old_paths = 0, set(), set(), []
    observation_refs, member_observation_refs, anchor_refs = set(), set(), set()
    excluded_fetches = []
    for event in reads:
        item = event['item']
        arguments, value = item['arguments'], result(item)
        if arguments['action'] == 'resolve':
            members = value.get('members', [])
            resolved_rows += len(members)
            excluded = [member for member in members if member.get('scope') == 'excluded']
            if excluded:
                excluded_fetches.append({'line': event['line'], 'count': len(excluded),
                                         'old_output_paths': sum('representative-run-clustered/' in member['locator']['value'] for member in excluded)})
            for member in members:
                resolved.add(member['source_item_ref'])
                if member['scope'] == 'source_media':
                    resolved_media.add(member['source_item_ref'])
        if arguments['action'] == 'expand':
            for returned in value.get('items', []):
                included = returned.get('included', {})
                if 'anchor_evidence' in included:
                    anchor_refs.add(returned['evidence_ref'])
                if 'observations' in included:
                    observation_refs.add(returned['source_item_ref'])
                if 'member_observations' in arguments.get('include', []):
                    member_observation_refs.add(returned['source_item_ref'])

    def collect_scope_samples(value):
        if isinstance(value, dict):
            if value.get('path') == 'representative-run-clustered':
                exposed_old_paths.extend(value.get('representative_paths', []))
            for child in value.values():
                collect_scope_samples(child)
        elif isinstance(value, list):
            for child in value:
                collect_scope_samples(child)

    for event in mcp:
        if event['item']['tool'] == 'mediasense.precheck.run':
            collect_scope_samples(result(event['item']))

    seen_responses, usage, image_batches = set(), collections.Counter(), []
    for line, row in enumerate(sessions[-1]['rows'], 1):
        payload = row.get('payload', {})
        if row['type'] == 'token_usage_record' and line >= PLAN_START_LINE:
            response_id = payload['response_id']
            if response_id not in seen_responses:
                seen_responses.add(response_id)
                usage.update({key: value for key, value in payload['usage'].items() if isinstance(value, int)})
        if payload.get('type') in ('custom_tool_call_output', 'function_call_output') and isinstance(payload.get('output'), list):
            images = sum(block.get('type') in ('image', 'input_image') for block in payload['output'])
            if images:
                image_batches.append({'line': line, 'images': images})
    assert sum(batch['images'] for batch in image_batches) == len(image_events)

    media_manifest = [json.loads(line) for line in (FIXTURE / 'manifests/media-manifest.jsonl').read_text().splitlines()]
    mismatches = []
    for entry in media_manifest:
        source = FIXTURE / 'test-260831/260501-HK美食之旅' / entry['path']
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry['derived_sha256']:
            mismatches.append(entry['path'])

    metrics = {
        'sessions': [{key: value for key, value in session.items() if key != 'rows'} for session in sessions],
        'sealed_result': {'ref': 'precheck-result:' + RESULT_ID, 'file': str(sealed_path),
                          'file_sha256': hashlib.sha256(sealed_bytes).hexdigest(), 'published_at': sealed['published_at']},
        'source': {'discovered': len(sealed['sources']), 'source_media': sum(scope == 'source_media' for scope in scopes.values()),
                   'precheck_runs': run_count, 'fixture_manifest_media': len(media_manifest), 'fixture_media_hash_mismatches': mismatches,
                   'checksum_manifest_sha256': hashlib.sha256((FIXTURE / 'manifests/SHA256SUMS').read_bytes()).hexdigest()},
        'work': {'capabilities': counted(row[0] for row in work), 'status': counted(row[2] for row in work),
                 'embedding_profile': config['embedding_profile'], 'compression_target': config['compression_target'],
                 'representative_methods': counted(group['basis']['representative_method'] for group in groups),
                 'qualifications': counted(code for group in groups for code in group['qualifications']),
                 'representative_comparisons': sum(group['basis']['representative_comparison_count'] for group in groups),
                 'outlier_paths': sum(len(group['outlier_paths']) for group in groups),
                 'max_group_members': max(group['member_count'] for group in groups),
                 'singleton_groups': sum(group['member_count'] == 1 for group in groups)},
        'geo': {'source_coordinate_observations': len(coordinates), 'source_exact_coordinates': len(set(coordinates)),
                'coordinate_producers': dict(coordinate_producers), 'zero_coordinate_source_items': coordinates.count((0, 0)),
                'covered_source_items': len(geo_sources), 'logical_queries': geo['effects']['logical_queries'],
                'provider_requests': sum(attempt['provider_requests'] for attempt in attempts),
                'attempts': counted('/'.join(attempt[key] for key in ('provider', 'operation', 'status')) for attempt in attempts),
                'requests_per_coordinate': counted(per_coordinate.values()),
                'components': counted(component['operation'] + '/' + component['status'] for component in geo['components']),
                'journal_operations': len(geo_rows), 'journal_state': geo_rows[0][1], 'journal_matches_sealed_attempts': True,
                'billable_units': geo['effects']['billable_units'], 'historical_provider_requests': sealed['execution_boundary']['audit']['historical_provider_requests']},
        'agent': {'mcp_tools': counted(event['item']['tool'] for event in mcp),
                  'precheck_read_actions': counted(event['item']['arguments']['action'] for event in reads),
                  'image_view_events': len(image_events), 'image_batches': image_batches,
                  'entry_image_artifacts': len(entry_images), 'boundary_image_artifacts': len(boundary_images),
                  'direct_image_artifacts': len(direct), 'direct_also_in_sheets': len(direct & (entry_images | boundary_images)),
                  'unique_image_artifacts': len(all_images), 'unique_visual_source_items': len(visual_source_refs),
                  'visual_artifact_presentations': len(main_manifest) + len(boundary_manifest) + len(direct),
                  'all_visual_origins_in_source_media': True, 'expanded_anchor_refs': len(anchor_refs),
                  'expanded_source_observations': len(observation_refs), 'expanded_mixed_member_observations': len(member_observation_refs),
                  'resolve_rows': resolved_rows, 'unique_resolved_items': len(resolved), 'unique_resolved_source_media': len(resolved_media),
                  'excluded_member_fetches': excluded_fetches, 'old_output_scope_samples': sorted(set(exposed_old_paths)),
                  'plan_model_requests': len(seen_responses), 'plan_usage': dict(usage),
                  'plan_uncached_input_tokens': usage['input_tokens'] - usage['cached_input_tokens'],
                  'plan_start_line': PLAN_START_LINE, 'plan_start_timestamp': sessions[-1]['rows'][PLAN_START_LINE - 1]['timestamp']},
        'candidate': {'groups': len(candidate['groups']), 'paths': [group['relative_path'] for group in candidate['groups']],
                      'decision_summaries': [note['summary'] for note in candidate['decision_notes']]},
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
