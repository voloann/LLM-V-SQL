/**
 * Utility to format raw SQL query strings into clean, multi-line formatted SQL.
 * Breaks clauses onto new lines (SELECT, FROM, JOIN, WHERE, GROUP BY, ORDER BY, etc.)
 * and indents logical operators (AND, OR) while preserving ranges like BETWEEN x AND y.
 */
export function formatSql(sql) {
  if (!sql || typeof sql !== 'string') return '';

  let clean = sql.replace(/\s+/g, ' ').trim();

  // Pattern matching major SQL clauses
  const clauseRegex = /\s*\b(SELECT|FROM|WHERE|LEFT\s+OUTER\s+JOIN|RIGHT\s+OUTER\s+JOIN|FULL\s+OUTER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|CROSS\s+JOIN|JOIN|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|UNION\s+ALL|UNION)\b\s*/gi;

  clean = clean.replace(clauseRegex, (match, p1) => {
    return '\n' + p1.toUpperCase().replace(/\s+/g, ' ') + ' ';
  });

  // Logical operators AND / OR on new line with indentation
  clean = clean.replace(/\s+\b(AND|OR)\b\s+/gi, (match, p1) => {
    return '\n  ' + p1.toUpperCase() + ' ';
  });

  // Keep BETWEEN ... AND together on one logical unit
  clean = clean.replace(/\bBETWEEN\s+([^\n]+?)\s*\n\s*AND\b/gi, 'BETWEEN $1 AND');

  return clean.trim();
}

export default formatSql;
