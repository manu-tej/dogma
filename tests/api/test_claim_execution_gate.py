import asyncio
import json
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from quration.api import server
from quration.pipelines.execution_contract import digest
from quration.hypothesis.graph import CausalGraph, Node, NodeType, Edge


def request(**headers):
    return SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'), headers=headers)


def test_authentication_and_browser_origin_required(monkeypatch):
    monkeypatch.setenv('DOGMA_LOCAL_EXECUTION_TOKEN', 'test-only-authorization-token-123456789')
    with pytest.raises(HTTPException) as error:
        server.require_local_execution_request(request(**{'x-dogma-local-execution': 'explicitly-authorized'}))
    assert error.value.status_code == 403
    headers = {'authorization': 'Bearer test-only-authorization-token-123456789', 'x-dogma-local-execution': 'explicitly-authorized'}
    server.require_local_execution_request(request(**headers))
    with pytest.raises(HTTPException): server.require_local_execution_request(request(origin='https://example.com', **headers))


def test_real_service_bootstrap_reports_preflight_gap_without_sidecar_import(monkeypatch, tmp_path):
    from quration.api import hypothesis_routes
    from quration.hypothesis.store.sqlite_repository import SqliteHypothesisRepository
    monkeypatch.setenv('DOGMA_EXECUTION_WORKSPACE', str(tmp_path))
    for name in ('DOGMA_METHODS_GRAPH_DB', 'METHODS_GRAPH_DB', 'BIOCURSOR_METHODS_GRAPH_DB', 'QURATION_METHODS_GRAPH_DB'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(server, '_claim_execution_service', None)
    repo = SqliteHypothesisRepository(':memory:')
    monkeypatch.setattr(hypothesis_routes, '_repo', repo)
    repo.save_graph(CausalGraph(id='g', query='q', nodes=[Node(id='a', type=NodeType.OTHER, label='a'), Node(id='b', type=NodeType.OTHER, label='b')],
        edges=[Edge(id='e', source_id='a', target_id='b', relation='observational')]))
    directory = tmp_path / '.dogma/execution-specs'; directory.mkdir(parents=True)
    (directory / (digest(['g', 'e'])[7:] + '.json')).write_text('{}')
    service = server.claim_execution_service()  # actual bundled launcher/bootstrap
    report = service.preflight()
    assert report['status'] == 'configuration_gap'
    with pytest.raises(ValueError): service.plan('g', 'e')


def test_direct_pipeline_route_is_closed():
    with pytest.raises(HTTPException) as error:
        asyncio.run(server.execute_pipeline(None))
    assert error.value.status_code == 409
