/** Canonical web URLs for grounded ontology terms, so sources are clickable. */

/**
 * URL for an ontology term (e.g. UniProt:P00533, GO:0007259).
 *
 * UniProt gets its native entry page; everything else resolves through
 * identifiers.org, which handles GO / MONDO / CHEBI / CL / UBERON / HP / etc.
 * Returns null when either part is missing.
 */
export function ontologyTermUrl(ontology: string, termId: string): string | null {
  if (!ontology || !termId) return null;
  // term_id may already carry its prefix ("GO:0007259"); use the bare id.
  const bareId = termId.includes(":") ? termId.split(":").pop()! : termId;

  if (ontology.toLowerCase() === "uniprot") {
    return `https://www.uniprot.org/uniprotkb/${bareId}`;
  }
  return `https://identifiers.org/${ontology.toUpperCase()}:${bareId}`;
}
