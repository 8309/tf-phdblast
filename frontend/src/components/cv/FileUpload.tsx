"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";

interface FileUploadProps {
  onChange: (file: File) => void;
}

export default function FileUpload({ onChange }: FileUploadProps) {
  const t = useTranslations("label");
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    (file: File) => {
      setError(null);
      if (file.type !== "application/pdf") {
        setError(t("pdf_only"));
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        setError(t("file_too_large"));
        return;
      }
      setFileName(file.name);
      onChange(file);
    },
    [onChange, t],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const onDragLeave = useCallback(() => {
    setDragging(false);
  }, []);

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onClick={() => inputRef.current?.click()}
      className={`
        flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed
        px-6 py-12 text-center transition-colors cursor-pointer
        ${
          dragging
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100"
        }
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={onInputChange}
      />

      <svg
        className="h-10 w-10 text-gray-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"
        />
      </svg>

      {error && (
        <p className="text-sm font-medium text-red-500">{error}</p>
      )}
      {fileName ? (
        <p className="text-sm font-medium text-gray-700">{fileName}</p>
      ) : (
        <>
          <p className="text-sm text-gray-600">
            {t("drag_drop_pdf")}
          </p>
          <p className="text-xs text-gray-400">{t("pdf_only")}</p>
        </>
      )}
    </div>
  );
}
