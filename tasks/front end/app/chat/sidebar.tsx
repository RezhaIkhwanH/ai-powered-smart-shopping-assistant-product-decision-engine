"use client";

import { useChatStore } from "@/store/chatStore";
import { Plus, MessageSquare } from "lucide-react";

export default function Sidebar() {
  const { rooms, activeRoomId, setActiveRoom } = useChatStore();

  return (
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
          <button
            key={room.id}
            onClick={() => setActiveRoom(room.id)}
            className={`flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors ${
              activeRoomId === room.id
                ? "bg-zinc-800 text-white"
                : "hover:bg-zinc-800/50 text-zinc-400"
            }`}
          >
            <MessageSquare size={18} className="shrink-0" />
            <span className="truncate text-sm font-medium">{room.title}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
