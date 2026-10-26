"""A bounded plan/approval/run/receipt seam. Unsupported artifacts remain receipts.

Context and gates are supplied by server-owned resolvers, never request assertions.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .execution_contract import canonical_context, contained, digest, file_digest


class ClaimExecutionService:
    def __init__(self, root, repository, executor, resolve_specification, preflight, *, clock=None):
        self.root = Path(root).resolve()
        self.repository, self.executor = repository, executor
        self.resolve_specification, self.preflight = resolve_specification, preflight
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.plans = {}

    def context(self, graph_id, edge_id):
        graph = self.repository.get_graph(graph_id)
        if graph is None:
            raise ValueError('graph missing')
        context = canonical_context(self.root, graph, edge_id,
            self.resolve_specification(graph_id, edge_id), self.preflight())
        graph.get_edge(edge_id).execution_context_digest = digest(context)
        self.repository.save_graph(graph)
        return context

    def plan(self, graph_id, edge_id):
        context = self.context(graph_id, edge_id)
        plan_id = str(uuid.uuid4())
        self.plans[plan_id] = {'context': context, 'digest': digest(context), 'approved': False}
        return {'plan_id': plan_id, 'context': context, 'context_digest': digest(context)}

    def approve(self, plan_id, context_digest, *, local_execution_authorized=False):
        plan = self.plans[plan_id]
        if not local_execution_authorized or context_digest != plan['digest']:
            raise ValueError('explicit local approval bound to context required')
        self._recheck(plan)
        plan['approved'] = True
        return {'approved': True, 'context_digest': context_digest}

    def _recheck(self, plan):
        context = plan['context']
        if digest(self.context(context['graph_id'], context['edge_id'])) != plan['digest']:
            raise ValueError('execution context changed since planning')
        policy = json.loads(contained(self.root, '.dogma/trust.json').read_text())
        if policy.get('trusted') is not True or policy.get('allow_local_operations') is not True:
            raise ValueError('explicit workspace trust required')

    def _persist(self, receipt, directory):
        path = contained(self.root, directory / 'receipt.json')
        temporary = path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            stream.write(json.dumps(receipt, sort_keys=True, indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)

    async def execute(self, plan_id, *, timeout_seconds=3600):
        plan = self.plans[plan_id]
        if not plan['approved']:
            raise ValueError('plan approval missing')
        self._recheck(plan)
        plan['approved'] = False  # one approval authorizes exactly one launch
        execution_id = str(uuid.uuid4())
        directory = contained(self.root, '.dogma/executions/' + execution_id)
        directory.mkdir(parents=True, exist_ok=False)
        directory_identity = directory.stat().st_ino
        receipt = {'schema': 1, 'execution_id': execution_id, 'created_at': self.clock(),
                   'status': 'pending', 'context': plan['context'], 'context_digest': plan['digest'],
                   'artifacts': {}, 'measurement': None}
        self._persist(receipt, directory)
        try:
            # Actual NextflowExecutor API supplies the id, status, command and times.
            def observe(executor_receipt):
                receipt['executor'] = executor_receipt
                self._persist(receipt, directory)
            execution = await asyncio.wait_for(self.executor.execute_approved_context(
                plan['context'], directory, execution_id, timeout_seconds=timeout_seconds, observer=observe), timeout_seconds + 5)
            receipt.update(executor=execution, status=execution['status'])
            self._recheck(plan)
            if directory.stat().st_ino != directory_identity:
                raise ValueError('execution output directory was substituted')
            from .transcript_readout import transcript_abundance
            result = transcript_abundance(plan['context'], directory) if execution['status'] == 'completed' and execution.get('exit_code') == 0 else None
            receipt['measurement'] = result
            receipt['readout_status'] = 'observed' if result is not None else 'unsupported_readout'
            artifacts = [directory / 'execution.config', directory / 'process.log']
            reports = directory / 'results' / 'reports'
            artifacts.extend(reports / name for name in ('execution_report.html', 'execution_timeline.html', 'execution_trace.txt', 'pipeline_dag.svg'))
            if result is not None:
                artifacts.append(directory / 'results' / 'salmon' / result['sample_id'] / 'quant.sf')
            # Nextflow work directories contain staged input symlinks and scratch
            # outputs; neither belongs to the durable declared-readout contract.
            for artifact in artifacts:
                if artifact.is_file():
                    contained(directory, artifact)
                    receipt['artifacts'][str(artifact.relative_to(directory))] = file_digest(self.root, artifact)
        except asyncio.CancelledError:
            receipt['status'] = 'cancelled'
            raise
        except asyncio.TimeoutError:
            receipt['status'] = 'timeout'
        except Exception as exc:
            receipt.update(status='failed', measurement=None, error=type(exc).__name__)
            if receipt.get('executor', {}).get('status') == 'completed':
                receipt['readout_error'] = type(exc).__name__
        finally:
            receipt['completed_at'] = self.clock()
            self._persist(receipt, directory)
        if receipt['status'] == 'completed' and receipt.get('measurement') is not None:
            self._recheck(plan)
            from quration.hypothesis.evidence import EvidenceEntry, EvidenceKind, EvidenceDirection
            from quration.hypothesis.provenance import PipelineRunProvenance
            context = plan['context']
            reference = str(directory / 'receipt.json')
            entry = EvidenceEntry(edge_id=context['edge_id'], kind=EvidenceKind.MEASUREMENT,
                direction=EvidenceDirection.INCONCLUSIVE,
                magnitude=json.dumps(receipt['measurement'], sort_keys=True),
                rationale='Observed transcript abundance only; no support/refute verdict.',
                claim_signature=tuple(context['claim_signature']), execution_context_digest=plan['digest'],
                execution_context=context, execution_receipt=reference,
                execution_receipt_hash=file_digest(self.root, reference),
                provenance=PipelineRunProvenance(run_id=execution_id,
                    data_accession=context['specification']['data_accession'],
                    execution_context_digest=plan['digest'], execution_receipt=reference))
            self.repository.add_evidence(context['graph_id'], entry)
        return receipt
