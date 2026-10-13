import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('.', import.meta.url));
export default { output: 'export', devIndicators: false, outputFileTracingRoot: root, turbopack: {root} };
