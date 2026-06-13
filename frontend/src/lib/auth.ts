import { decodeJwt as joseDecodeJwt } from "jose";

import type { User } from "./types";

export const JWT_COOKIE = "datahash_jwt";

interface JwtPayload {
  sub?: string;
  user_id?: string | number;
  email?: string;
  exp?: number;
}

export function decodeJwt(token: string): User | null {
  try {
    const payload = joseDecodeJwt(token) as JwtPayload;
    const userId = payload.sub ?? payload.user_id;
    if (userId === undefined || payload.exp === undefined) {
      return null;
    }
    return {
      user_id: String(userId),
      email: payload.email,
      exp: payload.exp,
    };
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const decoded = decodeJwt(token);
  if (!decoded) return true;
  return decoded.exp * 1000 < Date.now();
}
