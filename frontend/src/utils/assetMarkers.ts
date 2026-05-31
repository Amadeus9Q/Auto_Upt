/**
 * 素材标记解析工具
 * 统一管理正文中素材引用标记的格式及解析逻辑。
 */

export const ASSET_MARKER_PATTERN =
  /\{\{asset:(image|video|audio):([^}]+)\}\}|【(图片|视频|音频)：([^】]+)】/g;

const KIND_LABEL: Record<string, string> = {
  image: "图片",
  video: "视频",
  audio: "音频",
};

export function kindLabel(kind: string): string {
  return KIND_LABEL[kind] ?? kind;
}

/**
 * 从正文文本中提取所有素材标记，返回 { kind, token, index } 列表。
 */
export interface AssetMarkerMatch {
  kind: string;
  token: string;
  index: number;
}

export function findAssetMarkers(text: string): AssetMarkerMatch[] {
  const markers: AssetMarkerMatch[] = [];
  let match: RegExpExecArray | null;
  const pattern = new RegExp(ASSET_MARKER_PATTERN.source, "g");
  while ((match = pattern.exec(text)) !== null) {
    if (match[1]) {
      markers.push({ kind: match[1], token: match[2] ?? "", index: match.index });
    } else if (match[3]) {
      markers.push({ kind: kindFromLabel(match[3]), token: match[4] ?? "", index: match.index });
    }
  }
  return markers;
}

function kindFromLabel(label: string): string {
  if (label === "图片" || label === "image") return "image";
  if (label === "视频" || label === "video") return "video";
  if (label === "音频" || label === "audio") return "audio";
  return label;
}

/** 匹配素材标记中的 id:xxx 部分 */
export function extractAssetIdFromToken(token: string): string | null {
  const parts = token.split("｜id:");
  return parts[1] ?? null;
}

/** 提取标记的纯文本名称（去掉 id 部分） */
export function extractTokenName(token: string): string {
  return token.split("｜id:")[0].trim();
}
