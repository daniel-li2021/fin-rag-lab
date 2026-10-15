"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";

// Render original bytes; no reconstructed tables or generated highlights.
export default function OriginalPage({ url, hash, initialPage = 1 }) {
  const [document, setDocument] = useState(null),
    [page, setPage] = useState(initialPage || 1),
    [width, setWidth] = useState(300),
    [zoom, setZoom] = useState(1),
    [error, setError] = useState(""),
    [rendered, setRendered] = useState(false);
  const canvas = useRef(null),
    container = useRef(null);
  useEffect(() => {
    setPage(initialPage || 1);
    setZoom(1);
  }, [url, initialPage]);
  useEffect(() => {
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(180, Math.floor(entries[0].contentRect.width))),
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let loading,
      active = true;
    setDocument(null);
    setError("");
    setRendered(false);
    (async () => {
      const response = await fetch(url, {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok)
        throw Error(
          "Original unavailable. The saved excerpt remains accessible.",
        );
      if (!response.headers.get("content-type")?.includes("application/pdf"))
        throw Error(
          "This original is not a PDF. Use the original download link.",
        );
      const bytes = await response.arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      const actual = [...new Uint8Array(digest)]
        .map((n) => n.toString(16).padStart(2, "0"))
        .join("");
      if (actual !== hash?.toLowerCase())
        throw Error("Original hash mismatch. Preview withheld.");
      const pdfjs = await import("pdfjs-dist");
      if (!active) return;
      pdfjs.GlobalWorkerOptions.workerSrc = "/pdfjs/pdf.worker.min.mjs";
      loading = pdfjs.getDocument({
        data: new Uint8Array(bytes),
        isEvalSupported: false,
        cMapUrl: "/pdfjs/cmaps/",
        cMapPacked: true,
        standardFontDataUrl: "/pdfjs/standard_fonts/",
        wasmUrl: "/pdfjs/wasm/",
      });
      const pdf = await loading.promise;
      if (active) setDocument(pdf);
    })().catch((e) => {
      if (active && e.name !== "AbortError") setError(e.message);
    });
    return () => {
      active = false;
      controller.abort();
      loading?.destroy().catch(() => {});
    };
  }, [url, hash]);
  useEffect(() => {
    if (!document) return;
    let active = true,
      render;
    setRendered(false);
    setError("");
    (async () => {
      if (page < 1 || page > document.numPages)
        throw Error(
          `Original has ${document.numPages} physical pages; cited page is unavailable.`,
        );
      const pdfPage = await document.getPage(page);
      if (!active) return;
      const viewport = pdfPage.getViewport({
        scale: (width * zoom) / pdfPage.getViewport({ scale: 1 }).width,
      });
      const outputScale = Math.min(devicePixelRatio || 1, 2),
        node = canvas.current;
      node.width = Math.floor(viewport.width * outputScale);
      node.height = Math.floor(viewport.height * outputScale);
      node.style.width = `${Math.floor(viewport.width)}px`;
      node.style.height = `${Math.floor(viewport.height)}px`;
      render = pdfPage.render({
        canvasContext: node.getContext("2d"),
        viewport,
        transform: [outputScale, 0, 0, outputScale, 0, 0],
      });
      await render.promise;
      if (active) setRendered(true);
    })().catch((e) => {
      if (active && e.name !== "RenderingCancelledException")
        setError(e.message);
    });
    return () => {
      active = false;
      render?.cancel();
    };
  }, [document, page, width, zoom]);
  return (
    <section
      className="pdf-preview"
      ref={container}
      aria-label="Hash-verified original page"
    >
      {document && (
        <div className="pdf-toolbar">
          <button
            aria-label="Previous original page"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            <ArrowLeft size={14} />
          </button>
          <span>
            Page {page} / {document.numPages}
          </span>
          <button
            aria-label="Next original page"
            disabled={page >= document.numPages}
            onClick={() => setPage((p) => p + 1)}
          >
            <ArrowRight size={14} />
          </button>
          <select
            aria-label="Original page zoom"
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
          >
            <option value={1}>Fit width</option>
            <option value={1.5}>150%</option>
            <option value={2}>200%</option>
          </select>
        </div>
      )}
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : (
        !rendered && (
          <p className="small-note" role="status">
            Loading hash-verified original page…
          </p>
        )
      )}
      <div className="pdf-canvas-scroll">
        <canvas
          ref={canvas}
          aria-label={`Original PDF physical page ${page}`}
          role="img"
          style={{ display: rendered ? "block" : "none" }}
        />
      </div>
      {rendered && (
        <p className="small-note">
          SHA-256 verified · Original physical page {page}
        </p>
      )}
    </section>
  );
}
