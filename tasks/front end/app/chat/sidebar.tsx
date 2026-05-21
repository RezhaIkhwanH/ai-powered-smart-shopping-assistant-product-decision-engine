"use client";

import { useChatStore } from "@/store/chatStore";
import { Plus, MessageSquare, Trash2, AlertTriangle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

// Helper untuk mengambil token JWT
const getToken = () => {
  if (typeof document !== "undefined") {
    const match = document.cookie.match(new RegExp("(^| )token=([^;]+)"));
    if (match) return match[2];
  }
  return null;
};

export default function Sidebar() {
  const router = useRouter();
  const { rooms, activeRoomId, setActiveRoom, deleteRoom } = useChatStore();

  // State untuk efek loading saat menghapus
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // State BARU: Menampung ID obrolan yang mau dihapus (sekaligus trigger pembuka modal)
  const [roomToDelete, setRoomToDelete] = useState<string | null>(null);

  // 1. Fungsi saat ikon tempat sampah diklik (Hanya membuka modal)
  const handleDeleteClick = (e: React.MouseEvent, roomId: string) => {
    e.stopPropagation(); // Cegah merambat ke tombol pilih room
    setRoomToDelete(roomId);
  };

  // 2. Fungsi eksekutor jika user klik "Hapus" di dalam Modal
  const executeDelete = async () => {
    if (!roomToDelete) return;

    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    setDeletingId(roomToDelete);

    try {
      const res = await fetch(`http://127.0.0.1:8000/room/${roomToDelete}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const result = await res.json();

      if (result.status === "success" || res.ok) {
        deleteRoom(roomToDelete);

        if (activeRoomId === roomToDelete) {
          setActiveRoom(null);
        }
      } else {
        throw new Error(result.data || "Gagal menghapus room");
      }
    } catch (error: any) {
      console.error("Gagal hapus room:", error);
      alert(error.message);
    } finally {
      setDeletingId(null);
      setRoomToDelete(null); // Tutup modal setelah selesai
    }
  };

  return (
    <>
      {/* ========================================== */}
      {/* AREA SIDEBAR UTAMA */}
      {/* ========================================== */}
      <div className="w-72 bg-zinc-900 border-r border-zinc-800 flex flex-col shrink-0">
        <div className="p-4 border-b border-zinc-800">
          <button
            onClick={() => setActiveRoom(null)}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-semibold text-zinc-900 hover:bg-white transition-colors"
          >
            <Plus size={18} />
            Chat Baru
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {rooms.map((room) => (
            <div key={room.id} className="relative group flex items-center">
              <button
                onClick={() => setActiveRoom(room.id)}
                className={`flex flex-1 items-center gap-3 rounded-lg p-3 pr-10 text-left transition-colors ${
                  activeRoomId === room.id
                    ? "bg-zinc-800 text-white"
                    : "hover:bg-zinc-800/50 text-zinc-400"
                }`}
              >
                <MessageSquare size={18} className="shrink-0" />
                <span className="truncate text-sm font-medium">
                  {room.title}
                </span>
              </button>

              <button
                // Ubah fungsi onClick menjadi pembuka modal
                onClick={(e) => handleDeleteClick(e, room.id)}
                disabled={deletingId === room.id}
                className={`absolute right-2 p-2 text-zinc-500 hover:text-red-500 transition-all ${
                  activeRoomId === room.id
                    ? "opacity-100"
                    : "opacity-0 group-hover:opacity-100"
                } disabled:opacity-50`}
                title="Hapus obrolan"
              >
                {deletingId === room.id ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-500 border-t-transparent" />
                ) : (
                  <Trash2 size={16} />
                )}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ========================================== */}
      {/* CUSTOM MODAL CONFIRMATION */}
      {/* ========================================== */}
      {roomToDelete && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-sm rounded-2xl bg-zinc-900 border border-zinc-700 p-6 shadow-2xl zoom-in-95 animate-in duration-200">
            {/* Header Modal */}
            <div className="flex items-start gap-4 mb-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-500/10">
                <AlertTriangle className="h-5 w-5 text-red-500" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-zinc-100">
                  Hapus Obrolan?
                </h3>
                <p className="text-sm text-zinc-400 mt-1 leading-relaxed">
                  Tindakan ini tidak dapat dibatalkan. Riwayat percakapan akan
                  dihapus secara permanen.
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setRoomToDelete(null)}
                disabled={deletingId !== null}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition-colors disabled:opacity-50"
              >
                Batal
              </button>
              <button
                onClick={executeDelete}
                disabled={deletingId !== null}
                className="flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-700 transition-colors disabled:opacity-50 min-w-[90px]"
              >
                {deletingId ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                ) : (
                  "Hapus"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
