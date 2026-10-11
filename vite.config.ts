import { defineConfig, type Plugin } from 'vite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const ART_DIR = path.join(ROOT, 'public', 'art');

/**
 * Exposes the list of files in public/art as `virtual:art-manifest`, so the game only
 * requests 2D art that actually exists (no 404 noise) and falls back gracefully otherwise.
 * Adding/removing a file during `npm run dev` triggers a reload.
 */
function artManifest(): Plugin {
  const id = 'virtual:art-manifest';
  const rid = '\0' + id;
  const walk = (dir: string): string[] =>
    fs.existsSync(dir)
      ? fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => (d.isDirectory() ? walk(path.join(dir, d.name)) : [path.join(dir, d.name)]))
      : [];
  const list = () =>
    walk(ART_DIR)
      .filter((f) => /\.(png|webp|jpe?g|svg)$/i.test(f))
      .map((f) => 'art/' + path.relative(ART_DIR, f).split(path.sep).join('/'));
  return {
    name: 'art-manifest',
    resolveId(source) {
      return source === id ? rid : undefined;
    },
    load(loadId) {
      return loadId === rid ? `export default ${JSON.stringify(list())};` : undefined;
    },
    configureServer(server) {
      server.watcher.add(ART_DIR);
      const onChange = (file: string) => {
        if (!path.resolve(file).startsWith(ART_DIR)) return;
        const mod = server.moduleGraph.getModuleById(rid);
        if (mod) server.moduleGraph.invalidateModule(mod);
        server.ws.send({ type: 'full-reload' });
      };
      server.watcher.on('add', onChange);
      server.watcher.on('unlink', onChange);
    },
  };
}

/**
 * Dev-only: POST a PNG data URL to /__snap?name=foo → tools/blender/previews/game_foo.png.
 * Lets debugging scripts save full-resolution in-game renders (see src/debug.ts dbg.saveSnap).
 */
function devSnapshots(): Plugin {
  return {
    name: 'dev-snapshots',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/__snap', (req, res) => {
        if (req.method !== 'POST') { res.statusCode = 405; res.end(); return; }
        const name = (new URL(req.url ?? '', 'http://x').searchParams.get('name') ?? 'snap').replace(/[^\w-]/g, '_');
        const chunks: Buffer[] = [];
        req.on('data', (c: Buffer) => chunks.push(c));
        req.on('end', () => {
          const b64 = Buffer.concat(chunks).toString('utf8').replace(/^data:image\/png;base64,/, '');
          const out = path.join(ROOT, 'tools', 'blender', 'previews', `game_${name}.png`);
          fs.writeFileSync(out, Buffer.from(b64, 'base64'));
          res.end(out);
        });
      });
    },
  };
}

export default defineConfig({
  plugins: [artManifest(), devSnapshots()],
  server: { port: Number(process.env.PORT) || 5173, open: false },
  build: { target: 'es2022', chunkSizeWarningLimit: 2000 },
});
