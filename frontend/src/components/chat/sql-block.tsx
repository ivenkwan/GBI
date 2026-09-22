"use client";

export function SqlBlock({ sql }: { sql: string }) {
  return (
    <div className="bg-gray-900 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
        <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
          Generated SQL
        </span>
        <button
          onClick={() => navigator.clipboard.writeText(sql)}
          className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
        >
          Copy
        </button>
      </div>
      <pre className="p-4 text-xs text-green-400 font-mono overflow-x-auto">
        {sql}
      </pre>
    </div>
  );
}
