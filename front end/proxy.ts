// File: src/proxy.ts

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// ==========================================
// KUMPULAN ATURAN (HELPER FUNCTIONS)
// ==========================================

// Aturan 1: Untuk Halaman Tamu (Login / Register)
function handleGuestRoute(request: NextRequest, token: string | undefined) {
  // Kalau sudah punya token, jangan biarkan masuk halaman login lagi
  if (token) {
    return NextResponse.redirect(new URL("/chat", request.url));
  }
  return NextResponse.next();
}

// Aturan 2: Untuk Halaman Chat / Member Area
function handleProtectedRoute(request: NextRequest, token: string | undefined) {
  // Kalau tidak punya token, tendang ke login
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

// ==========================================
// FUNGSI UTAMA (SATPAM PUSAT / DISPATCHER)
// ==========================================
export function proxy(request: NextRequest) {
  const token = request.cookies.get("token")?.value;
  const path = request.nextUrl.pathname;

  // 1. Cek jika URL adalah Halaman Tamu
  if (path === "/login" || path === "/register" || path === "/") {
    return handleGuestRoute(request, token);
  }

  // 2. Cek jika URL adalah Halaman Chat (dimulai dari '/chat')
  if (path.startsWith("/chat")) {
    return handleProtectedRoute(request, token);
  }
}

// ==========================================
// DAFTARKAN SEMUA RUTE YANG MAU DIJAGA DI SINI
// ==========================================
export const config = {
  matcher: [
    "/chat/:path*", // Berlaku untuk /chat dan /chat/123 dsb
    "/login",
    "/register",
  ],
};
