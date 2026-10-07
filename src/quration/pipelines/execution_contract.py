"""Canonical, content-bound context for explicitly approved local executions."""
import hashlib
import json
import re
import os
from pathlib import Path


def digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def contained(root, path):
    root = Path(root).resolve()
    path = Path(path)
    candidate = path if path.is_absolute() else root / path
    # Replacing a pinned path with a symlink changes identity even within root.
    if any(part.is_symlink() for part in [candidate, *candidate.parents] if part != root.parent):
        raise ValueError('symlink paths are not accepted for execution')
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError('path escapes workspace or names workspace root')
    return resolved


def file_digest(root, path):
    resolved = contained(root, path)
    if not resolved.is_file():
        raise ValueError('required pinned file missing')
    return 'sha256:' + hashlib.sha256(resolved.read_bytes()).hexdigest()


def runtime_environment(runtime_version):
    values = {'NXF_VER': runtime_version, 'PATH': os.environ.get('PATH', ''),
              'HOME': os.environ.get('HOME') or str(Path.home())}
    for name in ('NXF_HOME', 'JAVA_HOME', 'NXF_JAVA_HOME'):
        if os.environ.get(name):
            values[name] = os.environ[name]
    return values


def canonical_context(root, graph, edge_id, specification, preflight):
    specification = json.loads(json.dumps(specification, sort_keys=True, allow_nan=False))
    edge = graph.get_edge(edge_id)
    if edge is None or edge.pending:
        raise ValueError('approved graph edge missing')
    required = ('readout', 'assay', 'dataset', 'sample_design', 'contrast', 'workflow_files',
                'pipeline_version', 'containers', 'runtime_version', 'parameters')
    if any(not specification.get(key) for key in required if key != 'parameters'):
        raise ValueError('required execution pins missing')
    if not re.fullmatch(r'(?:v?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?|[0-9a-f]{40})', specification['pipeline_version']):
        raise ValueError('exact pipeline version required')
    if not re.fullmatch(r'\d+\.\d+\.\d+', specification['runtime_version']):
        raise ValueError('exact Nextflow runtime version required')
    if any(not re.fullmatch(r'.+@sha256:[0-9a-f]{64}', image) for image in specification['containers']):
        raise ValueError('container digest pin required')
    if preflight.get('status') != 'evaluable' or preflight.get('coverage_gaps'):
        raise ValueError('all preflight gates must pass')
    configured = preflight.get('configured_graph', {})
    method_database = Path(configured.get('path', '')).resolve()
    if method_database.suffix != '.kuzu' or not method_database.is_file() or Path(configured.get('path', '')).is_symlink():
        raise ValueError('a regular verified methods graph database is required')
    method_binding = {'path': str(method_database), 'sha256': 'sha256:' + hashlib.sha256(method_database.read_bytes()).hexdigest()}
    if not configured.get('ingest_lock'):
        raise ValueError('verified methods graph lock is required')
    if configured.get('ingest_lock'):
        lock = Path(configured['ingest_lock']).resolve()
        if lock.name not in ('ingest.lock.json', 'methods.lock.json') or not lock.is_file() or Path(configured['ingest_lock']).is_symlink():
            raise ValueError('verified method lock binding missing')
        method_binding['lock'] = str(lock)
        method_binding['lock_hash'] = 'sha256:' + hashlib.sha256(lock.read_bytes()).hexdigest()
    verification = preflight.get('verification') or {}
    if (verification.get('status') != 'verified' or verification.get('verified') is not True
        or type(verification.get('schema')) is not int or verification['schema'] != 1
        or not re.fullmatch(r'sha256:[0-9a-f]{64}', verification.get('graph_hash', ''))
        or verification.get('graph_hash') != verification.get('expected_graph_hash')
        or not isinstance(verification.get('audit'), dict) or verification['audit'].get('ok') is not True):
        raise ValueError('verified methods graph required')
    if len(specification['workflow_files']) != 1:
        raise ValueError('only a complete single-file workflow is currently supported')
    workflow_text = contained(root, specification['workflow_files'][0]).read_text()
    if re.search(r'\b(include|plugin|module)\b', workflow_text):
        raise ValueError('included or dynamic workflow code is not bound')
    executor_lines = [line.strip() for line in workflow_text.splitlines() if re.search(r'\bexecutor\b', line) and not line.lstrip().startswith('//')]
    if any(not re.fullmatch(r"executor\s*(?:=\s*)?(['\"])local\1\s*;?", line) for line in executor_lines):
        raise ValueError('nonlocal or dynamic workflow executor overrides are unsupported')
    if any(image not in workflow_text for image in specification['containers']):
        raise ValueError('container pins must bind the actual workflow code')
    reserved = {'outdir', 'workdir', 'work-dir', 'input', 'reads', 'resume', 'stub-run'}
    if any(key.lstrip('-') in reserved or not re.fullmatch(r'(?:--)?[A-Za-z][A-Za-z0-9_]*', key) for key in specification['parameters']):
        raise ValueError('reserved or invalid execution parameter')
    if 'params.input' not in workflow_text or 'params.reads' not in workflow_text:
        raise ValueError('workflow must consume explicitly bound sample design and reads')
    if '-stub-run' in workflow_text or '-dry-run' in workflow_text:
        raise ValueError('stub or dry execution is not a measurement')
    if sorted(specification['workflow_files']) != sorted(preflight.get('workflow_files', [])):
        raise ValueError('preflight workflow does not match pinned workflow')
    bindings = specification.get('method_bindings', {})
    steps = preflight.get('method_chain', {}).get('steps', [])
    if not steps or set(bindings) != {step['process'] for step in steps}:
        raise ValueError('complete workflow method binding required')
    code_digest = file_digest(root, specification['workflow_files'][0])
    if any(step.get('container') not in specification['containers'] for step in steps):
        raise ValueError('every workflow process must use a pinned declared container')
    if any(bindings[step['process']] != {'method_id': step['method_id'], 'code_digest': code_digest} for step in steps):
        raise ValueError('method binding does not match pinned code and verified chain')
    files = list(specification['dataset']) + [specification['sample_design']] + list(specification['workflow_files'])
    if specification.get('_specification_file'):
        files.append(specification['_specification_file'])
    pins = {str(contained(root, path).relative_to(Path(root).resolve())): file_digest(root, path) for path in files}
    if any(graph.get_node(node) is None or graph.get_node(node).grounding is None for node in (edge.source_id, edge.target_id)):
        raise ValueError('resolved biological endpoints required')
    endpoint_grounding = [graph.get_node(node).model_dump(mode='json') for node in (edge.source_id, edge.target_id)]
    # UI coordinates and labels do not bind a scientific execution; grounding does.
    endpoint_grounding = [{k: v for k, v in item.items() if k in ('id', 'grounding', 'type')} for item in endpoint_grounding]
    return {'schema': 1, 'graph_id': graph.id, 'edge_id': edge.id,
            'claim_signature': [edge.source_id, edge.target_id, edge.relation],
            'proposed_test': edge.proposed_test.model_dump(mode='json') if edge.proposed_test else None,
            'workspace_root': str(Path(root).resolve()),
            'endpoint_grounding': endpoint_grounding, 'specification': specification,
            'file_pins': pins, 'methods_graph_hash': verification['graph_hash'],
            'preflight_digest': digest(preflight), 'methods_graph_binding': method_binding,
            'runtime_environment': runtime_environment(specification['runtime_version'])}
