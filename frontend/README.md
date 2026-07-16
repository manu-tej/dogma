# Dogma web workspace

React/TypeScript interface for Dogma's graph-grounded computational biology workspace.

## Overview

This frontend includes the hypothesis graph, method and pipeline planning, and the
legacy GEO dataset-search surface. It talks to the Dogma backend through the temporary
`quration` API compatibility namespace. It enables researchers to:

- Search for NGS datasets using disease terms, therapy classes, and gene targets
- View detailed experimental design information
- Explore sample characteristics and metadata
- Identify datasets with potential survival data
- Export results for further analysis

## Technology Stack

- **Framework**: React 18
- **Build Tool**: Vite 6
- **Language**: TypeScript
- **UI Components**: Radix UI primitives
- **Styling**: Tailwind CSS (via index.css)
- **State Management**: React hooks
- **API Client**: Custom fetch-based service
- **Icons**: Lucide React

## Quick Start

### Prerequisites

- Node.js 18+ and npm 9+
- Backend API running at http://localhost:8000 (see main README)

### Installation

```bash
# Install dependencies
npm install

# Create environment file
cat > .env << EOL
VITE_API_URL=http://localhost:8000
EOL

# Start development server
npm run dev
```

The application will be available at http://localhost:5173

### Building for Production

```bash
# Build optimized bundle
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/         # React components
│   │   ├── ui/             # Reusable UI components (Radix)
│   │   └── [features]/     # Feature-specific components
│   ├── services/           # API client services
│   │   └── api.ts          # Backend API client
│   ├── utils/              # Utility functions
│   ├── hooks/              # Custom React hooks
│   ├── lib/                # Third-party library configs
│   ├── App.tsx             # Main application component
│   ├── main.tsx            # Application entry point
│   └── index.css           # Global styles (Tailwind)
├── public/                 # Static assets
├── index.html              # HTML template
├── package.json            # Dependencies and scripts
├── vite.config.ts          # Vite configuration
└── tsconfig.json           # TypeScript configuration
```

## Features

### GEO Dataset Search

The primary feature is searching for GEO datasets with advanced filtering:

```typescript
// Example usage of the search API
import { searchGeo } from '@/services/api';

const results = await searchGeo({
  disease_terms: ["melanoma"],
  therapy_class: "immunotherapy",
  therapy_scope: "specific",
  targets_or_genes: ["PD-1", "CTLA4"],
  study_keywords: ["checkpoint inhibitor"],
  must_have_clinical: true,
  min_samples: 20
}, {
  max_results: 50,
  fetch_samples: true
});
```

### Dataset Information Display

Each result includes:
- GSE accession ID and title
- Dataset summary
- Experimental design (conditions, sample counts)
- Platform information
- Associated publication (PMID)
- Survival data indicator
- Match reasons explaining why it was returned

### Sample-Level Data

When `fetch_samples` is enabled, individual GSM sample records are retrieved:
- Sample characteristics
- Sample type
- Raw metadata

## API Integration

### Backend API Client

Located in `src/services/api.ts`:

```typescript
// API base URL from environment
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Search GEO datasets
export async function searchGeo(
  query: QuerySpec,
  options?: SearchOptions
): Promise<GeoDatasetCandidate[]> {
  // Implementation
}

// Health check
export async function checkHealth(): Promise<{ status: string }> {
  // Implementation
}
```

### TypeScript Types

Types are defined to match the backend Pydantic models:

```typescript
interface QuerySpec {
  disease_terms: string[];
  therapy_class?: string;
  therapy_scope: "specific" | "broad";
  targets_or_genes?: string[];
  study_keywords?: string[];
  must_have_clinical?: boolean;
  min_samples?: number;
}

interface GeoDatasetCandidate {
  gse_id: string;
  title: string;
  summary: string;
  experimental_design: ExperimentalDesign;
  n_samples?: number;
  platforms: string[];
  primary_pmid?: string;
  maybe_has_survival_data: boolean;
  match_reasons: string[];
  samples: GsmSample[];
  samples_fetched: boolean;
}
```

## Environment Variables

Create a `.env` file in the frontend directory:

```bash
# Backend API URL (required)
VITE_API_URL=http://localhost:8000

# Optional: Enable debug logging
VITE_DEBUG=true
```

Note: Vite only exposes variables prefixed with `VITE_` to the frontend.

## Development

### Running the Dev Server

```bash
npm run dev
```

Features:
- Hot Module Replacement (HMR)
- Fast refresh for React components
- TypeScript type checking
- Instant updates on file changes

### Type Checking

```bash
# Run TypeScript compiler in check mode
npx tsc --noEmit

# Or if configured in package.json
npm run type-check
```

### Code Quality

```bash
# Format code (if configured)
npm run format

# Lint code (if configured)
npm run lint
```

### Component Development

The project uses Radix UI for accessible, unstyled components:

```typescript
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

// Example component
function SearchForm() {
  return (
    <form>
      <Input placeholder="Search..." />
      <Button>Search</Button>
    </form>
  );
}
```

## Testing

### Manual Testing

1. Start the backend API
2. Start the frontend dev server
3. Open http://localhost:5173
4. Test the search functionality

### Integration Testing

Test with the backend API:

```bash
# 1. Ensure backend is running
curl http://localhost:8000/health

# 2. Test search from frontend
# Open browser dev tools (F12)
# Make a search and check Network tab for API calls
```

## Deployment

### Production Build

```bash
# Build optimized bundle
npm run build

# Output will be in dist/
ls -la dist/
```

### Serving Static Files

The built files can be served by any static file server:

```bash
# Using serve
npx serve dist

# Using Python
python -m http.server --directory dist 3000

# Using nginx
# Copy dist/ contents to nginx html directory
```

### Environment-Specific Builds

For different environments, create multiple `.env` files:

```bash
# .env.development
VITE_API_URL=http://localhost:8000

# .env.production
VITE_API_URL=https://api.dogma.example.com

# .env.staging
VITE_API_URL=https://staging-api.dogma.example.com
```

## Troubleshooting

### API Connection Issues

**Problem**: Cannot connect to backend API

**Solutions**:
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check CORS settings in backend `server.py`
3. Verify `VITE_API_URL` in `.env`
4. Check browser console for CORS errors

### Build Errors

**Problem**: TypeScript compilation errors

**Solutions**:
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Vite cache
rm -rf node_modules/.vite
npm run dev
```

### Hot Reload Not Working

**Problem**: Changes not reflected in browser

**Solutions**:
1. Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
2. Restart dev server
3. Clear browser cache
4. Check for syntax errors in console

### Port Already in Use

**Problem**: Port 5173 is already in use

**Solution**:
```bash
# Use a different port
vite --port 3000

# Or kill the process using 5173
lsof -i :5173
kill -9 <PID>
```

## Usage Examples

### Basic Search

```typescript
// Search for melanoma datasets
const results = await searchGeo({
  disease_terms: ["melanoma"],
  therapy_scope: "broad"
});

console.log(`Found ${results.length} datasets`);
```

### Advanced Search with Filters

```typescript
// Search for immunotherapy studies with survival data
const results = await searchGeo({
  disease_terms: ["melanoma", "skin cancer"],
  therapy_class: "immunotherapy",
  therapy_scope: "specific",
  targets_or_genes: ["PD-1", "PD-L1", "CTLA4"],
  study_keywords: ["checkpoint inhibitor", "response"],
  must_have_clinical: true,
  min_samples: 30
}, {
  max_results: 100,
  fetch_samples: true,
  max_samples_per_dataset: 50
});

// Filter for datasets with survival data
const withSurvival = results.filter(d => d.maybe_has_survival_data);
console.log(`Found ${withSurvival.length} datasets with potential survival data`);
```

### Processing Results

```typescript
// Extract all unique platforms
const platforms = new Set(
  results.flatMap(d => d.platforms)
);

// Group by condition count
const byConditions = results.reduce((acc, dataset) => {
  const count = dataset.experimental_design.conditions?.length || 0;
  acc[count] = (acc[count] || 0) + 1;
  return acc;
}, {});

console.log("Datasets by number of conditions:", byConditions);
```

## Contributing

See [MONOREPO_SETUP.md](../MONOREPO_SETUP.md) for development setup.

## Links

- [Main README](../README.md) - Project overview
- [API Documentation](../docs/API.md) - Backend API reference
- [Setup Guide](../MONOREPO_SETUP.md) - Detailed setup instructions

## License

See [LICENSE](../LICENSE) file
