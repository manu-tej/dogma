"""MAGE-TAB format exporter.

This module exports curated metadata to MAGE-TAB format (MicroArray Gene Expression Tabular),
which is the standard format for ArrayExpress submissions and functional genomics data.

MAGE-TAB consists of two main files:
- IDF (Investigation Description Format): Investigation-level metadata
- SDRF (Sample Data Relationship Format): Sample-level metadata
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from quration.models.metadata import CuratedDataset


def escape_tsv_value(value: Any) -> str:
    """Escape special characters in TSV values.

    Args:
        value: Value to escape (will be converted to string)

    Returns:
        Escaped string safe for TSV format

    Note:
        Escapes tabs, newlines, and carriage returns to prevent
        malformed TSV files.
    """
    if value is None:
        return ""

    s = str(value)
    # Replace special characters that would break TSV structure
    s = s.replace("\t", "\\t")  # Escape tabs
    s = s.replace("\n", "\\n")  # Escape newlines
    s = s.replace("\r", "\\r")  # Escape carriage returns
    return s


class MAGETABFormatter:
    """Formats curated metadata to MAGE-TAB compliant files.

    MAGE-TAB v1.1 specification: https://www.ebi.ac.uk/arrayexpress/help/magetab_spec.html
    """

    def to_magetab(
        self, dataset: CuratedDataset, output_dir: Path
    ) -> Dict[str, Path]:
        """Export dataset to MAGE-TAB format.

        Args:
            dataset: CuratedDataset to export
            output_dir: Output directory for files

        Returns:
            Dictionary with 'idf' and 'sdrf' file paths

        Example:
            >>> formatter = MAGETABFormatter()
            >>> files = formatter.to_magetab(dataset, Path("./output"))
            >>> print("IDF:", files['idf'])
            >>> print("SDRF:", files['sdrf'])
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate IDF file
        idf_content = self.create_idf(dataset)
        idf_path = output_dir / f"{dataset.dataset_id}.idf.txt"
        try:
            idf_path.write_text(idf_content, encoding="utf-8")
        except IOError as e:
            raise IOError(f"Failed to write IDF file to {idf_path}: {e}") from e

        # Generate SDRF file
        sdrf_content = self.create_sdrf(dataset)
        sdrf_path = output_dir / f"{dataset.dataset_id}.sdrf.txt"
        try:
            sdrf_path.write_text(sdrf_content, encoding="utf-8")
        except IOError as e:
            raise IOError(f"Failed to write SDRF file to {sdrf_path}: {e}") from e

        return {"idf": idf_path, "sdrf": sdrf_path}

    def create_idf(self, dataset: CuratedDataset) -> str:
        """Create IDF (Investigation Description Format) file content.

        Args:
            dataset: CuratedDataset to export

        Returns:
            IDF file content as string
        """
        lines = []

        # Investigation Section
        lines.append(f"Investigation Title\t{escape_tsv_value(dataset.title)}")
        if dataset.description:
            lines.append(f"Experiment Description\t{escape_tsv_value(dataset.description)}")

        # Experimental Design
        lines.append(f"Experimental Design\t{escape_tsv_value(dataset.protocol.experiment_type)}")
        lines.append(f"Experimental Design Term Source REF\tEFO")

        # Experimental Factor (if available)
        # Try to infer from sample characteristics, otherwise use disease/condition
        # For RNA-seq, common factors are disease state, tissue type, or treatment
        factor_name = "disease state"
        factor_type = "disease"
        if hasattr(dataset, 'samples') and dataset.samples:
            # Check if there's variation in characteristics that could be a factor
            diseases = set()
            tissues = set()
            for sample in dataset.samples:
                if sample.characteristics.disease:
                    diseases.add(sample.characteristics.disease.term)
                if sample.characteristics.tissue:
                    tissues.add(sample.characteristics.tissue.term)

            if len(diseases) > 1:
                factor_name = "disease state"
                factor_type = "disease"
            elif len(tissues) > 1:
                factor_name = "tissue"
                factor_type = "organism part"
            # Otherwise keep defaults

        lines.append(f"Experimental Factor Name\t{escape_tsv_value(factor_name)}")
        lines.append(f"Experimental Factor Type\t{escape_tsv_value(factor_type)}")

        # Person/Contact Information
        if dataset.publication and dataset.publication.authors:
            # Use first author
            author = dataset.publication.authors[0]
            # Try to split name
            parts = author.split()
            if len(parts) >= 2:
                lines.append(f"Person Last Name\t{escape_tsv_value(parts[-1])}")
                lines.append(f"Person First Name\t{escape_tsv_value(' '.join(parts[:-1]))}")
            else:
                lines.append(f"Person Last Name\t{escape_tsv_value(author)}")
                lines.append("Person First Name\t")
        else:
            lines.append("Person Last Name\t")
            lines.append("Person First Name\t")

        lines.append("Person Mid Initials\t")
        lines.append("Person Email\t")
        lines.append("Person Affiliation\t")
        lines.append("Person Roles\tinvestigator")

        # Publication Information
        if dataset.publication:
            if dataset.publication.title:
                lines.append(f"Publication Title\t{escape_tsv_value(dataset.publication.title)}")
            if dataset.publication.authors:
                authors_str = "; ".join(dataset.publication.authors)
                lines.append(f"Publication Author List\t{escape_tsv_value(authors_str)}")
            if dataset.publication.pmid:
                lines.append(f"PubMed ID\t{escape_tsv_value(dataset.publication.pmid)}")
            if dataset.publication.doi:
                lines.append(f"Publication DOI\t{escape_tsv_value(dataset.publication.doi)}")
        else:
            lines.append("Publication Title\t")
            lines.append("Publication Author List\t")
            lines.append("PubMed ID\t")
            lines.append("Publication DOI\t")

        lines.append("Publication Status\tpublished")

        # Protocol Information
        lines.append("Protocol Name\tgrowth protocol\textraction protocol\tlibrary construction protocol\tsequencing protocol")
        lines.append("Protocol Type\tgrowth protocol\tnucleic acid extraction protocol\tnucleic acid library construction protocol\tnucleic acid sequencing protocol")

        # Protocol descriptions
        extraction = escape_tsv_value(dataset.protocol.extraction_protocol or "Not specified")
        library = escape_tsv_value(dataset.protocol.library_construction_protocol or "Not specified")
        sequencing = escape_tsv_value(dataset.protocol.sequencing_protocol or "Not specified")
        lines.append(f"Protocol Description\tSample growth and treatment\t{extraction}\t{library}\t{sequencing}")

        # Technology Information
        lines.append(f"Technology Type\tsequencing assay")
        lines.append(f"Technology Type Term Source REF\tEFO")

        # SDRF File Reference
        lines.append(f"SDRF File\t{dataset.dataset_id}.sdrf.txt")

        # Term Source Information
        lines.append("Term Source Name\tEFO\tUBERON\tCL\tMONDO\tNCBITaxon")
        lines.append("Term Source File\thttp://www.ebi.ac.uk/efo/\thttp://purl.obolibrary.org/obo/uberon.owl\thttp://purl.obolibrary.org/obo/cl.owl\thttp://purl.obolibrary.org/obo/mondo.owl\thttp://purl.obolibrary.org/obo/ncbitaxon.owl")
        lines.append("Term Source Version\t")

        return "\n".join(lines)

    def create_sdrf(self, dataset: CuratedDataset) -> str:
        """Create SDRF (Sample Data Relationship Format) file content.

        Args:
            dataset: CuratedDataset to export

        Returns:
            SDRF file content as tab-separated string
        """
        # SDRF is a tab-separated table with specific column structure
        # We'll build it row by row

        # Header row - Updated for RNA-seq (not microarray)
        headers = [
            "Source Name",
            "Characteristics[organism]",
            "Term Source REF",
            "Characteristics[tissue]",
            "Term Source REF",
            "Characteristics[cell type]",
            "Term Source REF",
            "Characteristics[disease]",
            "Term Source REF",
            "Characteristics[age]",
            "Characteristics[sex]",
            "Protocol REF",
            "Extract Name",
            "Protocol REF",
            "Assay Name",
            "Technology Type",
            "Raw Data File",
            "Comment[FASTQ_URI]",
        ]

        rows = [headers]

        # Data rows - one per sample
        for sample in dataset.samples:
            char = sample.characteristics

            # Determine if paired-end and generate appropriate file names
            # Check library layout from protocol if available
            is_paired = False
            if hasattr(dataset.protocol, 'library_layout'):
                is_paired = dataset.protocol.library_layout and 'PAIRED' in str(dataset.protocol.library_layout).upper()

            # Generate file name(s) for raw data
            if is_paired:
                raw_data_file = f"{char.sample_id}_1.fastq.gz;{char.sample_id}_2.fastq.gz"
            else:
                raw_data_file = f"{char.sample_id}.fastq.gz"

            row = [
                # Source Name
                escape_tsv_value(char.sample_name or char.sample_id),
                # Organism
                escape_tsv_value(char.organism.term if char.organism else ""),
                escape_tsv_value(char.organism.ontology_name if char.organism else ""),
                # Tissue
                escape_tsv_value(char.tissue.term if char.tissue else ""),
                escape_tsv_value(char.tissue.ontology_name if char.tissue else ""),
                # Cell Type
                escape_tsv_value(char.cell_type.term if char.cell_type else ""),
                escape_tsv_value(char.cell_type.ontology_name if char.cell_type else ""),
                # Disease
                escape_tsv_value(char.disease.term if char.disease else ""),
                escape_tsv_value(char.disease.ontology_name if char.disease else ""),
                # Age
                escape_tsv_value(char.age or ""),
                # Sex
                escape_tsv_value(char.sex or ""),
                # Protocol REF (extraction)
                "extraction protocol",
                # Extract Name
                escape_tsv_value(f"{char.sample_id}_extract"),
                # Protocol REF (library construction + sequencing combined for RNA-seq)
                "library construction protocol",
                # Assay Name
                escape_tsv_value(f"{char.sample_id}_assay"),
                # Technology Type
                escape_tsv_value(str(dataset.protocol.experiment_type)),
                # Raw Data File (handles paired-end)
                escape_tsv_value(raw_data_file),
                # Comment[FASTQ_URI] - URI to raw data if available
                "",
            ]

            rows.append(row)

        # Convert to tab-separated format
        sdrf_lines = ["\t".join(row) for row in rows]
        return "\n".join(sdrf_lines)

    def validate_magetab(
        self, idf_path: Path, sdrf_path: Path
    ) -> List[str]:
        """Validate MAGE-TAB files.

        Args:
            idf_path: Path to IDF file
            sdrf_path: Path to SDRF file

        Returns:
            List of validation errors (empty if valid)

        Note:
            Basic validation only. For full validation, use external tools like
            the ArrayExpress MAGE-TAB validator.
        """
        errors = []

        # Check files exist
        if not idf_path.exists():
            errors.append(f"IDF file not found: {idf_path}")
        if not sdrf_path.exists():
            errors.append(f"SDRF file not found: {sdrf_path}")

        if errors:
            return errors

        # Basic IDF validation
        idf_content = idf_path.read_text()
        required_idf_fields = [
            "Investigation Title",
            "Experimental Design",
            "SDRF File",
        ]
        for field in required_idf_fields:
            if field not in idf_content:
                errors.append(f"Missing required IDF field: {field}")

        # Basic SDRF validation
        sdrf_content = sdrf_path.read_text()
        sdrf_lines = sdrf_content.split("\n")
        if len(sdrf_lines) < 2:
            errors.append("SDRF file must have at least header and one data row")
        else:
            header = sdrf_lines[0]
            if "Source Name" not in header:
                errors.append("SDRF missing required 'Source Name' column")

        return errors


def export_to_magetab(
    dataset: CuratedDataset, output_dir: Path
) -> Dict[str, Path]:
    """Convenience function to export dataset to MAGE-TAB.

    Args:
        dataset: CuratedDataset to export
        output_dir: Output directory

    Returns:
        Dictionary with file paths

    Example:
        >>> files = export_to_magetab(my_dataset, Path("./output"))
        >>> print(files['idf'], files['sdrf'])
    """
    formatter = MAGETABFormatter()
    return formatter.to_magetab(dataset, output_dir)
