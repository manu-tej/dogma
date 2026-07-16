"""ISA-TAB format exporter.

This module exports curated metadata to ISA-TAB format (Investigation/Study/Assay Tabular),
which is a general purpose framework for multi-omics metadata.

ISA-TAB consists of three file types:
- Investigation (i_*.txt): Investigation-level metadata
- Study (s_*.txt): Study design and sample characteristics
- Assay (a_*.txt): Assay measurements and data files
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


class ISATABFormatter:
    """Formats curated metadata to ISA-TAB compliant files.

    ISA-TAB v1.0 specification: https://isa-specs.readthedocs.io/en/latest/isatab.html
    """

    def to_isatab(
        self, dataset: CuratedDataset, output_dir: Path
    ) -> Dict[str, Path]:
        """Export dataset to ISA-TAB format.

        Args:
            dataset: CuratedDataset to export
            output_dir: Output directory for files

        Returns:
            Dictionary with 'investigation', 'study', and 'assay' file paths

        Example:
            >>> formatter = ISATABFormatter()
            >>> files = formatter.to_isatab(dataset, Path("./output"))
            >>> print("Investigation:", files['investigation'])
            >>> print("Study:", files['study'])
            >>> print("Assay:", files['assay'])
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate Investigation file
        investigation_content = self.create_investigation(dataset)
        investigation_path = output_dir / f"i_{dataset.dataset_id}.txt"
        try:
            investigation_path.write_text(investigation_content, encoding="utf-8")
        except IOError as e:
            raise IOError(f"Failed to write Investigation file to {investigation_path}: {e}") from e

        # Generate Study file
        study_content = self.create_study(dataset)
        study_path = output_dir / f"s_{dataset.dataset_id}.txt"
        try:
            study_path.write_text(study_content, encoding="utf-8")
        except IOError as e:
            raise IOError(f"Failed to write Study file to {study_path}: {e}") from e

        # Generate Assay file
        assay_content = self.create_assay(dataset)
        assay_path = output_dir / f"a_{dataset.dataset_id}.txt"
        try:
            assay_path.write_text(assay_content, encoding="utf-8")
        except IOError as e:
            raise IOError(f"Failed to write Assay file to {assay_path}: {e}") from e

        return {
            "investigation": investigation_path,
            "study": study_path,
            "assay": assay_path,
        }

    def create_investigation(self, dataset: CuratedDataset) -> str:
        """Create Investigation file content.

        Args:
            dataset: CuratedDataset to export

        Returns:
            Investigation file content
        """
        lines = []

        # ONTOLOGY SOURCE REFERENCE Section
        lines.append("ONTOLOGY SOURCE REFERENCE")
        lines.append("Term Source Name\tEFO\tUBERON\tCL\tMONDO\tNCBITaxon")
        lines.append("Term Source File\thttp://www.ebi.ac.uk/efo/\thttp://purl.obolibrary.org/obo/uberon.owl\thttp://purl.obolibrary.org/obo/cl.owl\thttp://purl.obolibrary.org/obo/mondo.owl\thttp://purl.obolibrary.org/obo/ncbitaxon.owl")
        lines.append("Term Source Version\t\t\t\t\t")
        lines.append("Term Source Description\tExperimental Factor Ontology\tUberon anatomy ontology\tCell Ontology\tMonarch Disease Ontology\tNCBI Taxonomy")

        # INVESTIGATION Section
        lines.append("INVESTIGATION")
        lines.append(f"Investigation Identifier\t{escape_tsv_value(dataset.dataset_id)}")
        lines.append(f"Investigation Title\t{escape_tsv_value(dataset.title)}")
        if dataset.description:
            lines.append(f"Investigation Description\t{escape_tsv_value(dataset.description)}")
        else:
            lines.append("Investigation Description\t")
        lines.append(f"Investigation Submission Date\t{escape_tsv_value(dataset.submission_date or '')}")
        lines.append(f"Investigation Public Release Date\t{escape_tsv_value(dataset.release_date or '')}")

        # INVESTIGATION PUBLICATIONS
        lines.append("INVESTIGATION PUBLICATIONS")
        if dataset.publication and dataset.publication.pmid:
            lines.append(f"Investigation PubMed ID\t{escape_tsv_value(dataset.publication.pmid)}")
            lines.append(f"Investigation Publication DOI\t{escape_tsv_value(dataset.publication.doi or '')}")
            authors = "; ".join(dataset.publication.authors) if dataset.publication.authors else ""
            lines.append(f"Investigation Publication Author List\t{escape_tsv_value(authors)}")
            lines.append(f"Investigation Publication Title\t{escape_tsv_value(dataset.publication.title or '')}")
            lines.append("Investigation Publication Status\tpublished")
            lines.append("Investigation Publication Status Term Accession Number\t")
            lines.append("Investigation Publication Status Term Source REF\t")
        else:
            lines.append("Investigation PubMed ID\t")
            lines.append("Investigation Publication DOI\t")
            lines.append("Investigation Publication Author List\t")
            lines.append("Investigation Publication Title\t")
            lines.append("Investigation Publication Status\t")
            lines.append("Investigation Publication Status Term Accession Number\t")
            lines.append("Investigation Publication Status Term Source REF\t")

        # INVESTIGATION CONTACTS
        lines.append("INVESTIGATION CONTACTS")
        if dataset.publication and dataset.publication.authors:
            # Use first author as contact
            author = dataset.publication.authors[0]
            parts = author.split()
            if len(parts) >= 2:
                lines.append(f"Investigation Person Last Name\t{escape_tsv_value(parts[-1])}")
                lines.append(f"Investigation Person First Name\t{escape_tsv_value(' '.join(parts[:-1]))}")
            else:
                lines.append(f"Investigation Person Last Name\t{escape_tsv_value(author)}")
                lines.append("Investigation Person First Name\t")
        else:
            lines.append("Investigation Person Last Name\t")
            lines.append("Investigation Person First Name\t")
        lines.append("Investigation Person Mid Initials\t")
        lines.append("Investigation Person Email\t")
        lines.append("Investigation Person Phone\t")
        lines.append("Investigation Person Fax\t")
        lines.append("Investigation Person Address\t")
        lines.append("Investigation Person Affiliation\t")
        lines.append("Investigation Person Roles\tprincipal investigator")
        lines.append("Investigation Person Roles Term Accession Number\t")
        lines.append("Investigation Person Roles Term Source REF\t")

        # STUDY Section
        lines.append("STUDY")
        lines.append(f"Study Identifier\t{escape_tsv_value(dataset.dataset_id)}")
        lines.append(f"Study Title\t{escape_tsv_value(dataset.title)}")
        lines.append(f"Study Description\t{escape_tsv_value(dataset.description or '')}")
        lines.append(f"Study Submission Date\t{escape_tsv_value(dataset.submission_date or '')}")
        lines.append(f"Study Public Release Date\t{escape_tsv_value(dataset.release_date or '')}")
        lines.append(f"Study File Name\ts_{escape_tsv_value(dataset.dataset_id)}.txt")

        # STUDY DESIGN DESCRIPTORS
        lines.append("STUDY DESIGN DESCRIPTORS")
        lines.append(f"Study Design Type\t{escape_tsv_value(dataset.protocol.experiment_type)}")
        lines.append("Study Design Type Term Accession Number\t")
        lines.append("Study Design Type Term Source REF\tEFO")

        # STUDY PUBLICATIONS (same as investigation)
        lines.append("STUDY PUBLICATIONS")
        lines.append("Study PubMed ID\t")
        lines.append("Study Publication DOI\t")
        lines.append("Study Publication Author List\t")
        lines.append("Study Publication Title\t")
        lines.append("Study Publication Status\t")
        lines.append("Study Publication Status Term Accession Number\t")
        lines.append("Study Publication Status Term Source REF\t")

        # STUDY FACTORS
        # Try to infer from sample characteristics, otherwise use disease/condition
        # For RNA-seq, common factors are disease state, tissue type, or treatment
        lines.append("STUDY FACTORS")
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

        lines.append(f"Study Factor Name\t{escape_tsv_value(factor_name)}")
        lines.append(f"Study Factor Type\t{escape_tsv_value(factor_type)}")
        lines.append("Study Factor Type Term Accession Number\t")
        lines.append("Study Factor Type Term Source REF\t")

        # STUDY ASSAYS
        lines.append("STUDY ASSAYS")
        lines.append(f"Study Assay File Name\ta_{escape_tsv_value(dataset.dataset_id)}.txt")
        lines.append(f"Study Assay Measurement Type\t{escape_tsv_value(dataset.protocol.library_strategy)}")
        lines.append("Study Assay Measurement Type Term Accession Number\t")
        lines.append("Study Assay Measurement Type Term Source REF\tEFO")
        lines.append(f"Study Assay Technology Type\tsequencing")
        lines.append("Study Assay Technology Type Term Accession Number\t")
        lines.append("Study Assay Technology Type Term Source REF\tEFO")
        lines.append(f"Study Assay Technology Platform\t{escape_tsv_value(dataset.platform.platform_type)}")

        # STUDY PROTOCOLS
        lines.append("STUDY PROTOCOLS")
        protocols = ["growth protocol", "extraction protocol", "library construction protocol", "sequencing protocol"]
        lines.append(f"Study Protocol Name\t{chr(9).join(protocols)}")
        lines.append("Study Protocol Type\tgrowth protocol\tnucleic acid extraction protocol\tnucleic acid library construction protocol\tnucleic acid sequencing protocol")
        lines.append("Study Protocol Type Term Accession Number\t\t\t\t")
        lines.append("Study Protocol Type Term Source REF\t\t\t\t")

        extraction = escape_tsv_value(dataset.protocol.extraction_protocol or "Not specified")
        library = escape_tsv_value(dataset.protocol.library_construction_protocol or "Not specified")
        sequencing = escape_tsv_value(dataset.protocol.sequencing_protocol or "Not specified")
        lines.append(f"Study Protocol Description\tSample growth and treatment\t{extraction}\t{library}\t{sequencing}")
        lines.append("Study Protocol URI\t\t\t\t")
        lines.append("Study Protocol Version\t\t\t\t")
        lines.append("Study Protocol Parameters Name\t\t\t\t")
        lines.append("Study Protocol Parameters Name Term Accession Number\t\t\t\t")
        lines.append("Study Protocol Parameters Name Term Source REF\t\t\t\t")
        lines.append("Study Protocol Components Name\t\t\t\t")
        lines.append("Study Protocol Components Type\t\t\t\t")
        lines.append("Study Protocol Components Type Term Accession Number\t\t\t\t")
        lines.append("Study Protocol Components Type Term Source REF\t\t\t\t")

        # STUDY CONTACTS
        lines.append("STUDY CONTACTS")
        lines.append("Study Person Last Name\t")
        lines.append("Study Person First Name\t")
        lines.append("Study Person Mid Initials\t")
        lines.append("Study Person Email\t")
        lines.append("Study Person Phone\t")
        lines.append("Study Person Fax\t")
        lines.append("Study Person Address\t")
        lines.append("Study Person Affiliation\t")
        lines.append("Study Person Roles\t")
        lines.append("Study Person Roles Term Accession Number\t")
        lines.append("Study Person Roles Term Source REF\t")

        return "\n".join(lines)

    def create_study(self, dataset: CuratedDataset) -> str:
        """Create Study file content.

        Args:
            dataset: CuratedDataset to export

        Returns:
            Study file content (tab-separated)
        """
        # Study file is tab-separated with specific columns
        headers = [
            "Source Name",
            "Characteristics[organism]",
            "Term Source REF",
            "Term Accession Number",
            "Characteristics[tissue]",
            "Term Source REF",
            "Term Accession Number",
            "Characteristics[cell type]",
            "Term Source REF",
            "Term Accession Number",
            "Characteristics[disease]",
            "Term Source REF",
            "Term Accession Number",
            "Protocol REF",
            "Sample Name",
        ]

        rows = [headers]

        # One row per sample
        for sample in dataset.samples:
            char = sample.characteristics

            # Helper function to safely get ontology ID
            def get_ontology_id(ont_obj):
                """Get full ontology ID (e.g., 'NCBITaxon:9606') from ontology object."""
                if not ont_obj:
                    return ""
                # If ontology_id exists, return it (it should already be in format like 'NCBITaxon:9606')
                if hasattr(ont_obj, 'ontology_id') and ont_obj.ontology_id:
                    return ont_obj.ontology_id
                # Otherwise try to construct from ontology_name and accession
                if hasattr(ont_obj, 'ontology_name') and hasattr(ont_obj, 'accession'):
                    if ont_obj.ontology_name and ont_obj.accession:
                        return f"{ont_obj.ontology_name}:{ont_obj.accession}"
                return ""

            row = [
                escape_tsv_value(char.sample_name or char.sample_id),
                # Organism
                escape_tsv_value(char.organism.term if char.organism else ""),
                escape_tsv_value(char.organism.ontology_name if char.organism else ""),
                escape_tsv_value(get_ontology_id(char.organism)),
                # Tissue
                escape_tsv_value(char.tissue.term if char.tissue else ""),
                escape_tsv_value(char.tissue.ontology_name if char.tissue else ""),
                escape_tsv_value(get_ontology_id(char.tissue)),
                # Cell type
                escape_tsv_value(char.cell_type.term if char.cell_type else ""),
                escape_tsv_value(char.cell_type.ontology_name if char.cell_type else ""),
                escape_tsv_value(get_ontology_id(char.cell_type)),
                # Disease
                escape_tsv_value(char.disease.term if char.disease else ""),
                escape_tsv_value(char.disease.ontology_name if char.disease else ""),
                escape_tsv_value(get_ontology_id(char.disease)),
                # Protocol
                "extraction protocol",
                # Sample Name
                escape_tsv_value(char.sample_id),
            ]

            rows.append(row)

        study_lines = ["\t".join(row) for row in rows]
        return "\n".join(study_lines)

    def create_assay(self, dataset: CuratedDataset) -> str:
        """Create Assay file content.

        Args:
            dataset: CuratedDataset to export

        Returns:
            Assay file content (tab-separated)
        """
        # Assay file is tab-separated with specific columns
        headers = [
            "Sample Name",
            "Protocol REF",
            "Extract Name",
            "Protocol REF",
            "Labeled Extract Name",
            "Label",
            "Protocol REF",
            "Assay Name",
            "Technology Type",
            "Raw Data File",
            "Derived Data File",
        ]

        rows = [headers]

        # One row per sample
        for sample in dataset.samples:
            char = sample.characteristics

            row = [
                escape_tsv_value(char.sample_id),
                # Library construction
                "library construction protocol",
                escape_tsv_value(f"{char.sample_id}_extract"),
                # Labeling (if applicable)
                "",  # No labeling protocol for RNA-seq
                "",  # No labeled extract
                "",  # No label
                # Sequencing
                "sequencing protocol",
                escape_tsv_value(f"{char.sample_id}_assay"),
                escape_tsv_value(str(dataset.protocol.experiment_type)),
                # Data files
                escape_tsv_value(f"{char.sample_id}.fastq.gz"),
                escape_tsv_value(f"{char.sample_id}_processed.txt"),
            ]

            rows.append(row)

        assay_lines = ["\t".join(row) for row in rows]
        return "\n".join(assay_lines)

    def validate_isatab(
        self, investigation_path: Path, study_path: Path, assay_path: Path
    ) -> List[str]:
        """Validate ISA-TAB files.

        Args:
            investigation_path: Path to investigation file
            study_path: Path to study file
            assay_path: Path to assay file

        Returns:
            List of validation errors (empty if valid)

        Note:
            Basic validation only. For full validation, use ISA-tools validator.
        """
        errors = []

        # Check files exist
        if not investigation_path.exists():
            errors.append(f"Investigation file not found: {investigation_path}")
        if not study_path.exists():
            errors.append(f"Study file not found: {study_path}")
        if not assay_path.exists():
            errors.append(f"Assay file not found: {assay_path}")

        if errors:
            return errors

        # Check file naming conventions
        if not investigation_path.name.startswith("i_"):
            errors.append(f"Investigation file must start with 'i_': {investigation_path.name}")
        if not study_path.name.startswith("s_"):
            errors.append(f"Study file must start with 's_': {study_path.name}")
        if not assay_path.name.startswith("a_"):
            errors.append(f"Assay file must start with 'a_': {assay_path.name}")

        # Basic content validation
        investigation_content = investigation_path.read_text()
        required_sections = ["ONTOLOGY SOURCE REFERENCE", "INVESTIGATION", "STUDY"]
        for section in required_sections:
            if section not in investigation_content:
                errors.append(f"Missing required section in investigation file: {section}")

        return errors


def export_to_isatab(
    dataset: CuratedDataset, output_dir: Path
) -> Dict[str, Path]:
    """Convenience function to export dataset to ISA-TAB.

    Args:
        dataset: CuratedDataset to export
        output_dir: Output directory

    Returns:
        Dictionary with file paths

    Example:
        >>> files = export_to_isatab(my_dataset, Path("./output"))
        >>> print(files['investigation'], files['study'], files['assay'])
    """
    formatter = ISATABFormatter()
    return formatter.to_isatab(dataset, output_dir)
