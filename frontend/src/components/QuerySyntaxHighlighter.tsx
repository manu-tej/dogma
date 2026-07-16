/**
 * Syntax highlighter for NCBI search queries
 * Color-codes different parts of the query for better readability
 */

interface QueryToken {
  type: 'field' | 'term' | 'operator' | 'paren' | 'quote' | 'whitespace';
  value: string;
}

function tokenizeQuery(query: string): QueryToken[] {
  const tokens: QueryToken[] = [];
  let i = 0;

  while (i < query.length) {
    const char = query[i];

    // Field tags: [Title], [Organism], etc.
    if (char === '[') {
      const endBracket = query.indexOf(']', i);
      if (endBracket !== -1) {
        tokens.push({
          type: 'field',
          value: query.substring(i, endBracket + 1)
        });
        i = endBracket + 1;
        continue;
      }
    }

    // Parentheses
    if (char === '(' || char === ')') {
      tokens.push({ type: 'paren', value: char });
      i++;
      continue;
    }

    // Quotes
    if (char === '"') {
      tokens.push({ type: 'quote', value: char });
      i++;
      continue;
    }

    // Whitespace
    if (/\s/.test(char)) {
      let whitespace = '';
      while (i < query.length && /\s/.test(query[i])) {
        whitespace += query[i];
        i++;
      }
      tokens.push({ type: 'whitespace', value: whitespace });
      continue;
    }

    // Operators and terms
    // Look ahead to capture full words
    let word = '';
    while (i < query.length && !/[\s()\[\]"]/.test(query[i])) {
      word += query[i];
      i++;
    }

    if (word) {
      // Check if it's an operator
      if (word === 'AND' || word === 'OR' || word === 'NOT') {
        tokens.push({ type: 'operator', value: word });
      } else {
        tokens.push({ type: 'term', value: word });
      }
    }
  }

  return tokens;
}

interface QuerySyntaxHighlighterProps {
  query: string;
  className?: string;
}

export function QuerySyntaxHighlighter({ query, className = '' }: QuerySyntaxHighlighterProps) {
  const tokens = tokenizeQuery(query);

  return (
    <span className={`font-mono ${className}`}>
      {tokens.map((token, idx) => {
        switch (token.type) {
          case 'field':
            return (
              <span key={idx} className="text-signal">
                {token.value}
              </span>
            );
          case 'operator':
            return (
              <span key={idx} className="text-signal font-semibold">
                {token.value}
              </span>
            );
          case 'term':
            return (
              <span key={idx} className="text-foreground">
                {token.value}
              </span>
            );
          case 'paren':
            return (
              <span key={idx} className="text-muted-foreground/70">
                {token.value}
              </span>
            );
          case 'quote':
            return (
              <span key={idx} className="text-positive">
                {token.value}
              </span>
            );
          case 'whitespace':
            return <span key={idx}>{token.value}</span>;
          default:
            return <span key={idx}>{token.value}</span>;
        }
      })}
    </span>
  );
}
