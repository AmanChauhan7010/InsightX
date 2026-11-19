import React, { useRef, useMemo, useState } from 'react';
import { Trash2, Copy, Check, AlignLeft, Code2 } from 'lucide-react';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  language: string;
  placeholder?: string;
  readOnly?: boolean;
  minHeightClass?: string;
  ariaLabel?: string;
}

const PY_KEYWORDS = new Set([
  'async', 'await', 'def', 'class', 'return', 'if', 'elif', 'else', 'for', 'while',
  'try', 'except', 'finally', 'with', 'as', 'import', 'from', 'pass', 'break',
  'continue', 'raise', 'yield', 'lambda', 'in', 'not', 'and', 'or', 'is', 'None',
  'True', 'False', 'global', 'nonlocal', 'assert', 'del',
]);

const JS_KEYWORDS = new Set([
  'async', 'await', 'function', 'const', 'let', 'var', 'return', 'if', 'else',
  'for', 'while', 'try', 'catch', 'finally', 'throw', 'new', 'class', 'extends',
  'import', 'export', 'from', 'default', 'interface', 'type', 'enum', 'implements',
  'public', 'private', 'readonly', 'true', 'false', 'null', 'undefined', 'switch',
  'case', 'break', 'continue', 'typeof', 'instanceof',
]);

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function highlightLine(line: string, language: string): string {
  const isPy = language === 'python';
  const keywords = isPy ? PY_KEYWORDS : JS_KEYWORDS;
  // Tokenize comments, strings, decorators, numbers, identifiers, brackets
  const tokenRegex = isPy
    ? /(#.*$|"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|@[A-Za-z_]\w*|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b|[()[\]{}])/g
    : /(\/\/.*$|`(?:\\.|[^`\\])*`|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b|[()[\]{}])/g;

  let result = '';
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(line)) !== null) {
    if (match.index > lastIndex) {
      result += escapeHtml(line.slice(lastIndex, match.index));
    }
    const token = match[0];
    const escaped = escapeHtml(token);

    if ((isPy && token.startsWith('#')) || (!isPy && token.startsWith('//'))) {
      result += `<span style="color:#64748B;font-style:italic">${escaped}</span>`;
    } else if (
      token.startsWith('"') ||
      token.startsWith("'") ||
      token.startsWith('`')
    ) {
      result += `<span style="color:#86EFAC">${escaped}</span>`;
    } else if (isPy && token.startsWith('@')) {
      result += `<span style="color:#FCD34D">${escaped}</span>`;
    } else if (/^\d/.test(token)) {
      result += `<span style="color:#FDBA74">${escaped}</span>`;
    } else if (keywords.has(token)) {
      result += `<span style="color:#93C5FD;font-weight:600">${escaped}</span>`;
    } else if (/^[()[\]{}]$/.test(token)) {
      result += `<span style="color:#CBD5E1">${escaped}</span>`;
    } else {
      result += `<span style="color:#E2E8F0">${escaped}</span>`;
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < line.length) {
    result += escapeHtml(line.slice(lastIndex));
  }
  return result || '&nbsp;';
}

function checkBracketBalance(code: string): { balanced: boolean; message: string } {
  const pairs: Record<string, string> = { '(': ')', '[': ']', '{': '}' };
  const closing = new Set([')', ']', '}']);
  const stack: string[] = [];
  let inString: string | null = null;

  for (let i = 0; i < code.length; i++) {
    const ch = code[i];
    if (inString) {
      if (ch === '\\') {
        i++;
        continue;
      }
      if (ch === inString) inString = null;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      inString = ch;
      continue;
    }
    if (pairs[ch]) {
      stack.push(pairs[ch]);
    } else if (closing.has(ch)) {
      const expected = stack.pop();
      if (expected !== ch) {
        return { balanced: false, message: `Unmatched '${ch}'` };
      }
    }
  }
  if (stack.length > 0) {
    return { balanced: false, message: `Missing closing '${stack[stack.length - 1]}'` };
  }
  return { balanced: true, message: 'Brackets balanced' };
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  value,
  onChange,
  language,
  placeholder = 'Write or paste Python, JavaScript, or TypeScript code here...',
  readOnly = false,
  minHeightClass = 'h-80',
  ariaLabel = 'Source Code Editor',
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  const lines = useMemo(() => (value ? value.split('\n') : ['']), [value]);

  const highlightedHtml = useMemo(() => {
    if (!value) return '';
    return value
      .split('\n')
      .map((line) => highlightLine(line, language))
      .join('\n') + '\n';
  }, [value, language]);

  const bracketStatus = useMemo(() => checkBracketBalance(value), [value]);

  const handleScroll = () => {
    if (!textareaRef.current) return;
    const { scrollTop, scrollLeft } = textareaRef.current;
    if (preRef.current) {
      preRef.current.scrollTop = scrollTop;
      preRef.current.scrollLeft = scrollLeft;
    }
    if (gutterRef.current) {
      gutterRef.current.scrollTop = scrollTop;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (readOnly) return;
    const el = e.currentTarget;
    const indentUnit = language === 'python' ? '    ' : '  ';

    // Tab / Shift+Tab indentation
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = el.selectionStart;
      const end = el.selectionEnd;

      if (e.shiftKey) {
        const lineStart = value.lastIndexOf('\n', start - 1) + 1;
        const currentLine = value.slice(lineStart, end);
        if (currentLine.startsWith(indentUnit)) {
          const next = value.slice(0, lineStart) + value.slice(lineStart + indentUnit.length);
          onChange(next);
          requestAnimationFrame(() => {
            el.selectionStart = Math.max(lineStart, start - indentUnit.length);
            el.selectionEnd = Math.max(lineStart, end - indentUnit.length);
          });
        }
      } else {
        const next = value.slice(0, start) + indentUnit + value.slice(end);
        onChange(next);
        requestAnimationFrame(() => {
          el.selectionStart = el.selectionEnd = start + indentUnit.length;
        });
      }
      return;
    }

    // Enter key: preserve leading indentation & auto-indent after ':' (Python) or '{' (JS/TS)
    if (e.key === 'Enter') {
      e.preventDefault();
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const lineStart = value.lastIndexOf('\n', start - 1) + 1;
      const currentLine = value.slice(lineStart, start);
      const leadingSpaces = currentLine.match(/^(\s*)/)?.[1] || '';
      const trimmed = currentLine.trimEnd();
      const needsExtra =
        (language === 'python' && trimmed.endsWith(':')) ||
        (language !== 'python' && trimmed.endsWith('{'));
      const insertText = '\n' + leadingSpaces + (needsExtra ? indentUnit : '');
      const next = value.slice(0, start) + insertText + value.slice(end);
      onChange(next);
      requestAnimationFrame(() => {
        el.selectionStart = el.selectionEnd = start + insertText.length;
      });
    }
  };

  const handleSafeFormat = () => {
    if (readOnly || !value) return;
    // Safe, meaning-preserving formatting: normalize CRLF -> LF, expand tabs, trim trailing spaces
    const tabSpaces = language === 'python' ? '    ' : '  ';
    const cleaned = value
      .replace(/\r\n/g, '\n')
      .split('\n')
      .map((l) => l.replace(/\t/g, tabSpaces).replace(/[ \t]+$/, ''))
      .join('\n')
      .replace(/\n{3,}/g, '\n\n');
    onChange(cleaned);
  };

  const handleCopy = () => {
    if (!value) return;
    navigator.clipboard?.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div
      className="rounded-xl border border-slate-700 overflow-hidden shadow-sm focus-within:ring-2 focus-within:ring-blue-500/40 focus-within:border-blue-500 transition-all"
      style={{ backgroundColor: '#0F172A' }}
    >
      {/* Editor Toolbar */}
      <div className="px-3.5 py-2 bg-slate-900/95 border-b border-slate-800 flex items-center justify-between text-[11px]">
        <div className="flex items-center space-x-2 text-slate-300 font-mono">
          <Code2 className="w-3.5 h-3.5 text-blue-400" />
          <span className="uppercase font-semibold text-blue-300">{language}</span>
          <span className="text-slate-600">•</span>
          <span className="text-slate-400">{lines.length} line{lines.length === 1 ? '' : 's'}</span>
          {value && (
            <>
              <span className="text-slate-600">•</span>
              <span className={bracketStatus.balanced ? 'text-emerald-400' : 'text-amber-400'}>
                {bracketStatus.message}
              </span>
            </>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {!readOnly && (
            <button
              type="button"
              onClick={handleSafeFormat}
              disabled={!value}
              className="inline-flex items-center space-x-1 px-2 py-1 rounded text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-40 transition-colors"
              title="Normalize indentation & remove trailing whitespace"
            >
              <AlignLeft className="w-3 h-3" />
              <span>Format</span>
            </button>
          )}
          <button
            type="button"
            onClick={handleCopy}
            disabled={!value}
            className="inline-flex items-center space-x-1 px-2 py-1 rounded text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-40 transition-colors"
          >
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
          {!readOnly && (
            <button
              type="button"
              onClick={() => onChange('')}
              disabled={!value}
              className="inline-flex items-center space-x-1 px-2 py-1 rounded text-slate-300 hover:text-red-400 hover:bg-slate-800 disabled:opacity-40 transition-colors"
            >
              <Trash2 className="w-3 h-3" />
              <span>Clear Code</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Editor Surface: Line Numbers Gutter + Synchronized Syntax Overlay + Textarea */}
      <div className={`relative flex ${minHeightClass}`} style={{ backgroundColor: '#0F172A' }}>
        {/* Line Numbers Gutter */}
        <div
          ref={gutterRef}
          aria-hidden="true"
          className="w-12 shrink-0 py-4 pr-3 pl-2 text-right font-mono text-[13px] leading-6 select-none overflow-hidden border-r border-slate-800 bg-slate-950/50"
          style={{ color: '#94A3B8' }}
        >
          {lines.map((_, idx) => (
            <div key={idx}>{idx + 1}</div>
          ))}
        </div>

        {/* Overlay Container */}
        <div className="relative flex-1 overflow-hidden">
          {/* Syntax-Highlighted Display Layer */}
          <pre
            ref={preRef}
            aria-hidden="true"
            className="absolute inset-0 m-0 p-4 font-mono text-[13px] leading-6 whitespace-pre overflow-hidden pointer-events-none"
            style={{ color: '#E2E8F0', tabSize: language === 'python' ? 4 : 2 }}
            dangerouslySetInnerHTML={{ __html: highlightedHtml }}
          />

          {/* Interactive Textarea Layer */}
          <textarea
            ref={textareaRef}
            aria-label={ariaLabel}
            value={value}
            onChange={(e) => !readOnly && onChange(e.target.value)}
            onScroll={handleScroll}
            onKeyDown={handleKeyDown}
            readOnly={readOnly}
            spellCheck={false}
            autoCapitalize="off"
            autoComplete="off"
            autoCorrect="off"
            placeholder={placeholder}
            className="insightx-code-textarea absolute inset-0 w-full h-full m-0 p-4 font-mono text-[13px] leading-6 whitespace-pre bg-transparent border-0 outline-none resize-none overflow-auto"
            style={{ tabSize: language === 'python' ? 4 : 2 }}
          />
        </div>
      </div>
    </div>
  );
};
