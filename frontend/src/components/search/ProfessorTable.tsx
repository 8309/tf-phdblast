"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import type { Professor } from "@/lib/types";

interface ProfessorTableProps {
  professors: Professor[];
  onSelectionChange: (indices: number[]) => void;
}

export default function ProfessorTable({
  professors,
  onSelectionChange,
}: ProfessorTableProps) {
  const t = useTranslations("label");
  const [sorting, setSorting] = useState<SortingState>([
    { id: "name", desc: false },
  ]);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggleRow = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      const arr = Array.from(next);
      onSelectionChange(arr);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => {
      let next: Set<number>;
      if (prev.size === professors.length) {
        next = new Set();
      } else {
        next = new Set(professors.map((_, i) => i));
      }
      onSelectionChange(Array.from(next));
      return next;
    });
  };

  // Extend professors with original index
  type Row = Professor & { _idx: number };
  const data: Row[] = useMemo(
    () => professors.map((p, i) => ({ ...p, _idx: i })),
    [professors],
  );

  const columnHelper = createColumnHelper<Row>();

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: "select",
        header: () => (
          <input
            type="checkbox"
            checked={selected.size === professors.length && professors.length > 0}
            onChange={toggleAll}
            className="rounded"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={selected.has(row.original._idx)}
            onChange={() => toggleRow(row.original._idx)}
            className="rounded"
          />
        ),
        size: 40,
      }),
      columnHelper.accessor("preliminary_score", {
        id: "score",
        header: t("score"),
        cell: (info) => (
          <span className="font-semibold text-blue-700">
            {info.getValue() ?? 0}
          </span>
        ),
        size: 60,
      }),
      columnHelper.accessor("name", {
        header: t("name"),
        cell: (info) => {
          const prof = info.row.original;
          return prof.profile_url ? (
            <a
              href={prof.profile_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              {info.getValue()}
            </a>
          ) : (
            info.getValue()
          );
        },
      }),
      columnHelper.accessor("university", {
        header: t("university"),
      }),
      columnHelper.accessor("email", {
        header: t("email"),
        cell: (info) => {
          const email = info.getValue();
          return email ? (
            <a
              href={`mailto:${email}`}
              className="text-blue-600 hover:underline"
            >
              {email}
            </a>
          ) : (
            <span className="text-gray-300">-</span>
          );
        },
      }),
      columnHelper.accessor("research_summary", {
        header: t("research"),
        cell: (info) => (
          <span className="line-clamp-2 text-xs text-gray-600">
            {info.getValue() ?? ""}
          </span>
        ),
      }),
      columnHelper.accessor("preliminary_reason", {
        id: "reason",
        header: t("reason"),
        cell: (info) => (
          <span className="text-xs text-gray-500">
            {info.getValue() ?? ""}
          </span>
        ),
      }),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selected, professors.length],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (professors.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-3 py-2 text-left font-medium text-gray-600 select-none"
                  style={{ width: header.getSize() }}
                  onClick={header.column.getToggleSortingHandler()}
                >
                  <span className="flex items-center gap-1 cursor-pointer">
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                    {header.column.getIsSorted() === "asc" && " \u2191"}
                    {header.column.getIsSorted() === "desc" && " \u2193"}
                  </span>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className="border-t border-gray-100 hover:bg-blue-50/40"
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
