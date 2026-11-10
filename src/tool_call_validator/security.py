"""Deny-by-default checks using trusted, caller-scoped policy. Never executes tools."""
import argparse
import json
from pathlib import Path
from .core import validate_call, _pairs, _constant, _float, MAX_BYTES


def load_json(raw):
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != {'tools'} or not isinstance(policy['tools'], dict):
        raise ValueError('Policy must contain only a tools mapping')
    for name, rule in policy['tools'].items():
        if not isinstance(name, str) or not name or not isinstance(rule, dict) or set(rule) != {'allowed_values', 'max_values'}:
            raise ValueError('Each tool needs allowed_values and max_values')
        if not isinstance(rule['allowed_values'], dict) or not isinstance(rule['max_values'], dict):
            raise ValueError('Constraints must be objects')
        for field, values in rule['allowed_values'].items():
            if not isinstance(field, str) or not field or not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
                raise ValueError('Allowlisted values must be nonempty lists of strings')
        for field, limit in rule['max_values'].items():
            if not isinstance(field, str) or not field or type(limit) is not int or limit < 0:
                raise ValueError('Maximum constraints must be nonnegative integers')


def check_call(raw, schemas, policy):
    """Policy must come from the authenticated application, NEVER from the model.

    Reports deliberately exclude arguments and schema error messages, which may
    contain sensitive values. Only top-level argument constraints are supported.
    """
    validate_policy(policy)
    result = validate_call(raw, schemas)
    if not result['valid']:
        return {'allowed': False, 'schema_valid': False,
                'reason_codes': ['schema_rejected']}
    call = result['call']
    rule = policy['tools'].get(call['name'])
    if rule is None:
        return {'allowed': False, 'schema_valid': True, 'reason_codes': ['tool_denied']}
    reasons = []
    for field, values in rule['allowed_values'].items():
        value = call['arguments'].get(field)
        if not isinstance(value, str) or value not in values:
            reasons.append('argument_not_allowed')
    for field, maximum in rule['max_values'].items():
        value = call['arguments'].get(field)
        if type(value) is not int or not 0 <= value <= maximum:
            reasons.append('argument_limit_exceeded')
    return {'allowed': not reasons, 'schema_valid': True, 'reason_codes': sorted(set(reasons))}


def main():
    parser = argparse.ArgumentParser(description='Check a tool proposal against trusted caller policy; no execution')
    parser.add_argument('call', type=Path)
    parser.add_argument('--schemas', required=True, type=Path)
    parser.add_argument('--policy', required=True, type=Path)
    args = parser.parse_args()
    try:
        schemas = load_json(args.schemas.read_text(encoding='utf-8'))
        policy = load_json(args.policy.read_text(encoding='utf-8'))
        if not isinstance(schemas, dict):
            raise ValueError('Schemas must be a mapping')
        with args.call.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            validate_policy(policy)
            result = {'allowed': False, 'schema_valid': False, 'reason_codes': ['size_limit']}
        else:
            result = check_call(raw.decode('utf-8'), schemas, policy)
    except Exception:
        print(json.dumps({'allowed': False, 'reason_codes': ['configuration_or_input_error']}))
        return 2
    print(json.dumps(result))
    return 0 if result['allowed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
