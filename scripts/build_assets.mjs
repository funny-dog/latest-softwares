import { build } from 'esbuild';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { createHash } from 'crypto';
import { join, basename } from 'path';

const WEB_DIR = 'web';
const DIST_DIR = 'web/dist';

// 确保 dist 目录存在
mkdirSync(DIST_DIR, { recursive: true });

// 读取源文件
const appJs = readFileSync(join(WEB_DIR, 'app.js'), 'utf-8');
const stylesCss = readFileSync(join(WEB_DIR, 'styles.css'), 'utf-8');

// 计算内容哈希
function contentHash(content) {
  return createHash('md5').update(content).digest('hex').slice(0, 8);
}

// 构建 JS
const jsResult = await build({
  stdin: {
    contents: appJs,
    loader: 'js',
  },
  bundle: false,
  minify: true,
  write: false,
});

const jsHash = contentHash(jsResult.outputFiles[0].text);
const jsFilename = `app.${jsHash}.js`;
writeFileSync(join(DIST_DIR, jsFilename), jsResult.outputFiles[0].text);

// 构建 CSS（简单 minification）
const minifiedCss = stylesCss
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/\s+/g, ' ')
  .replace(/\s*([{}:;,])\s*/g, '$1')
  .trim();

const cssHash = contentHash(minifiedCss);
const cssFilename = `styles.${cssHash}.css`;
writeFileSync(join(DIST_DIR, cssFilename), minifiedCss);

// 生成 asset manifest
const manifest = {
  'app.js': jsFilename,
  'styles.css': cssFilename,
};

writeFileSync(
  join(DIST_DIR, 'asset-manifest.json'),
  JSON.stringify(manifest, null, 2)
);

console.log('✓ Build complete:');
console.log(`  ${jsFilename} (${(jsResult.outputFiles[0].text.length / 1024).toFixed(1)}KB)`);
console.log(`  ${cssFilename} (${(minifiedCss.length / 1024).toFixed(1)}KB)`);
