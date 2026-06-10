# Datahash Frontend

Next.js 16 (App Router) + React 19 + Tailwind v4 + TanStack Table.

## Dev

```bash
cp .env.example .env.local
npm install
npm run dev
```

Backend must be running on `http://localhost:8000` (or override `BACKEND_URL` / `NEXT_PUBLIC_BACKEND_URL`).

## Notes

- Auth is JWT stored in an httpOnly cookie (`datahash_jwt`) plus a mirror non-httpOnly cookie (`datahash_jwt_pub`) used by the client fetch wrapper. Both are set by the `/api/auth/login` route handler.
- Routes under `(app)/*` are gated by `src/middleware.ts`.
- Chat (`/chat`) is a placeholder for Stage 6 (CopilotKit).
