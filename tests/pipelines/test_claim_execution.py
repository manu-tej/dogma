import asyncio
import json
from pathlib import Path
import pytest
from quration.hypothesis.graph import CausalGraph, Node, NodeType, Edge, EdgeState, NodePosition
from quration.hypothesis.provenance import OntologyTermProvenance
from quration.hypothesis.store.sqlite_repository import SqliteHypothesisRepository
from quration.pipelines.claim_execution_service import ClaimExecutionService
from quration.pipelines.execution_contract import file_digest
from quration.pipelines.executor import NextflowExecutor
from quration.models.nextflow import NextflowConfig

IMAGE = 'salmon@sha256:' + 'a' * 64
QUANT = 'Name\tLength\tEffectiveLength\tTPM\tNumReads\nENST000001\t1000\t800\t3.5\t12.25\n'


def fixture(tmp_path, *, code=0, artifact=QUANT, mutate=None):
    (tmp_path / '.dogma').mkdir()
    (tmp_path / '.dogma/trust.json').write_text(json.dumps({'trusted': True, 'allow_local_operations': True}))
    (tmp_path / 'reads.fastq').write_text('@read\nA\n+\n!\n')
    (tmp_path / 'samples.csv').write_text('sample,fastq\nsample1,reads.fastq\n')
    (tmp_path / 'main.nf').write_text("params.input = null\nparams.reads = null\nprocess SALMON {\n container '" + IMAGE + "'\n script:\n 'salmon quant'\n}\n")
    repo = SqliteHypothesisRepository(tmp_path / 'evidence.sqlite')
    graph = CausalGraph(id='graph', query='observational', nodes=[
        Node(id='dataset', type=NodeType.OTHER, label='data', grounding=OntologyTermProvenance(ontology='GEO', term_id='fixture-data')),
        Node(id='transcript', type=NodeType.TARGET, label='transcript', grounding=OntologyTermProvenance(ontology='Ensembl', term_id='ENST000001'))],
        edges=[Edge(id='edge', source_id='dataset', target_id='transcript', relation='has_transcript_abundance')])
    repo.save_graph(graph)
    specification = {'readout': 'transcript_abundance', 'assay': 'bulk_rnaseq', 'data_accession': 'fixture-data',
        'transcript_id': 'ENST000001', 'sample_id': 'sample1', 'dataset': ['reads.fastq'], 'sample_design': 'samples.csv',
        'contrast': {'kind': 'single_sample', 'sample_id': 'sample1'}, 'workflow_files': ['main.nf'],
        'pipeline_version': '1.0.0', 'containers': [IMAGE], 'runtime_version': '24.10.0', 'parameters': {},
        'method_bindings': {'SALMON': {'method_id': 'm:salmon', 'code_digest': file_digest(tmp_path, 'main.nf')}}}
    (tmp_path / 'methods.kuzu').write_bytes(b'fake verified method substrate')
    (tmp_path / 'methods.lock.json').write_text('{"schema":1}')
    preflight = {'configured_graph': {'path': str(tmp_path / 'methods.kuzu'), 'ingest_lock': str(tmp_path / 'methods.lock.json')}, 'status': 'evaluable', 'coverage_gaps': [], 'workflow_files': ['main.nf'],
        'method_chain': {'steps': [{'process': 'SALMON', 'method_id': 'm:salmon', 'container': IMAGE}]},
        'verification': {'schema': 1, 'status': 'verified', 'verified': True, 'audit': {'ok': True},
            'graph_hash': 'sha256:' + 'b' * 64, 'expected_graph_hash': 'sha256:' + 'b' * 64}}
    launched = []
    class Process:
        returncode = 0
        async def communicate(self): return (b'nextflow version 24.10.0 build fixture', b'')
        async def wait(self): return code
        def kill(self): pass
    async def process_factory(*command, **kwargs):
        launched.append((command, kwargs))
        if '-version' in command:
            return Process()
        if artifact is not None:
            output = Path(command[command.index('--outdir') + 1]) / 'salmon/sample1'
            output.mkdir(parents=True)
            (output / 'quant.sf').write_text(artifact)
        if mutate: mutate(tmp_path, repo)
        return Process()
    executor = NextflowExecutor(NextflowConfig(work_dir=str(tmp_path / 'work'), output_dir=str(tmp_path / 'outputs')),
        process_factory=process_factory, clock=lambda: '2026-10-02T00:00:00Z')
    service = ClaimExecutionService(tmp_path, repo, executor, lambda *_: specification, lambda: preflight)
    return service, repo, specification, preflight, launched


def run(service):
    plan = service.plan('graph', 'edge')
    service.approve(plan['plan_id'], plan['context_digest'], local_execution_authorized=True)
    return asyncio.run(service.execute(plan['plan_id']))


def test_observed_artifact_receipt_evidence_reopen_and_input_staleness(tmp_path):
    service, repo, spec, preflight, launched = fixture(tmp_path)
    receipt = run(service)
    assert receipt['status'] == 'completed'
    assert receipt['measurement']['TPM'] == 3.5
    assert receipt['measurement']['NumReads'] == 12.25
    assert repo.get_graph('graph').get_edge('edge').state == EdgeState.EXAMINED
    assert repo.get_graph('graph').get_edge('edge').confidence == 0.0
    command, kwargs = launched[-1]
    assert '-C' in command
    assert command[command.index('--input') + 1] == str(tmp_path / 'samples.csv')
    assert command[command.index('--reads') + 1] == str(tmp_path / 'reads.fastq')
    assert kwargs['env']['NXF_VER'] == '24.10.0'
    repo.close()
    reopened = SqliteHypothesisRepository(tmp_path / 'evidence.sqlite')
    assert reopened.get_graph('graph').get_edge('edge').state == EdgeState.EXAMINED
    (tmp_path / 'reads.fastq').write_text('changed data')
    assert reopened.get_graph('graph').get_edge('edge').state == EdgeState.UNTESTED
    assert len(reopened.evidence_for_edge('graph', 'edge')) == 1


@pytest.mark.parametrize('artifact,code', [(None, 0), ('wrong\tschema\n', 0), (QUANT, 1)])
def test_no_measurement_from_missing_wrong_or_failed_artifact(tmp_path, artifact, code):
    service, repo, *_ = fixture(tmp_path, artifact=artifact, code=code)
    receipt = run(service)
    assert receipt['measurement'] is None
    assert repo.get_graph('graph').get_edge('edge').state == EdgeState.UNTESTED
    assert not repo.evidence_for_edge('graph', 'edge')


@pytest.mark.parametrize('change', ['contrast', 'code', 'claim', 'input'])
def test_midrun_change_prevents_attachment(tmp_path, change):
    def mutate(root, repo):
        if change == 'claim':
            graph = repo.get_graph('graph'); graph.edges[0].relation = 'causes'; repo.save_graph(graph)
        elif change == 'code': (root / 'main.nf').write_text('changed workflow')
        elif change == 'input': (root / 'reads.fastq').write_text('changed input')
        else: spec['contrast'] = {'kind': 'DE', 'case': 'x', 'control': 'y'}
    service, repo, spec, *_ = fixture(tmp_path, mutate=mutate)
    receipt = run(service)
    assert receipt['status'] == 'failed' and receipt['measurement'] is None
    assert not repo.evidence_for_edge('graph', 'edge')


def test_approval_and_unknown_step_gates(tmp_path):
    service, repo, spec, preflight, launched = fixture(tmp_path)
    plan = service.plan('graph', 'edge')
    with pytest.raises(ValueError): asyncio.run(service.execute(plan['plan_id']))
    with pytest.raises(ValueError): service.approve(plan['plan_id'], 'wrong', local_execution_authorized=True)
    preflight['coverage_gaps'] = ['unknown step']
    with pytest.raises(ValueError): service.plan('graph', 'edge')
    assert not launched


def test_symlink_input_and_reserved_parameter_refused(tmp_path):
    service, repo, spec, *_ = fixture(tmp_path)
    (tmp_path / 'alias.fastq').symlink_to(tmp_path / 'reads.fastq')
    spec['dataset'] = ['alias.fastq']
    with pytest.raises(ValueError): service.plan('graph', 'edge')
    spec['dataset'] = ['reads.fastq']; spec['parameters'] = {'outdir': '/tmp/elsewhere'}
    with pytest.raises(ValueError): service.plan('graph', 'edge')


@pytest.mark.parametrize('change', ['grounding', 'proposed_test', 'method', 'artifact', 'layout'])
def test_reopen_current_identity_and_artifacts(tmp_path, change):
    from quration.hypothesis.graph import EdgeTest
    service, repo, *_ = fixture(tmp_path)
    receipt = run(service)
    graph = repo.get_graph('graph')
    if change == 'grounding': graph.nodes[1].grounding.term_id = 'ENST999999'
    elif change == 'proposed_test': graph.edges[0].proposed_test = EdgeTest(expected='changed assay')
    elif change == 'method': (tmp_path / 'methods.kuzu').write_bytes(b'changed method content')
    elif change == 'artifact':
        (tmp_path / '.dogma/executions' / receipt['execution_id'] / 'results/salmon/sample1/quant.sf').write_text(QUANT.replace('3.5', '4.5'))
    else: graph.nodes[1].position = NodePosition(x=200, y=100)
    repo.save_graph(graph); repo.close()
    reopened = SqliteHypothesisRepository(tmp_path / 'evidence.sqlite')
    expected = EdgeState.EXAMINED if change == 'layout' else EdgeState.UNTESTED
    assert reopened.get_graph('graph').get_edge('edge').state == expected
    assert len(reopened.evidence_for_edge('graph', 'edge')) == 1


def test_receipt_identity_idempotent_and_conflict_rejected(tmp_path):
    service, repo, *_ = fixture(tmp_path)
    run(service)
    entry = repo.evidence_for_edge('graph', 'edge')[0]
    repo.add_evidence('graph', entry.model_copy(deep=True))
    assert len(repo.evidence_for_edge('graph', 'edge')) == 1
    incompatible = entry.model_copy(deep=True); incompatible.magnitude = 'forged'
    with pytest.raises(ValueError): repo.add_evidence('graph', incompatible)


@pytest.mark.parametrize('design', ['sample,fastq\nforeign,reads.fastq\n',
    'sample,fastq\nsample1,other.fastq\n', 'sample,fastq\nsample1,reads.fastq\nsample1,reads.fastq\n'])
def test_wrong_or_ambiguous_design_has_no_measurement(tmp_path, design):
    service, repo, *_ = fixture(tmp_path)
    (tmp_path / 'samples.csv').write_text(design)
    receipt = run(service)
    assert receipt['measurement'] is None and receipt['status'] == 'failed'
    assert not repo.evidence_for_edge('graph', 'edge')


def test_trust_required_at_approval_and_before_launch(tmp_path):
    service, repo, spec, preflight, launched = fixture(tmp_path)
    plan = service.plan('graph', 'edge')
    (tmp_path / '.dogma/trust.json').write_text('{}')
    with pytest.raises(ValueError): service.approve(plan['plan_id'], plan['context_digest'], local_execution_authorized=True)
    assert not launched


def test_timeout_persists_executor_command_without_measurement(tmp_path):
    service, repo, *_ = fixture(tmp_path)
    class Process:
        killed = False
        returncode = 0
        async def communicate(self): return (b'nextflow version 24.10.0 build fixture', b'')
        async def wait(self):
            if self.killed: return -9
            await asyncio.Event().wait()
        def kill(self): self.killed = True
    async def process_factory(*command, **kwargs): return Process()
    service.executor._process_factory = process_factory
    plan = service.plan('graph', 'edge')
    service.approve(plan['plan_id'], plan['context_digest'], local_execution_authorized=True)
    receipt = asyncio.run(service.execute(plan['plan_id'], timeout_seconds=0.01))
    assert receipt['status'] == 'timeout' and receipt['measurement'] is None
    assert 'run' in receipt['executor']['command']
    assert receipt['executor']['status'] == 'timeout'
    assert not repo.evidence_for_edge('graph', 'edge')


def test_incompatible_causal_claim_retains_receipt_without_measurement(tmp_path):
    service, repo, *_ = fixture(tmp_path)
    graph = repo.get_graph('graph'); graph.edges[0].relation = 'causes'; repo.save_graph(graph)
    receipt = run(service)
    assert receipt['status'] == 'completed' and receipt['readout_status'] == 'unsupported_readout'
    assert receipt['measurement'] is None and not repo.evidence_for_edge('graph', 'edge')


def test_actual_runtime_version_mismatch_prevents_workflow_launch(tmp_path):
    service, repo, spec, preflight, launched = fixture(tmp_path)
    class WrongRuntime:
        returncode = 0
        async def communicate(self): return (b'nextflow version 23.10.0', b'')
        async def wait(self): return 0
        def kill(self): pass
    async def runtime_factory(*command, **kwargs):
        launched.append((command, kwargs)); return WrongRuntime()
    service.executor._process_factory = runtime_factory
    receipt = run(service)
    assert receipt['status'] == 'failed' and receipt['measurement'] is None
    assert len(launched) == 1 and '-version' in launched[0][0]
    assert not repo.evidence_for_edge('graph', 'edge')


def test_valid_measurement_with_normal_staged_work_symlink(tmp_path):
    def stage(root, repo):
        directory = next((root / '.dogma/executions').iterdir())
        work = directory / 'work/ab/task'; work.mkdir(parents=True)
        (work / 'reads.fastq').symlink_to(root / 'reads.fastq')
    service, repo, *_ = fixture(tmp_path, mutate=stage)
    receipt = run(service)
    assert receipt['status'] == 'completed' and receipt['measurement']['TPM'] == 3.5
    assert repo.get_graph('graph').get_edge('edge').state == EdgeState.EXAMINED
    assert not any(path.startswith('work/') for path in receipt['artifacts'])
    assert 'results/salmon/sample1/quant.sf' in receipt['artifacts']


def test_symlink_measurement_is_rejected_even_within_workspace(tmp_path):
    def substitute(root, repo):
        directory = next((root / '.dogma/executions').iterdir())
        artifact = directory / 'results/salmon/sample1/quant.sf'
        foreign = root / 'foreign-quant.sf'; foreign.write_text(QUANT)
        artifact.unlink(); artifact.symlink_to(foreign)
    service, repo, *_ = fixture(tmp_path, mutate=substitute)
    receipt = run(service)
    assert receipt['status'] == 'failed' and receipt['measurement'] is None
    assert not repo.evidence_for_edge('graph', 'edge')


@pytest.mark.parametrize('declaration', ["executor 'awsbatch'", "executor { params.executor }"])
def test_workflow_nonlocal_or_dynamic_executor_refused(tmp_path, declaration):
    service, repo, spec, preflight, launched = fixture(tmp_path)
    workflow = tmp_path / 'main.nf'
    workflow.write_text(workflow.read_text().replace('process SALMON {', 'process SALMON {\n ' + declaration))
    spec['method_bindings']['SALMON']['code_digest'] = file_digest(tmp_path, 'main.nf')
    with pytest.raises(ValueError, match='executor'): service.plan('graph', 'edge')
    assert not launched


def test_local_workflow_directive_and_high_priority_config_selector(tmp_path):
    service, repo, spec, preflight, launched = fixture(tmp_path)
    workflow = tmp_path / 'main.nf'
    workflow.write_text(workflow.read_text().replace('process SALMON {', "process SALMON {\n executor 'local'"))
    spec['method_bindings']['SALMON']['code_digest'] = file_digest(tmp_path, 'main.nf')
    receipt = run(service)
    command = launched[-1][0]
    config = Path(command[command.index('-C') + 1]).read_text()
    assert "withName: '.*' { executor = 'local' }" in config
    assert receipt['status'] == 'completed'


def test_bounded_graceful_and_stubborn_cleanup(tmp_path):
    service, repo, *_ = fixture(tmp_path)
    class Graceful:
        returncode = None
        terminated = False
        killed = False
        def terminate(self): self.terminated = True
        def kill(self): self.killed = True
        async def wait(self): return -15
    graceful = Graceful()
    result = asyncio.run(service.executor._stop_approved_process(graceful, grace_seconds=0.01))
    assert graceful.terminated and not graceful.killed
    assert result == {'controller': 'terminated', 'child_cleanup': 'unverified'}
    class Stubborn(Graceful):
        async def wait(self):
            if self.killed: return -9
            await asyncio.Event().wait()
    stubborn = Stubborn()
    result = asyncio.run(service.executor._stop_approved_process(stubborn, grace_seconds=0.01))
    assert stubborn.terminated and stubborn.killed
    assert result['controller'] == 'killed_after_grace'


def test_cancellation_receipt_preserves_executor_and_no_measurement(tmp_path):
    service, repo, *_ = fixture(tmp_path)
    entered = None
    class Process:
        returncode = None
        stopped = False
        async def communicate(self):
            self.returncode = 0
            return (b'nextflow version 24.10.0', b'')
        async def wait(self):
            if self.stopped: return -15
            entered.set()
            await asyncio.Event().wait()
        def terminate(self): self.stopped = True
        def kill(self): self.stopped = True
    async def process_factory(*command, **kwargs): return Process()
    service.executor._process_factory = process_factory
    plan = service.plan('graph', 'edge')
    service.approve(plan['plan_id'], plan['context_digest'], local_execution_authorized=True)
    async def cancel():
        nonlocal entered
        entered = asyncio.Event()
        task = asyncio.create_task(service.execute(plan['plan_id']))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    asyncio.run(cancel())
    receipt = json.loads(next((tmp_path / '.dogma/executions').glob('*/receipt.json')).read_text())
    assert receipt['status'] == 'cancelled' and receipt['measurement'] is None
    assert receipt['executor']['status'] == 'cancelled'
    assert 'run' in receipt['executor']['command'] and receipt['executor']['completed_at']
    assert receipt['executor']['cleanup']['child_cleanup'] == 'unverified'
    assert not repo.evidence_for_edge('graph', 'edge')


def test_launcher_environment_shared_and_nonsecret_settings_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv('NXF_HOME', str(tmp_path / 'nextflow-cache'))
    monkeypatch.setenv('JAVA_HOME', '/test/server-java')
    service, repo, spec, preflight, launched = fixture(tmp_path)
    receipt = run(service)
    version_environment = launched[0][1]['env']
    execution_environment = launched[-1][1]['env']
    assert version_environment == execution_environment
    assert version_environment['HOME'] and version_environment['NXF_HOME'] == str(tmp_path / 'nextflow-cache')
    assert version_environment['JAVA_HOME'] == '/test/server-java'
    assert receipt['executor']['runtime_settings']['NXF_HOME'] == str(tmp_path / 'nextflow-cache')
    assert 'PATH' not in receipt['executor']['runtime_settings']
