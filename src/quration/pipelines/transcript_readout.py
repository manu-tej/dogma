"""Salmon quant.sf facts only: relative abundance and estimated assigned fragments.

Format: https://salmon.readthedocs.io/en/stable/file_formats.html . This adapter
cannot measure differential expression, causal effects, proteins or phosphorylation.
"""
import csv
import math
import re
from .execution_contract import contained


def transcript_abundance(context, directory):
    spec = context['specification']
    if 'm:salmon' not in {binding.get('method_id') for binding in spec.get('method_bindings', {}).values()}:
        return None
    if spec['readout'] != 'transcript_abundance' or spec['assay'] != 'bulk_rnaseq':
        return None
    if context['claim_signature'][2] != 'has_transcript_abundance':
        return None
    target = context['endpoint_grounding'][1]['grounding']
    source = context['endpoint_grounding'][0]['grounding']
    if target.get('ontology') != 'Ensembl' or source.get('term_id') != spec.get('data_accession'):
        return None
    transcript = target.get('term_id')
    if transcript != spec.get('transcript_id') or not transcript.startswith('ENST'):
        return None
    # One named sample/readout only; no implicit aggregation or contrast testing.
    if not re.fullmatch(r'[A-Za-z0-9_-]+', spec.get('sample_id', '')) or spec.get('contrast') != {'kind': 'single_sample', 'sample_id': spec['sample_id']}:
        return None
    design_path = contained(context['workspace_root'], spec['sample_design'])
    with design_path.open(newline='') as design_stream:
        design = csv.DictReader(design_stream)
        if design.fieldnames != ['sample', 'fastq']:
            raise ValueError('unsupported sample design schema')
        rows = list(design)
        names = [row['sample'] for row in rows]
        if len(set(names)) != len(names) or names != [spec['sample_id']]:
            raise ValueError('sample identity is missing, duplicated or ambiguous')
        reads = str(contained(context['workspace_root'], rows[0]['fastq']))
        if [reads] != [str(contained(context['workspace_root'], path)) for path in spec['dataset']]:
            raise ValueError('sample design does not bind pinned reads')
    path = contained(context['workspace_root'], directory / 'results' / 'salmon' / spec['sample_id'] / 'quant.sf')
    contained(directory, path)
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        if reader.fieldnames != ['Name', 'Length', 'EffectiveLength', 'TPM', 'NumReads']:
            raise ValueError('unexpected Salmon quant.sf schema')
        matched = []
        seen = set()
        for row in reader:
            if None in row or not row['Name'] or row['Name'] in seen:
                raise ValueError('malformed or duplicate transcript row')
            seen.add(row['Name'])
            values = {key: float(row[key]) for key in ('Length', 'EffectiveLength', 'TPM', 'NumReads')}
            if any(not math.isfinite(value) or value < 0 for value in values.values()) or values['Length'] <= 0:
                raise ValueError('invalid transcript abundance value')
            if row['Name'] == transcript:
                matched.append(values)
    if len(matched) != 1:
        raise ValueError('requested transcript missing')
    return {'readout': 'transcript_abundance', 'assay': 'bulk_rnaseq', 'transcript_id': transcript,
            'sample_id': spec['sample_id'], 'TPM': matched[0]['TPM'], 'NumReads': matched[0]['NumReads'],
            'caveats': ['TPM is relative abundance; NumReads is estimated assigned fragments.',
                        'This is no differential-expression or causal-effect test.']}
