"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();

  // 1. State untuk menyimpan ketikan user & status sistem
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // 2. Fungsi eksekutor saat tombol masuk/enter ditekan
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); // Mencegah browser refresh
    setIsLoading(true);
    setErrorMessage(""); // Kosongkan error sebelumnya jika ada

    try {
      // 3. Menembak API Backend Anda
      const response = await fetch("http://127.0.0.1:8000/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (data.status === "error") {
        throw new Error(
          data.message ||
            "Gagal login, periksa kembali email dan password Anda.",
        );
      }

      // Jika API mengembalikan status error (400, 401, 404, dll)
      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.message ||
            "Gagal login, periksa kembali email dan password Anda.",
        );
      }

      // 4. Mengambil Token (Sesuaikan 'data.token' dengan format balasan API FastAPI Anda)
      // Biasanya FastAPI mengembalikan { access_token: "..." }
      const token = data.data.access_token;

      if (token) {
        // 5. Simpan ke Cookie agar bisa dibaca oleh proxy.ts
        // max-age=86400 berarti cookie akan kedaluwarsa dalam 1 hari (dalam hitungan detik)
        document.cookie = `token=${token}; path=/; max-age=86400; SameSite=Strict`;

        // 6. Arahkan ke halaman chat
        router.push("/chat");
      } else {
        throw new Error("Token tidak ditemukan dari respons server.");
      }
    } catch (error: any) {
      setErrorMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      {/* Container Form Login */}
      <div className="w-full max-w-md rounded-2xl bg-zinc-900 p-8 shadow-xl border border-zinc-800">
        {/* Judul */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-semibold tracking-wide text-zinc-100">
            LOGIN
          </h1>
        </div>

        {/* Menampilkan Pesan Error (jika ada) */}
        {errorMessage && (
          <div className="mb-6 rounded-lg bg-red-950/50 p-3 text-sm text-red-400 border border-red-900/50 text-center">
            {errorMessage}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleLogin} className="space-y-6">
          <div className="space-y-2">
            <label
              className="text-sm font-medium text-zinc-400"
              htmlFor="email"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="nama@email.com"
              required
              className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-4 py-3 text-sm text-zinc-200 focus:border-zinc-500 focus:outline-none transition-colors"
            />
          </div>

          <div className="space-y-2">
            <label
              className="text-sm font-medium text-zinc-400"
              htmlFor="password"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-4 py-3 text-sm text-zinc-200 focus:border-zinc-500 focus:outline-none transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading || !email || !password}
            className="w-full rounded-lg bg-zinc-100 px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors mt-2"
          >
            {isLoading ? "Memproses..." : "Masuk"}
          </button>
        </form>

        {/* Link ke Register */}
        <p className="mt-6 text-center text-sm text-zinc-500">
          Belum punya akun?{" "}
          <Link
            href="/register"
            className="font-medium text-zinc-300 hover:text-white transition-colors"
          >
            Daftar
          </Link>
        </p>
      </div>
    </div>
  );
}
