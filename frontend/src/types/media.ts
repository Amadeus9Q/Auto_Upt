export type MediaKind = "image" | "video" | "audio";
export type MediaTab = "images" | "videos" | "audios";

export interface LocalAsset {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  previewUrl: string;
  kind: MediaKind;
  file: File;
  folderId?: string;
  aliasPaths?: string[];
  backendAssetId?: string;
  backendUrl?: string;
  uploadPurpose?: string;
}

export interface EditorAssets {
  images: LocalAsset[];
  videos: LocalAsset[];
  audios: LocalAsset[];
  coverImage: LocalAsset | null;
  coverImageId: string | null;
}

export interface MediaFolder {
  id: string;
  name: string;
  parentId: string | null;
  createdAt: string;
}
