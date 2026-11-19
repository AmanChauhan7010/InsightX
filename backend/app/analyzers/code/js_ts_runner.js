// Unified JavaScript / TypeScript diagnostic runner using ESLint & TypeScript Compiler API
const path = require('path');
const fs = require('fs');

const frontendNodeModules = path.resolve(__dirname, '../../../../frontend/node_modules');
const tsPath = path.join(frontendNodeModules, 'typescript');
const eslintPath = path.join(frontendNodeModules, 'eslint');

let ts = null;
let ESLint = null;

try {
  ts = require(tsPath);
} catch (e) {}

try {
  ESLint = require(eslintPath).ESLint;
} catch (e) {}

async function run() {
  const code = process.env.SOURCE_CODE || '';
  const filePath = process.env.FILE_PATH || 'app.js';
  const isTs = filePath.endsWith('.ts') || filePath.endsWith('.tsx');
  const diagnostics = [];

  // 1. TypeScript diagnostics
  if (isTs && ts) {
    try {
      const sourceFile = ts.createSourceFile(filePath, code, ts.ScriptTarget.Latest, true);
      const defaultHost = ts.createCompilerHost({});
      const host = {
        getSourceFile: (name) => name === filePath ? sourceFile : defaultHost.getSourceFile(name, ts.ScriptTarget.Latest),
        getDefaultLibFileName: (opts) => defaultHost.getDefaultLibFileName(opts),
        writeFile: () => {},
        getCurrentDirectory: () => '.',
        getDirectories: () => [],
        getCanonicalFileName: (f) => f,
        useCaseSensitiveFileNames: () => true,
        getNewLine: () => '\n',
        fileExists: (name) => name === filePath || defaultHost.fileExists(name),
        readFile: (name) => name === filePath ? code : defaultHost.readFile(name)
      };
      const program = ts.createProgram([filePath], { noEmit: true, strict: true }, host);
      const diags = ts.getPreEmitDiagnostics(program, sourceFile);
      for (const d of diags) {
        if (!d.file || d.file.fileName !== filePath) continue;
        const { line, character } = sourceFile.getLineAndCharacterOfPosition(d.start);
        diagnostics.push({
          tool: 'tsc',
          rule_id: 'TS' + d.code,
          message: ts.flattenDiagnosticMessageText(d.messageText, '\n'),
          line: line + 1,
          column: character + 1,
          severity: 'High',
          category: 'Type Errors'
        });
      }
    } catch (e) {}
  }

  // 2. ESLint for undefined names & syntax (for JS files)
  if (!isTs && ESLint) {
    try {
      const eslint = new ESLint({
        overrideConfigFile: true,
        overrideConfig: [{
          languageOptions: {
            ecmaVersion: 'latest',
            sourceType: 'module',
            globals: {
              console: 'readonly',
              process: 'readonly',
              Buffer: 'readonly',
              window: 'readonly',
              document: 'readonly',
              setTimeout: 'readonly',
              clearTimeout: 'readonly',
              setInterval: 'readonly',
              clearInterval: 'readonly',
              fetch: 'readonly'
            }
          },
          rules: {
            'no-undef': 'error'
          }
        }]
      });
      const results = await eslint.lintText(code);
      for (const msg of results[0]?.messages || []) {
        diagnostics.push({
          tool: 'eslint',
          rule_id: msg.ruleId || 'JS_SYNTAX_ERROR',
          message: msg.message,
          line: msg.line || 1,
          column: msg.column || 1,
          severity: msg.severity === 2 ? 'High' : 'Medium',
          category: msg.ruleId === 'no-undef' ? 'Undefined Names / Symbol Errors' : 'Syntax & Parsing'
        });
      }
    } catch (e) {}
  }

  process.stdout.write(JSON.stringify(diagnostics));
}

run().catch((err) => {
  process.stderr.write(String(err));
  process.stdout.write('[]');
});
