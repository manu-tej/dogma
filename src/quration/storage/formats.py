"""Output formatters for curated metadata."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quration.models.metadata import CuratedDataset, CuratedSample


class OutputFormatter:
    """Formats and saves curated metadata in various formats."""

    @staticmethod
    def to_json(data: CuratedDataset | list[CuratedDataset], pretty: bool = True) -> str:
        """Convert to JSON string.

        Args:
            data: Curated dataset(s)
            pretty: Whether to pretty-print JSON

        Returns:
            JSON string
        """
        if isinstance(data, list):
            data_dict = [d.model_dump(mode="json") for d in data]
        else:
            data_dict = data.model_dump(mode="json")

        indent = 2 if pretty else None
        return json.dumps(data_dict, indent=indent, default=str)

    @staticmethod
    def to_jsonld(data: CuratedDataset | list[CuratedDataset]) -> dict[str, Any]:
        """Convert to JSON-LD format for semantic web compatibility.

        Args:
            data: Curated dataset(s)

        Returns:
            JSON-LD dictionary
        """
        datasets = [data] if isinstance(data, CuratedDataset) else data

        # JSON-LD context
        context = {
            "@vocab": "http://schema.org/",
            "efo": "http://www.ebi.ac.uk/efo/",
            "obo": "http://purl.obolibrary.org/obo/",
            "sio": "http://semanticscience.org/resource/",
        }

        # Convert datasets to JSON-LD
        graph = []

        for dataset in datasets:
            dataset_ld = {
                "@type": "Dataset",
                "@id": f"geo:{dataset.dataset_id}",
                "identifier": dataset.dataset_id,
                "name": dataset.title,
                "description": dataset.description,
                "datePublished": dataset.release_date,
                "numberOfSamples": dataset.sample_count,
                "sample": [],
            }

            # Add samples
            for sample in dataset.samples:
                sample_ld = {
                    "@type": "Sample",
                    "@id": f"geo:{sample.characteristics.sample_id}",
                    "identifier": sample.characteristics.sample_id,
                    "name": sample.characteristics.sample_name,
                }

                # Add ontology terms
                if sample.characteristics.organism and sample.characteristics.organism.iri:
                    sample_ld["organism"] = {
                        "@id": sample.characteristics.organism.iri,
                        "name": sample.characteristics.organism.term,
                    }

                if sample.characteristics.tissue and sample.characteristics.tissue.iri:
                    sample_ld["tissue"] = {
                        "@id": sample.characteristics.tissue.iri,
                        "name": sample.characteristics.tissue.term,
                    }

                if sample.characteristics.disease and sample.characteristics.disease.iri:
                    sample_ld["disease"] = {
                        "@id": sample.characteristics.disease.iri,
                        "name": sample.characteristics.disease.term,
                    }

                dataset_ld["sample"].append(sample_ld)

            graph.append(dataset_ld)

        return {"@context": context, "@graph": graph}

    @staticmethod
    def to_parquet(
        data: CuratedDataset | list[CuratedDataset], output_path: str | Path
    ) -> None:
        """Save to Parquet format for efficient analytics.

        Args:
            data: Curated dataset(s)
            output_path: Output file path
        """
        datasets = [data] if isinstance(data, CuratedDataset) else data

        # Flatten data for tabular format
        rows = []

        for dataset in datasets:
            for sample in dataset.samples:
                char = sample.characteristics
                quality = sample.quality_metrics

                row = {
                    # Dataset info
                    "dataset_id": dataset.dataset_id,
                    "dataset_title": dataset.title,
                    # Sample info
                    "sample_id": char.sample_id,
                    "sample_name": char.sample_name,
                    # Organism
                    "organism_term": char.organism.term if char.organism else None,
                    "organism_id": char.organism.ontology_id if char.organism else None,
                    # Tissue
                    "tissue_term": char.tissue.term if char.tissue else None,
                    "tissue_id": char.tissue.ontology_id if char.tissue else None,
                    # Cell type
                    "cell_type_term": char.cell_type.term if char.cell_type else None,
                    "cell_type_id": char.cell_type.ontology_id if char.cell_type else None,
                    # Disease
                    "disease_term": char.disease.term if char.disease else None,
                    "disease_id": char.disease.ontology_id if char.disease else None,
                    # Clinical
                    "age": char.age,
                    "sex": char.sex,
                    "genotype_term": char.genotype.term if char.genotype else None,
                    "genotype_id": char.genotype.ontology_id if char.genotype else None,
                    "treatment_term": char.treatment.term if char.treatment else None,
                    "treatment_id": char.treatment.ontology_id if char.treatment else None,
                    # Quality
                    "completeness_score": quality.completeness_score,
                    "consistency_score": quality.consistency_score,
                    "ontology_coverage": quality.ontology_coverage,
                    "overall_quality_score": quality.overall_quality_score,
                    "quality_grade": quality.quality_grade,
                    # Metadata
                    "curated_at": sample.curated_at.isoformat(),
                }

                rows.append(row)

        # Create DataFrame and save
        df = pd.DataFrame(rows)
        df.to_parquet(output_path, index=False)

    @staticmethod
    def save_all_formats(
        data: CuratedDataset | list[CuratedDataset],
        output_dir: str | Path,
        prefix: str = "curated",
    ) -> dict[str, Path]:
        """Save curated data in all supported formats.

        Args:
            data: Curated dataset(s)
            output_dir: Output directory
            prefix: Filename prefix

        Returns:
            Dictionary mapping format to output path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_paths = {}

        # JSON
        json_path = output_dir / f"{prefix}_{timestamp}.json"
        with open(json_path, "w") as f:
            f.write(OutputFormatter.to_json(data, pretty=True))
        output_paths["json"] = json_path

        # JSON-LD
        jsonld_path = output_dir / f"{prefix}_{timestamp}.jsonld"
        jsonld_data = OutputFormatter.to_jsonld(data)
        with open(jsonld_path, "w") as f:
            json.dump(jsonld_data, f, indent=2)
        output_paths["jsonld"] = jsonld_path

        # Parquet
        parquet_path = output_dir / f"{prefix}_{timestamp}.parquet"
        OutputFormatter.to_parquet(data, parquet_path)
        output_paths["parquet"] = parquet_path

        return output_paths
