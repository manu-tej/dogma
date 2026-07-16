# Method Broker

The Method Broker is an intelligent system for matching user analysis requests to appropriate bioinformatics methods and pipelines. It uses LLM-based natural language understanding to parse user queries and a sophisticated matching engine to recommend the best methods.

## Features

- **Natural Language Queries**: Users can describe their analysis needs in plain English
- **LLM-Based Parsing**: Automatically extracts structured requirements from queries
- **Intelligent Matching**: Scores methods based on relevance, quality, and compatibility
- **Comprehensive Registry**: Pre-populated with common bioinformatics tools and pipelines
- **Method Proposals**: Users can request new methods to be added
- **Quality Metrics**: Each method includes reproducibility, citations, and community ratings

## Architecture

```
┌─────────────────┐
│  User Query     │
└────────┬────────┘
         │
         v
┌─────────────────────┐
│  Request Parser     │  ← LLM-based
│  (LLM Integration)  │
└────────┬────────────┘
         │
         v
┌─────────────────────┐
│  Parsed Request     │
│  - Data Modality    │
│  - Analysis Type    │
│  - Requirements     │
└────────┬────────────┘
         │
         v
┌─────────────────────┐
│  Matching Engine    │
│  - Heuristic Scores │
│  - Quality Metrics  │
└────────┬────────────┘
         │
         v
┌─────────────────────┐
│  Ranked Methods     │
│  with Explanations  │
└─────────────────────┘
```

## Components

### 1. Method Registry

Stores and manages available analysis methods.

```python
from quration.broker import MethodRegistry

registry = MethodRegistry()

# List all methods
methods = registry.list_methods()

# Filter by category
variant_methods = registry.list_methods(category=MethodCategory.VARIANT_CALLING)

# Search by keyword
results = registry.search_methods("rnaseq")
```

### 2. Request Parser

Uses LLMs to parse natural language queries into structured requests.

```python
from quration.broker import RequestParser
from quration.config import get_config

config = get_config()
parser = RequestParser(config)

parsed = parser.parse_request(
    "I need to call variants from whole genome sequencing data"
)

print(f"Data Modality: {parsed.data_modality}")
print(f"Analysis Type: {parsed.analysis_type}")
print(f"Confidence: {parsed.confidence}")
```

### 3. Matching Engine

Scores and ranks methods based on parsed requests.

```python
from quration.broker import MatchingEngine, MethodRegistry

registry = MethodRegistry()
engine = MatchingEngine(registry)

matches = engine.find_matches(parsed_request, max_results=5)

for match in matches:
    print(f"{match.method.name}: {match.score:.2f}")
    print(f"  Reasons: {', '.join(match.match_reasons)}")
```

### 4. Method Broker

Main orchestrator that ties everything together.

```python
from quration.broker import MethodBroker, MethodRequest
from quration.config import get_config

config = get_config()
broker = MethodBroker(config)

request = MethodRequest(
    query="I need to analyze differential gene expression in RNA-seq data",
    max_recommendations=5,
    prefer_published=True,
)

response = await broker.process_request(request)

for match in response.matches:
    print(f"{match.rank}. {match.method.name} ({match.score:.2%})")
```

### 5. Proposal Manager

Handles user requests for new methods.

```python
from quration.broker import ProposalManager, MethodProposal, MethodCategory

manager = ProposalManager()

proposal = MethodProposal(
    name="AlphaFold Protein Structure Prediction",
    category=MethodCategory.CUSTOM,
    description="AI-powered protein structure prediction",
    justification="Need this for structural analysis",
    use_cases=["Predict protein structures from sequences"],
    proposed_by="user123",
)

proposal_id = manager.submit_proposal(proposal)
```

## API Endpoints

### Match Methods

```bash
POST /broker/match
Content-Type: application/json

{
  "query": "I need to call variants from whole genome sequencing",
  "max_recommendations": 5,
  "prefer_published": true
}
```

Response:
```json
{
  "request": {...},
  "parsed_request": {
    "data_modality": "dna_seq",
    "analysis_type": "variant calling",
    "confidence": 0.95
  },
  "matches": [
    {
      "method": {...},
      "score": 0.92,
      "match_reasons": ["Supports dna_seq data", "Peer-reviewed method"],
      "recommended": true,
      "rank": 1
    }
  ]
}
```

### List Methods

```bash
GET /broker/methods?category=variant_calling&modality=dna_seq
```

### Get Method Details

```bash
GET /broker/methods/gatk-germline-variant-calling
```

### Submit Proposal

```bash
POST /broker/proposals
Content-Type: application/json

{
  "name": "New Method",
  "category": "rna_seq",
  "description": "A new RNA-seq analysis method",
  "justification": "We need this for our research",
  "use_cases": ["Analyze RNA-seq data"],
  "proposed_by": "user123"
}
```

### Get Statistics

```bash
GET /broker/stats
```

Response:
```json
{
  "registry": {
    "total_methods": 5,
    "by_category": {
      "variant_calling": 1,
      "rna_seq": 1,
      ...
    },
    "average_quality_score": 0.95
  },
  "proposals": {
    "total_proposals": 10,
    "by_status": {
      "pending": 3,
      "approved": 5,
      "rejected": 2
    }
  }
}
```

## Default Methods

The registry comes pre-populated with:

1. **GATK Germline Variant Calling** - Best practices for variant discovery
2. **DESeq2 Differential Expression** - RNA-seq differential expression analysis
3. **nf-core ChIP-seq** - Comprehensive ChIP-seq pipeline
4. **Seurat Single-cell Analysis** - scRNA-seq clustering and analysis
5. **FastQC Quality Control** - Sequencing data quality assessment

## Adding Custom Methods

You can add custom methods to the registry:

```python
from quration.broker import AnalysisMethod, MethodCategory
from quration.broker.models import (
    MethodInputSpec,
    MethodOutputSpec,
    MethodQualityMetrics,
)

custom_method = AnalysisMethod(
    id="my-custom-method",
    name="My Custom Analysis",
    category=MethodCategory.CUSTOM,
    description="Custom analysis method",
    implementation_type="script",
    version="1.0.0",
    inputs=[
        MethodInputSpec(
            name="input_data",
            description="Input data files",
            data_type="BAM",
            required=True,
        )
    ],
    outputs=[
        MethodOutputSpec(
            name="results",
            description="Analysis results",
            data_type="CSV",
        )
    ],
    supported_modalities=[DataModality.DNA_SEQ],
    quality_metrics=MethodQualityMetrics(
        reproducibility_score=0.85,
        code_availability=True,
        documentation_quality=0.80,
        peer_reviewed=False,
        citation_count=0,
    ),
    compute_requirements={},
    tags=["custom"],
)

broker.add_method(custom_method)
```

## Scoring Algorithm

The matching engine uses a weighted scoring system:

**Overall Score = 0.5 × Relevance + 0.3 × Quality + 0.2 × Compatibility**

Where:
- **Relevance** (0-1): How well the method matches the request
  - Data modality match (30%)
  - Analysis type match (25%)
  - Specific tool match (20%)
  - Keyword match (10%)
  - Organism compatibility (10%)
  - Sample count compatibility (5%)

- **Quality** (0-1): Method quality metrics
  - Reproducibility score (40%)
  - Documentation quality (20%)
  - Code availability (20%)
  - Peer review status (20%)

- **Compatibility** (0-1): Requirements compatibility
  - Data modality compatibility (50%)
  - Organism compatibility (30%)
  - Sample count compatibility (20%)

## Future Enhancements

- **Advanced Heuristics**: Machine learning-based scoring
- **Literature Harvesting**: Automatic discovery of new methods from publications
- **User Preferences**: Personalized recommendations based on user history
- **Multiple LLM Providers**: Support for different LLM backends
- **Execution Engine**: Actually run the matched methods
- **Cost Estimation**: Predict computational costs
- **Performance Benchmarks**: Compare method performance metrics

## Testing

Run the test suite:

```bash
pytest tests/test_broker.py -v
```

## Frontend Integration

The frontend includes a `MethodBrowser` component:

```typescript
import { MethodBrowser } from './components/MethodBrowser';

function App() {
  return <MethodBrowser />;
}
```

Features:
- Browse all methods
- Search by keyword
- Get recommendations from natural language queries
- View detailed method information
- Submit method proposals
