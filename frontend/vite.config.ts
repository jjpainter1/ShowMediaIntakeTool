import path from 'node:path'
import os from 'node:os'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const host = process.env.TAURI_DEV_HOST
const isTauri = Boolean(process.env.TAURI_ENV_PLATFORM)
const rootDir = path.dirname(fileURLToPath(import.meta.url))

// Keep Vite dependency cache outside Dropbox to avoid EBUSY on rename during sync.
const viteCacheDir = process.env.LOCALAPPDATA
  ? path.join(process.env.LOCALAPPDATA, 'ShowMediaIntakeTool', 'vite-cache')
  : path.join(os.tmpdir(), 'show-media-intake-vite')

// https://vite.dev/config/
export default defineConfig({
  cacheDir: viteCacheDir,
  plugins: [react()],
  resolve: {
    alias: isTauri
      ? {}
      : {
          '@tauri-apps/plugin-dialog': path.resolve(
            rootDir,
            'src/lib/stubs/tauri-plugin-dialog.ts',
          ),
        },
  },
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? { protocol: 'ws', host, port: 1421 }
      : undefined,
    watch: {
      ignored: ['**/src-tauri/**'],
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
