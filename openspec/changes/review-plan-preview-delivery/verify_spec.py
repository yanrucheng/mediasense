"""Validate packet-6 design artifacts only; never invokes a Host or business Tool."""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
ORDER = ['overview', 'preferences', 'working_notes', 'content', 'validation', 'view']


def read(path):
    return json.loads(path.read_text())


def identity(content):
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return 'sha256:' + hashlib.sha256(encoded).hexdigest()


def core(response):
    if 'committed_receipt' in response:
        return response['committed_receipt']
    return {k: v for k, v in response.items() if k != 'view'}


def assignment(org, available):
    if org is None:
        return None
    # This review fixture deliberately uses explicit sets; this is not a
    # second runtime Source Set resolver or a public fixture schema.
    scope = set(org['scope']['source_item_refs'])
    groups = [r for g in org['groups'] for r in g['members']['source_item_refs']]
    others = [r for o in org['other_outcomes'] for r in o['members']['source_item_refs']]
    assigned = groups + others
    assert scope and scope <= available
    assert set(assigned) <= scope and len(assigned) == len(set(assigned))
    if org['kind'] == 'candidate':
        assert set(assigned) == scope
    return {'scope': len(scope), 'organized': len(groups), 'other_outcomes': len(others), 'unassigned': len(scope - set(assigned))}


def main():
    proposal = read(PACKET / 'plan-work.tool.json')
    frozen = read(ROOT / 'docs/spec/contract/frozen-plan/frozen-plan.schema.json')
    mock = read(PACKET / 'interaction.mock.json')
    base = read(PACKET / 'contract-base.json')
    # The retained base checksum describes the pre-implementation interface.
    # Promotion now requires the current contract and release copy to match.
    assert (ROOT / base['active_contract_path']).read_bytes() == (PACKET / 'plan-work.tool.json').read_bytes()
    assert (ROOT / 'src/mediasense/_resources/contracts/plan-work.tool.json').read_bytes() == (PACKET / 'plan-work.tool.json').read_bytes()
    assert hashlib.sha256((ROOT / base['frozen_schema_path']).read_bytes()).hexdigest() == base['frozen_schema_sha256']
    schemas = [proposal['inputSchema'], proposal['outputSchema'], frozen]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources([(s['$id'], Resource.from_contents(s)) for s in schemas])
    validators = [Draft202012Validator(s, registry=registry, format_checker=FormatChecker()) for s in schemas]
    request_validator, response_validator, frozen_validator = validators
    context_validator = Draft202012Validator(
        {'$ref': proposal['inputSchema']['$id'] + '#/$defs/trusted_confirmation'},
        registry=registry, format_checker=FormatChecker(),
    )
    assert proposal['inputSchema']['$defs']['organization_content'] == proposal['outputSchema']['$defs']['organization_content']
    available = {s['source_item_ref'] for s in mock['fixture']['sources']}
    states, previous, stats = {}, {}, Counter()
    for file in (PACKET / 'specs').rglob('spec.md'):
        text = file.read_text()
        headings = re.findall(r'^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements$', text, re.M)
        assert len(headings) == len(set(headings)), 'Repeated delta section can hide requirements: ' + str(file)
        stats['requirement_blocks'] += len(re.findall(r'^### Requirement:', text, re.M))
        stats['scenario_blocks'] += len(re.findall(r'^#### Scenario:', text, re.M))
    for case in mock['cases']:
        request, response = case['request'], case['response']
        expected_shape = case.get('request_shape_valid', True)
        errors = list(request_validator.iter_errors(request))
        assert (not errors) == expected_shape, (case['name'], [e.message for e in errors])
        response_validator.validate(response)
        stats['exchanges'] += 1
        stats['expected_shape_rejections'] += not expected_shape
        for key in ['trusted_context', 'prior_human_acceptance']:
            if key in case:
                context_validator.validate(case[key])
        if case.get('semantic_rejection'):
            try:
                assignment(request['organization_content'], available)
            except AssertionError:
                pass
            else:
                raise AssertionError('Expected fixture semantic rejection: ' + case['name'])
            stats['expected_semantic_rejections'] += 1
        receipt = core(response)
        committed = response['outcome'] == 'ok' or 'committed_receipt' in response
        work = receipt.get('work_ref', request.get('work_ref'))
        if 'replay_of' in case:
            original = previous[case['replay_of']]
            assert request == original['request']
            assert receipt == core(original['response'])
            assert case.get('trusted_context') == original.get('trusted_context')
            stats['replays_verified'] += 1
        elif committed and request['action'] == 'create':
            assert work not in states
            states[work] = {'revision': receipt['revision'], 'state': 'open', 'notes': '', 'preferences': request.get('organization_preferences', {}), 'organization': None}
        elif committed and request['action'] == 'update':
            state = states[work]
            assert state['state'] == 'open' and request['base_revision'] == state['revision']
            assert receipt['revision'] != state['revision']
            for wire, internal in [('working_notes', 'notes'), ('organization_preferences', 'preferences'), ('organization_content', 'organization')]:
                if wire in request:
                    state[internal] = deepcopy(request[wire])
            assignment(state['organization'], available)
            state['revision'] = receipt['revision']
        elif committed and request['action'] == 'seal':
            state = states[work]
            context = case['trusted_context']
            assert state['state'] == 'open' and state['organization']['kind'] == 'candidate'
            assert request['revision'] == state['revision'] == context['reviewed_revision']
            assert context['work_ref'] == work and context['confirmed_content_identity'] == request['candidate_content_identity']
            artifact = receipt['frozen_plan']
            frozen_validator.validate(artifact)
            expected = {k: deepcopy(v) for k, v in state['organization'].items() if k != 'kind'}
            expected.update(contract='mediasense.frozen-plan', plan_ref=mock['fixture']['reserved_plan_refs'][work])
            assert artifact['sealed_content'] == expected
            assert identity(expected) == request['candidate_content_identity'] == artifact['seal']['content_identity']
            assert artifact['seal']['final_confirmation']['confirmed_at'] == context['confirmed_at']
            state['state'] = 'closed'
            assert state['revision'] == receipt['revision']
            stats['frozen_artifacts_verified'] += 1
        elif committed and request['action'] == 'inspect':
            state = states[work]
            assert receipt['revision'] == state['revision'] and receipt['state'] == state['state']
            expected_sections = request.get('sections', ORDER)
            assert response['returned_sections'] == [name for name in ORDER if name in expected_sections]
            assert list(response['sections']) == response['returned_sections']
            assert response['reserved_plan_ref'] == mock['fixture']['reserved_plan_refs'][work]
            sections = response['sections']
            if 'working_notes' in sections:
                assert sections['working_notes'] == state['notes'], case['name']
            if 'preferences' in sections:
                assert sections['preferences'] == state['preferences']
            org = state['organization']
            if 'overview' in sections:
                assert sections['overview']['organization_kind'] == (org['kind'] if org else 'none')
                assert sections['overview']['scope_summary'] == assignment(org, available)
            if 'content' in sections:
                content = sections['content']
                if org is None:
                    assert content is None
                elif content['mode'] == 'complete':
                    assert content['value'] == org
                else:
                    assert content['header'] == {k: org[k] for k in ['kind', 'result_ref', 'scope', 'logical_root']}
                    assert all(item in org[content['collection']] for item in content['items'])
                    assert content['page']['returned'] == len(content['items'])
            is_candidate = bool(org and org['kind'] == 'candidate')
            assert ('candidate_content_identity' in response) == is_candidate
            if 'validation' in sections:
                assert sections['validation']['seal_ready'] == is_candidate
            if is_candidate:
                materialized = {k: v for k, v in org.items() if k != 'kind'}
                materialized.update(contract='mediasense.frozen-plan', plan_ref=response['reserved_plan_ref'])
                assert response['candidate_content_identity'] == identity(materialized)
        elif response['outcome'] == 'error' and work in states:
            assert response.get('revision', states[work]['revision']) == states[work]['revision']
            if response['error']['code'] == 'confirmation_binding_mismatch':
                context = case['trusted_context']
                assert context['reviewed_revision'] != states[work]['revision'] or context['work_ref'] != work
                stats['stale_confirmations_verified'] += 1
        view = response.get('view', response.get('sections', {}).get('view'))
        if view:
            assert view['work_ref'] == work and view['result_ref'] == mock['fixture']['result_ref']
            assert view['revision'] == receipt['revision']
            assert view['current_revision'] == states[work]['revision']
            if view['status'] in ['ready', 'degraded']:
                assert view['revision'] == view['current_revision']
            if view['status'] == 'superseded':
                assert view['revision'] != view['current_revision']
            stats['view_bindings_verified'] += 1
        previous[case['name']] = case
    pages = [previous['candidate_group_page_' + str(i)]['response']['sections']['content'] for i in [1, 2]]
    assert pages[0]['page']['complete'] is False and pages[1]['page']['complete'] is True
    assert pages[0]['page']['next_cursor'] == previous['candidate_group_page_2']['request']['page']['cursor']
    assert pages[0]['items'] + pages[1]['items'] == previous['inspect_complete_candidate']['response']['sections']['content']['value']['groups']
    result = {'status': 'passed', 'scope': 'Static specification/schema/example consistency only; no production Tool, browser, media or installation executed.',
              'schemas_checked': len(schemas), **stats}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
