"use client";

import type { Asset } from "@/lib/types";
import { mediaUrl } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/utils";
import { DownloadIcon, XIcon } from "./icons";

export function VideoModal({
  asset,
  onClose,
}: {
  asset: Asset | null;
  onClose: () => void;
}) {
  if (!asset) return null;
  const isVideo = asset.kind === "video" || asset.kind === "export" || asset.mime.startsWith("video/");
  const isAudio = asset.mime.startsWith("audio/");

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <div className="card-head">
          <div className="row">
            <strong style={{ fontSize: 14 }}>
              {isVideo ? "معاينة المقطع" : isAudio ? "معاينة الصوت" : "معاينة الصورة"}
            </strong>
            <span className="badge">{asset.kind}</span>
          </div>
          <div className="row">
            <a
              className="btn btn-sm"
              href={mediaUrl(asset.download_url)}
              download
              target="_blank"
              rel="noreferrer"
            >
              <DownloadIcon size={14} />
              تنزيل
            </a>
            <button className="btn-icon" onClick={onClose} aria-label="إغلاق">
              <XIcon size={16} />
            </button>
          </div>
        </div>
        {isVideo ? (
          <video src={mediaUrl(asset.url)} controls autoPlay playsInline />
        ) : isAudio ? (
          <div style={{ padding: 30 }}>
            <audio src={mediaUrl(asset.url)} controls style={{ width: "100%" }} />
          </div>
        ) : (
          <img src={mediaUrl(asset.url)} alt="" style={{ width: "100%", display: "block" }} />
        )}
        <div
          className="row wrap"
          style={{
            padding: "12px 18px",
            borderTop: "1px solid var(--line)",
            color: "var(--muted)",
            fontSize: 12,
            gap: 16,
          }}
        >
          <span>{formatBytes(asset.size_bytes)}</span>
          <span>{formatDuration(asset.duration_s)}</span>
          {asset.width && asset.height ? (
            <span>
              {asset.width}×{asset.height}
            </span>
          ) : null}
          <span className="mono" style={{ marginInlineStart: "auto", opacity: 0.6 }}>
            {asset.id}
          </span>
        </div>
      </div>
    </div>
  );
}
