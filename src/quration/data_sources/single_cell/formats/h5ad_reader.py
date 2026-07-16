"""H5AD (AnnData) file reader for single-cell data."""

from typing import Any

import anndata
import pandas as pd

from quration.models.single_cell import CellPopulation, MarkerGene


class H5ADReader:
    """Reader for H5AD (AnnData) files."""

    def __init__(self, file_path: str, backed: bool = False):
        """Initialize H5AD reader.

        Args:
            file_path: Path to H5AD file
            backed: If True, use backed mode (memory efficient for large files)
        """
        self.file_path = file_path
        self.adata = anndata.read_h5ad(file_path, backed='r' if backed else None)

    @property
    def n_cells(self) -> int:
        """Number of cells in dataset."""
        return self.adata.n_obs

    @property
    def n_genes(self) -> int:
        """Number of genes in dataset."""
        return self.adata.n_vars

    def get_cell_metadata(self) -> pd.DataFrame:
        """Get cell-level metadata (obs).

        Returns:
            DataFrame with cell-level annotations
        """
        return self.adata.obs

    def get_gene_metadata(self) -> pd.DataFrame:
        """Get gene-level metadata (var).

        Returns:
            DataFrame with gene annotations
        """
        return self.adata.var

    def get_embeddings(self) -> dict[str, Any]:
        """Get dimensional reduction embeddings.

        Returns:
            Dictionary of embedding name -> coordinates
        """
        embeddings = {}
        if hasattr(self.adata, 'obsm'):
            for key, values in self.adata.obsm.items():
                embeddings[key] = values
        return embeddings

    def has_clusters(self) -> bool:
        """Check if dataset has cluster assignments.

        Returns:
            True if cluster assignments found
        """
        # Look for common cluster column names
        cluster_cols = ['leiden', 'louvain', 'cluster', 'clusters', 'cell_cluster']
        for col in cluster_cols:
            if col in self.adata.obs.columns:
                return True
        return False

    def get_cluster_column(self) -> str | None:
        """Get name of cluster assignment column.

        Returns:
            Column name or None if not found
        """
        cluster_cols = ['leiden', 'louvain', 'cluster', 'clusters', 'cell_cluster']
        for col in cluster_cols:
            if col in self.adata.obs.columns:
                return col
        return None

    def get_populations(self, cluster_key: str | None = None) -> list[CellPopulation]:
        """Extract cell populations/clusters.

        Args:
            cluster_key: Column name for cluster assignments (auto-detect if None)

        Returns:
            List of CellPopulation objects
        """
        if cluster_key is None:
            cluster_key = self.get_cluster_column()

        if cluster_key is None or cluster_key not in self.adata.obs.columns:
            return []

        populations = []
        cluster_ids = self.adata.obs[cluster_key].unique()

        for cluster_id in cluster_ids:
            cluster_mask = self.adata.obs[cluster_key] == cluster_id
            n_cells = cluster_mask.sum()

            # Calculate mean genes detected if available
            mean_genes = None
            if 'n_genes' in self.adata.obs.columns:
                mean_genes = float(self.adata.obs.loc[cluster_mask, 'n_genes'].mean())
            elif 'n_genes_by_counts' in self.adata.obs.columns:
                mean_genes = float(
                    self.adata.obs.loc[cluster_mask, 'n_genes_by_counts'].mean()
                )

            # Try to extract marker genes
            marker_genes = self._extract_marker_genes_for_cluster(str(cluster_id))

            # Try to infer cell type
            cell_type = self._infer_cell_type(cluster_mask)

            populations.append(
                CellPopulation(
                    population_id=str(cluster_id),
                    population_name=f"Cluster {cluster_id}",
                    cell_type=cell_type,
                    n_cells=int(n_cells),
                    marker_genes=marker_genes[:10] if marker_genes else [],  # Top 10
                    mean_genes_detected=mean_genes,
                )
            )

        return populations

    def _extract_marker_genes_for_cluster(
        self, cluster_id: str
    ) -> list[MarkerGene] | None:
        """Extract marker genes for a cluster from uns.

        Args:
            cluster_id: Cluster identifier

        Returns:
            List of MarkerGene objects or None
        """
        if 'rank_genes_groups' not in self.adata.uns:
            return None

        rgg = self.adata.uns['rank_genes_groups']
        marker_genes = []

        try:
            # Get number of genes available
            n_genes = len(rgg['names'][cluster_id]) if cluster_id in rgg['names'] else 0

            for i in range(min(50, n_genes)):
                gene_symbol = rgg['names'][cluster_id][i]

                # Extract statistics if available
                log2fc = None
                pval = None
                pval_adj = None

                if 'logfoldchanges' in rgg:
                    log2fc = float(rgg['logfoldchanges'][cluster_id][i])

                if 'pvals' in rgg:
                    pval = float(rgg['pvals'][cluster_id][i])

                if 'pvals_adj' in rgg:
                    pval_adj = float(rgg['pvals_adj'][cluster_id][i])

                marker_genes.append(
                    MarkerGene(
                        gene_symbol=str(gene_symbol),
                        log2_fold_change=log2fc,
                        p_value=pval,
                        adjusted_p_value=pval_adj,
                    )
                )

        except (KeyError, IndexError, TypeError):
            # Marker genes not available or wrong format
            return None

        return marker_genes if marker_genes else None

    def _infer_cell_type(self, cluster_mask: pd.Series) -> Any | None:
        """Try to infer cell type from cell-level annotations.

        Args:
            cluster_mask: Boolean mask for cluster cells

        Returns:
            OntologyTerm or None
        """
        # Look for cell type annotations
        cell_type_cols = ['cell_type', 'celltype', 'cell.type', 'CellType']

        for col in cell_type_cols:
            if col in self.adata.obs.columns:
                # Get most common cell type in cluster
                cell_types = self.adata.obs.loc[cluster_mask, col]
                if len(cell_types) > 0:
                    most_common = cell_types.mode()
                    if len(most_common) > 0:
                        from quration.models.metadata import OntologyTerm

                        return OntologyTerm(term=str(most_common[0]))

        return None

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics about the dataset.

        Returns:
            Dictionary with summary information
        """
        summary = {
            "n_cells": self.n_cells,
            "n_genes": self.n_genes,
            "has_embeddings": len(self.get_embeddings()) > 0,
            "has_clusters": self.has_clusters(),
            "has_marker_genes": 'rank_genes_groups' in self.adata.uns,
            "obs_columns": list(self.adata.obs.columns),
            "var_columns": list(self.adata.var.columns),
            "embeddings": list(self.get_embeddings().keys()),
        }

        return summary

    def close(self):
        """Close the file handle (for backed mode)."""
        if hasattr(self.adata, 'file') and self.adata.file is not None:
            self.adata.file.close()
