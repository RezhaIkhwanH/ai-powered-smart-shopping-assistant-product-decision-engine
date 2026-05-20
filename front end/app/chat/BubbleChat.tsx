import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function BubbleChat({
  text,
  sender,
  imageUrls,
}: {
  text: string;
  sender: "user" | "ai";
  imageUrls?: string[] | null;
}) {
  const isUser = sender === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] md:max-w-[70%] rounded-2xl p-4 text-sm leading-relaxed flex flex-col gap-3 ${
          isUser
            ? "bg-zinc-100 text-zinc-900 rounded-tr-sm whitespace-pre-wrap"
            : "bg-zinc-800 text-zinc-200 rounded-tl-sm shadow-md"
        }`}
      >
        {/* GALERI PREVIEW BANYAK GAMBAR */}
        {imageUrls && imageUrls.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {imageUrls.map((url, index) => (
              <div
                key={index}
                className="relative w-32 h-32 sm:w-48 sm:h-48 rounded-xl overflow-hidden border border-zinc-700/50 shadow-sm"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={url}
                  alt={`Attachment ${index + 1}`}
                  className="object-cover w-full h-full"
                />
              </div>
            ))}
          </div>
        )}

        {/* TEKS PESAN BAWAAN */}
        {!isUser ? (
          <div className="prose prose-invert prose-sm max-w-none text-zinc-200">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              // ==========================================
              // CUSTOM STYLING UNTUK MARKDOWN (TABEL DLL)
              // ==========================================
              components={{
                // 1. Modifikasi Tag <table> utama
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto my-4 rounded-lg border border-zinc-700 shadow-sm">
                    <table
                      className="w-full text-left border-collapse"
                      {...props}
                    />
                  </div>
                ),
                // 2. Modifikasi Header Tabel <thead>
                thead: ({ node, ...props }) => (
                  <thead className="bg-zinc-700/50 text-zinc-100" {...props} />
                ),
                // 3. Modifikasi Sel Header <th>
                th: ({ node, ...props }) => (
                  <th
                    className="px-4 py-3 font-semibold border-b border-zinc-700 whitespace-nowrap"
                    {...props}
                  />
                ),
                // 4. Modifikasi Sel Data <td>
                td: ({ node, ...props }) => (
                  <td
                    className="px-4 py-3 border-b border-zinc-700/50 text-zinc-300"
                    {...props}
                  />
                ),
                // 5. (Opsional) Modifikasi tag <a> untuk link agar lebih menarik
                a: ({ node, ...props }) => (
                  <a
                    className="text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors"
                    {...props}
                  />
                ),
              }}
            >
              {text}
            </ReactMarkdown>
          </div>
        ) : (
          <span>{text}</span>
        )}
      </div>
    </div>
  );
}
