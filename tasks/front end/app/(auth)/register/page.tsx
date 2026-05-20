"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage("");

    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch("http://127.0.0.1:8000/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.message ||
            "Gagal mendaftar, periksa kembali informasi Anda.",
        );
      }

      router.push("/login");
    } catch (error: any) {
      setErrorMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      {/* Container Form Register */}
      <div className="w-full max-w-md rounded-2xl bg-zinc-900 p-8 shadow-xl border border-zinc-800">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-semibold tracking-wide text-zinc-100">
            REGISTER
          </h1>
          {errorMessage ? (
            <p className="mt-2 text-sm text-red-500">{errorMessage}</p>
          ) : null}
        </div>

        <form onSubmit={handleRegister} className="space-y-5">
          <div className="space-y-2">
            <label
              className="text-sm font-medium text-zinc-400"
              htmlFor="username"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              disabled={isLoading}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-4 py-3 text-sm text-zinc-200 focus:border-zinc-500 focus:outline-none transition-colors"
            />
          </div>

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
              disabled={isLoading}
              onChange={(e) => setEmail(e.target.value)}
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
              disabled={isLoading}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-4 py-3 text-sm text-zinc-200 focus:border-zinc-500 focus:outline-none transition-colors"
            />
          </div>

          <div className="space-y-2">
            <label
              className="text-sm font-medium text-zinc-400"
              htmlFor="confirm-password"
            >
              Konfirmasi Password
            </label>
            <input
              id="confirm-password"
              type="password"
              disabled={isLoading}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-4 py-3 text-sm text-zinc-200 focus:border-zinc-500 focus:outline-none transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={
              isLoading || !username || !email || !password || !confirmPassword
            }
            className="w-full rounded-lg bg-zinc-100 px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-white transition-colors mt-4 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            {isLoading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-zinc-900"></div>
            ) : (
              "Daftar"
            )}
          </button>
        </form>

        {/* Link ke Login */}

        <p className="mt-6 text-center text-sm text-zinc-500">
          Sudah punya akun?{" "}
          <Link
            href="/login"
            className="font-medium text-zinc-300 hover:text-white transition-colors"
          >
            Masuk
          </Link>
        </p>
      </div>
    </div>
  );
}
